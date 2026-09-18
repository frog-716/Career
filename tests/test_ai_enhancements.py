import json
import pytest

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.opportunity import create_opportunity
from workbench.providers import TestProvider
from workbench.secret_store import MemorySecretStore
from workbench.model_gateway import GatewayError, OpenAICompatibleAdapter
from workbench.model_gateway import ModelGateway
from batch_c_helpers import editor_client


HEADERS = {"X-Career-Request": "1"}


def test_model_config_uses_secret_reference_and_explicit_default_delete(tmp_path):
    secrets = MemorySecretStore()
    store = Store(tmp_path / "data", TestProvider(), secrets)
    client = TestClient(create_app(store), headers={**HEADERS, "Content-Type": "application/json"})
    created = client.post("/api/ai/models", json={
        "display_name": "Synthetic OpenAI", "provider": "OpenAI-compatible",
        "base_url": "https://example.test/v1", "model": "gpt-test",
        "api_key": "do-not-persist-this-key", "enabled": True,
    }).json()
    assert created["api_key_masked"] == "••••••••"
    assert "do-not-persist-this-key" not in json.dumps(created)
    assert "do-not-persist-this-key" not in store.db.read_bytes().decode("utf-8", "ignore")
    configured = client.post(f"/api/ai/models/{created['id']}/default", json={"expected_revision": created["revision"]})
    assert configured.status_code == 200
    deleted = client.request("DELETE", f"/api/ai/models/{created['id']}", json={"confirm": True})
    assert deleted.status_code == 200
    assert store.state()["ai"]["default_model_config_id"] is None
    assert secrets.values == {}


def test_deepseek_legacy_model_alias_is_normalized_and_first_config_is_default(tmp_path):
    secrets = MemorySecretStore()
    store = Store(tmp_path / "data", TestProvider(), secrets)
    client = TestClient(create_app(store), headers={**HEADERS, "Content-Type": "application/json"})
    created = client.post("/api/ai/models", json={
        "display_name": "DeepSeek", "provider": "DeepSeek",
        "base_url": "https://api.deepseek.com", "model": "deepseek-v4.1-flash",
        "api_key": "synthetic-key", "enabled": True,
    })
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["model"] == "deepseek-flash"
    assert store.state()["ai"]["default_model_config_id"] == body["id"]


def test_structured_resume_ai_is_proposal_until_confirmed(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    client = editor_client(store)
    response = client.post(client.editor_path + "/ai-suggest", json={
        "instruction": "保持事实不变，检查表达。", "idempotency_key": "resume-ai-1",
    })
    assert response.status_code == 200, response.text
    proposal = response.json()
    current = client.get(client.editor_path).json()
    assert proposal["status"] == "pending"
    assert current["revision"] == proposal["expected_revision"]
    resolved = client.post(client.editor_path + f"/ai-proposals/{proposal['id']}/resolve", json={"decision": "accept"})
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["proposal"]["status"] == "accepted"


def test_research_web_proposal_requires_confirmation_and_keeps_provenance(tmp_path, monkeypatch):
    store = Store(tmp_path / "data", TestProvider())
    client = TestClient(create_app(store), headers={**HEADERS, "Content-Type": "application/json"})
    opportunity = create_opportunity(store, {"company_name": "虚构公司", "title": "研究工程师", "jd": "负责研究", "idempotency_key": "research-op"})
    monkeypatch.setattr("workbench.research.web_search", lambda *args: [{"url": "https://example.test/company", "title": "公司主页", "retrieved_at": "2026-09-18T00:00:00+00:00"}])
    before = client.get(f"/api/opportunities/{opportunity['id']}/research-overview").json()
    proposal = client.post(f"/api/opportunities/{opportunity['id']}/research/update", json={"idempotency_key": "research-1"})
    assert proposal.status_code == 200, proposal.text
    proposal = proposal.json()
    pending = client.get(f"/api/opportunities/{opportunity['id']}/research-overview").json()
    assert pending["opportunity"]["revision"] == before["opportunity"]["revision"]
    accepted = client.post(f"/api/opportunities/{opportunity['id']}/research-proposals/{proposal['id']}/resolve", json={"decision": "accept"})
    assert accepted.status_code == 200, accepted.text
    after = client.get(f"/api/opportunities/{opportunity['id']}/research-overview").json()
    assert after["opportunity"]["items"]
    assert after["opportunity"]["items"][0]["source_refs"][0]["url"] == "https://example.test/company"


@pytest.mark.parametrize("status,code", [(401, "authentication_failed"), (404, "model_unavailable"), (429, "rate_limited"), (503, "provider_error")])
def test_openai_compatible_connection_maps_provider_status(monkeypatch, status, code):
    class Response:
        status_code = status
        content = b"{}"

        def json(self): return {}

    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def post(self, *args, **kwargs): return Response()

    monkeypatch.setattr("workbench.model_gateway.httpx.Client", lambda **kwargs: Client())
    adapter = OpenAICompatibleAdapter({"base_url": "https://example.test/v1", "model": "gpt", "provider": "OpenAI-compatible"}, "key")
    with pytest.raises(GatewayError) as error:
        adapter.test()
    assert error.value.code == code


def test_model_gateway_uses_selected_config_without_exposing_secret(tmp_path, monkeypatch):
    secrets = MemorySecretStore()
    store = Store(tmp_path / "data", TestProvider(), secrets)
    client = TestClient(create_app(store), headers={**HEADERS, "Content-Type": "application/json"})
    config = client.post("/api/ai/models", json={
        "display_name": "Gateway test", "provider": "OpenAI-compatible",
        "base_url": "https://example.test/v1", "model": "gpt-5.6-luna",
        "api_key": "gateway-secret", "enabled": True,
    }).json()
    client.post(f"/api/ai/models/{config['id']}/default", json={"expected_revision": config["revision"]})
    monkeypatch.setattr(OpenAICompatibleAdapter, "complete", lambda self, packet, schema: {"ok": True})
    result, diagnostics = ModelGateway(store).generate("synthetic_task", {"id": "context-1"}, {"version": 4})
    assert result == {"ok": True}
    assert diagnostics["model_config_id"] == config["id"]
    with store.connect(False) as connection:
        assert all("gateway-secret" not in json.dumps(item) for item in store._records(connection, "ai_call"))
