"""Stage 1.5: production-data LOCAL_ONLY must fail closed at AI boundaries."""

import json

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.ai_config import secret as read_secret
from workbench.model_gateway import OpenAICompatibleAdapter
from workbench.opportunity import create_opportunity
from workbench.providers import LocalOnlyDisabled, RealProvider, TestProvider, get_provider
from workbench.runtime_mode import RuntimeModeError, startup_mode
from workbench.secret_store import SecretStore


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


class SecretAccessTrap(SecretStore):
    """Fails immediately if LOCAL_ONLY reaches any secret-store operation."""

    def __init__(self):
        self.calls = []

    def _fail(self, operation, *args):
        self.calls.append((operation, args))
        raise AssertionError(f"LOCAL_ONLY touched secret store: {operation}")

    def allocate_ref(self):
        return self._fail("allocate_ref")

    def put(self, ref, value):
        return self._fail("put", ref, value)

    def get(self, ref):
        return self._fail("get", ref)

    def delete(self, ref):
        return self._fail("delete", ref)


def seed_real_style_model_config(store):
    config = {
        "id": "model-config:production-shaped",
        "display_name": "Production-shaped synthetic config",
        "provider": "OpenAI-compatible",
        "base_url": "https://provider.invalid/v1",
        "destination_binding": {
            "provider": "OpenAI-compatible",
            "provider_key": "openai-compatible",
            "scheme": "https",
            "host": "provider.invalid",
            "port": 443,
            "base_path": "/v1",
            "normalized_url": "https://provider.invalid/v1",
        },
        "model": "synthetic-production-model",
        "api_key_ref": "career-ai-real-style-secret-ref",
        "secret_status": "ready",
        "enabled": True,
        "created_at": "2026-09-20T00:00:00+00:00",
        "updated_at": "2026-09-20T00:00:00+00:00",
    }
    with store.connect() as connection:
        store._record(connection, "ai_model_config", config)
        connection.execute(
            "INSERT INTO current VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
            ("ai-settings", "ai_settings", 0, json.dumps({
                "id": "ai-settings",
                "default_model_config_id": config["id"],
            }, ensure_ascii=False, sort_keys=True)),
        )


def network_trap(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError(f"LOCAL_ONLY attempted network access: args={args!r}")

    monkeypatch.setattr("workbench.research.httpx.get", fail)
    monkeypatch.setattr("workbench.providers.httpx.Client", fail)
    monkeypatch.setattr("workbench.model_gateway.httpx.Client", fail)


def test_missing_or_invalid_mode_is_local_only_and_startup_requires_explicit_mode(monkeypatch):
    monkeypatch.delenv("CAREER_AI_MODE", raising=False)
    assert get_provider().diagnostics()["mode"] == "local_only"
    with pytest.raises(LocalOnlyDisabled) as missing:
        get_provider().complete({})
    assert missing.value.code == "local_only_disabled"

    monkeypatch.setenv("CAREER_AI_MODE", "maybe-real")
    assert get_provider().diagnostics()["mode"] == "local_only"
    with pytest.raises(RuntimeModeError):
        startup_mode()

    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    assert startup_mode().value == "LOCAL_ONLY"
    monkeypatch.setenv("CAREER_AI_MODE", "AI_ENABLED")
    assert startup_mode().value == "AI_ENABLED"


def test_production_shaped_config_blocks_all_ai_routes_without_secret_or_network(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    monkeypatch.setenv("CAREER_AI_PROVIDER", "test")
    monkeypatch.setenv("CAREER_AI_API_KEY", "sk-real-looking-but-synthetic")
    network_trap(monkeypatch)

    secret_trap = SecretAccessTrap()
    provider = TestProvider()
    real_provider = RealProvider(
        "https://provider.invalid/v1", "synthetic", "sk-real-looking-but-synthetic"
    )
    store = Store(tmp_path / "data", provider, secret_trap)
    seed_real_style_model_config(store)
    client = TestClient(create_app(store), headers=HEADERS)
    store.save_profile("LOCAL_ONLY 隔离用虚构候选人资料", 0)

    with pytest.raises(LocalOnlyDisabled):
        provider.complete({})
    with pytest.raises(LocalOnlyDisabled):
        real_provider.complete({})
    with pytest.raises(LocalOnlyDisabled):
        read_secret(store, {"api_key_ref": "career-ai-real-style-secret-ref"})
    adapter = OpenAICompatibleAdapter(
        {"provider": "OpenAI-compatible", "base_url": "https://provider.invalid/v1", "model": "synthetic"},
        "sk-real-looking-but-synthetic",
    )
    with pytest.raises(LocalOnlyDisabled):
        adapter.test()
    # The gate is bound to the Store created for this candidate, so changing
    # the process environment later cannot turn a production-shaped copy on.
    monkeypatch.setenv("CAREER_AI_MODE", "AI_ENABLED")
    with pytest.raises(LocalOnlyDisabled):
        provider.complete({})
    with pytest.raises(LocalOnlyDisabled):
        real_provider.complete({})
    with pytest.raises(LocalOnlyDisabled):
        adapter.test()

    legacy_job = store.save_job({
        "company": "LOCAL_ONLY 虚构公司",
        "title": "旧分析岗位",
        "jd": "仅用于本地隔离测试",
        "idempotency_key": "local-only-legacy-job",
    })
    legacy = client.post("/api/analysis", json={
        "job_id": legacy_job["id"],
        "kind": "job",
        "idempotency_key": "local-only-legacy-analysis",
    })

    opportunity = create_opportunity(store, {
        "company_name": "LOCAL_ONLY 研究公司",
        "title": "本地隔离研究岗位",
        "jd": "禁止任何真实 Research 出网",
        "idempotency_key": "local-only-research-opportunity",
    })
    research = client.post(
        f"/api/opportunities/{opportunity['id']}/research/update",
        json={"idempotency_key": "local-only-research", "search_confirmed": True},
    )

    started = client.post(
        f"/api/opportunities/{opportunity['id']}/resume/start",
        json={
            "expected_opportunity_revision": opportunity["revision"],
            "idempotency_key": "local-only-resume-start",
            "source": {"kind": "blank"},
        },
    ).json()
    saved = client.put(
        f"/api/resume-documents/{started['document_id']}",
        json={
            "document": {
                "schemaVersion": 1,
                "profile": {"id": "local-only-profile", "name": "虚构候选人", "contacts": []},
                "sections": [], "formatting": {}, "meta": {},
            },
            "expected_revision": started["revision"],
        },
    )
    assert saved.status_code == 200, saved.text
    resume = client.post(
        f"/api/resume-documents/{started['document_id']}/ai-suggest",
        json={"instruction": "只用于隔离测试", "idempotency_key": "local-only-resume"},
    )

    submitted = client.post(
        f"/api/opportunities/{opportunity['id']}/submitted",
        json={"expected_revision": opportunity["revision"], "idempotency_key": "local-only-submit", "resume": {"mode": "none"}},
    )
    assert submitted.status_code == 200, submitted.text
    submitted_opportunity = submitted.json()["opportunity"]
    interview = client.post(
        f"/api/opportunities/{submitted_opportunity['id']}/interviews/real",
        json={"name": "一面", "expected_opportunity_revision": submitted_opportunity["revision"], "idempotency_key": "local-only-interview"},
    )
    assert interview.status_code == 200, interview.text
    interview_body = interview.json()
    interview_id = interview_body["interview"]["id"]
    raw = client.put(
        f"/api/opportunities/{submitted_opportunity['id']}/interviews/{interview_id}/raw",
        json={"content": "虚构面试 Raw", "expected_revision": 0, "idempotency_key": "local-only-raw"},
    )
    assert raw.status_code == 200, raw.text
    interview_ai = client.post(
        f"/api/opportunities/{submitted_opportunity['id']}/interviews/{interview_id}/generate-final-review",
        json={"communication_ids": [], "wiki_ids": [], "idempotency_key": "local-only-interview-ai"},
    )
    ephemeral_test = client.post("/api/ai/test-connection", json={
        "provider": "OpenAI-compatible", "base_url": "https://provider.invalid/v1",
        "model": "synthetic", "api_key": "sk-real-looking-but-synthetic",
    })

    for response in (legacy, research, resume, interview_ai, ephemeral_test):
        assert response.status_code == 503, response.text
        assert response.json()["code"] == "local_only_disabled"
        assert "local_only_disabled" in response.json()["detail"]
    assert provider.diagnostics()["mode"] == "test"
    assert secret_trap.calls == []


def test_local_only_rebinds_an_injected_provider_created_under_ai_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("CAREER_AI_MODE", "AI_ENABLED")
    injected = TestProvider()
    payload = injected.build_payload({"taskKind": "job", "sources": []})
    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    store = Store(tmp_path / "data", injected)
    monkeypatch.setenv("CAREER_AI_MODE", "AI_ENABLED")

    with pytest.raises(LocalOnlyDisabled):
        store.provider.complete(payload)


def test_local_only_keeps_manual_editing_and_backup_capable(tmp_path, monkeypatch):
    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    store = Store(tmp_path / "data", TestProvider(), SecretAccessTrap())
    client = TestClient(create_app(store), headers=HEADERS)

    profile = client.post("/api/profile", json={"content": "仅用于本地手工编辑", "expected_revision": 0})
    assert profile.status_code == 200, profile.text
    opportunity = client.post("/api/opportunities", json={
        "company_name": "本地编辑公司", "title": "本地编辑岗位", "jd": "虚构 JD",
        "idempotency_key": "local-only-manual-opportunity",
    })
    assert opportunity.status_code == 200, opportunity.text
    state = client.get("/api/state?view=summary")
    assert state.status_code == 200
    assert state.json()["opportunities"][0]["company"] == "本地编辑公司"
