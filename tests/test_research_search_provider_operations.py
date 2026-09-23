"""Research search remains preview-confirmed, isolated and durably idempotent."""

import threading
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi.testclient import TestClient

from workbench import ai_operations, research
from workbench.app import create_app
from workbench.core import Store
from workbench.opportunity import create_opportunity
from workbench.providers import TestProvider
from workbench.search_provider import SearchProviderError, TavilySearchProvider
from workbench.secret_store import MemorySecretStore


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}
PRIVATE_MARKER = "SYNTHETIC-PRIVATE-JD-MUST-NOT-LEAVE"


class CountingFakeSearchProvider:
    def __init__(self, *, results=None, error=None, entered=None, release=None):
        self.calls = []
        self.results = results if results is not None else [{
            "title": "虚构公开招聘页面",
            "url": "https://example.test/careers",
            "snippet": "仅供测试的公开页面摘要。",
            "source": {"provider": "fake-tavily"},
        }]
        self.error = error
        self.entered = entered
        self.release = release

    def search(self, query):
        self.calls.append(query)
        if self.entered:
            self.entered.set()
        if self.release:
            assert self.release.wait(5)
        if self.error:
            raise self.error
        return self.results


class CountingModelProvider(TestProvider):
    def __init__(self):
        super().__init__()
        self.call_count = 0

    def complete(self, payload):
        self.call_count += 1
        return super().complete(payload)


def client_for(tmp_path, monkeypatch, search_provider, model_provider=None, secret_store=None):
    monkeypatch.setenv("CAREER_AI_MODE", "AI_ENABLED")
    store = Store(
        tmp_path / "data",
        model_provider or CountingModelProvider(),
        secret_store or MemorySecretStore(),
        search_provider=search_provider,
    )
    return TestClient(create_app(store), headers=HEADERS), store


def make_opportunity(store, key="research-search"):
    return create_opportunity(store, {
        "company_name": "CUTOVER-RESEARCH-TEST 虚构星河科技",
        "title": "AI 产品经理",
        "jd": f"{PRIVATE_MARKER} 只用于隔离测试的完整岗位说明。",
        "idempotency_key": "create-" + key,
    })


def initial_preview(client, opportunity_id, key):
    path = f"/api/opportunities/{opportunity_id}/research/update"
    response = client.post(path, json={"idempotency_key": key})
    assert response.status_code == 409
    return path, response.json()


def search_confirm(client, path, key):
    return client.post(path, json={"idempotency_key": key, "search_confirmed": True})


def test_search_preview_is_public_query_only_and_confirm_dispatches_once(tmp_path, monkeypatch):
    search = CountingFakeSearchProvider()
    model = CountingModelProvider()
    client, store = client_for(tmp_path, monkeypatch, search, model)
    opportunity = make_opportunity(store)

    path, preview = initial_preview(client, opportunity["id"], "search-once")
    assert preview["status"] == "search_confirmation_required"
    assert preview["provider"] == "tavily"
    assert preview["destination"] == "https://api.tavily.com/search"
    assert preview["fields"] == ["query"]
    assert preview["query"] == "CUTOVER-RESEARCH-TEST 虚构星河科技 AI 产品经理 产品 商业模式 最新动态"
    assert search.calls == []
    assert model.call_count == 0

    prepared = search_confirm(client, path, "search-once")
    assert prepared.status_code == 409, prepared.text
    assert prepared.json()["status"] == "context_confirmation_required"
    assert search.calls == [preview["query"]]
    assert PRIVATE_MARKER not in search.calls[0]
    assert model.call_count == 0

    repeated = search_confirm(client, path, "search-once")
    assert repeated.status_code == 409
    assert repeated.json()["prepared_id"] == prepared.json()["prepared_id"]
    assert search.calls == [preview["query"]]


def test_research_search_result_stays_a_lead_until_user_confirmation(tmp_path, monkeypatch):
    search = CountingFakeSearchProvider()
    model = CountingModelProvider()
    client, store = client_for(tmp_path, monkeypatch, search, model)
    opportunity = make_opportunity(store, "lead-only")
    path, preview = initial_preview(client, opportunity["id"], "lead-only")
    prepared = search_confirm(client, path, "lead-only").json()

    result = client.post(path, json={
        "idempotency_key": "lead-only",
        "search_confirmed": True,
        "prepared_id": prepared["prepared_id"],
        "payload_hash": prepared["payload_hash"],
        "confirm_outbound": True,
    })
    assert result.status_code == 200, result.text
    assert model.call_count == 1
    proposal = result.json()
    items = proposal["company_items"] + proposal["opportunity_items"]
    assert items
    assert all(item["evidence_status"] == "lead" for item in items)
    assert all(item["verification"]["user_confirmed"] is False for item in items)
    overview = client.get(f"/api/opportunities/{opportunity['id']}/research-overview").json()
    assert overview["items"] == []

    accepted = client.post(
        f"/api/opportunities/{opportunity['id']}/research-proposals/{proposal['id']}/resolve",
        json={"decision": "accept"},
    )
    assert accepted.status_code == 200, accepted.text
    overview = client.get(f"/api/opportunities/{opportunity['id']}/research-overview").json()
    assert overview["items"]
    assert all(item["evidence_status"] == "lead" for item in overview["items"])
    assert all(item["verification"]["user_confirmed"] is False for item in overview["items"])

    item = overview["items"][0]
    confirmed = client.put(
        f"/api/opportunities/{opportunity['id']}/research/items/{item['id']}",
        json={
            "scope": "opportunity",
            "category": item["category"],
            "classification": "fact",
            "content": "用户核对后的虚构公开岗位摘录",
            "evidence_status": "user_confirmed",
            "evidence": [{
                "source_id": "user-excerpt-cutover-search",
                "source_type": "user_provided_excerpt",
                "input_method": "user_pasted",
                "observed_on": "2026-09-23",
                "scope": "opportunity",
                "owner_id": opportunity["id"],
                "excerpt": "用户从虚构公开页面复制并核对的摘录。",
            }],
            "verification": {"user_confirmed": True, "independently_verified": False},
            "source_refs": item["source_refs"],
            "expected_revision": overview["opportunity"]["revision"],
            "idempotency_key": "user-confirm-search-result-excerpt",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["items"][0]["evidence_status"] == "user_confirmed"
    assert confirmed.json()["items"][0]["verification"]["user_confirmed"] is True
    assert confirmed.json()["items"][0]["source_refs"]
    assert search.calls == [preview["query"]]


def test_search_result_replays_after_restart_without_second_provider_call(tmp_path, monkeypatch):
    search = CountingFakeSearchProvider()
    client, store = client_for(tmp_path, monkeypatch, search)
    opportunity = make_opportunity(store, "restart")
    path, _ = initial_preview(client, opportunity["id"], "restart-search")
    first = search_confirm(client, path, "restart-search")
    assert first.status_code == 409
    assert len(search.calls) == 1
    data_dir = store.data_dir

    monkeypatch.setattr(research, "_VOLATILE_RESEARCH_PREPARATIONS", {})
    monkeypatch.setattr(ai_operations, "_VOLATILE_RESULTS", {})
    restarted = Store(
        data_dir,
        CountingModelProvider(),
        MemorySecretStore(),
        search_provider=search,
    )
    restarted_client = TestClient(create_app(restarted), headers=HEADERS)
    second = search_confirm(restarted_client, path, "restart-search")
    assert second.status_code == 409, second.text
    assert second.json()["status"] == "context_confirmation_required"
    assert len(search.calls) == 1


def test_concurrent_duplicate_confirm_runs_search_once(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    search = CountingFakeSearchProvider(entered=entered, release=release)
    client, store = client_for(tmp_path, monkeypatch, search)
    opportunity = make_opportunity(store, "concurrent")
    path, _ = initial_preview(client, opportunity["id"], "concurrent-search")
    request = {"idempotency_key": "concurrent-search", "search_confirmed": True}

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, path, json=request)
        assert entered.wait(3)
        second = pool.submit(client.post, path, json=request)
        concurrent = second.result(timeout=3)
        release.set()
        completed = first.result(timeout=5)

    assert concurrent.status_code in {202, 409}
    assert completed.status_code == 409
    assert len(search.calls) == 1


def test_search_provider_error_is_classified_and_same_key_is_not_retried(tmp_path, monkeypatch):
    search = CountingFakeSearchProvider(error=SearchProviderError("rate_limited"))
    client, store = client_for(tmp_path, monkeypatch, search)
    opportunity = make_opportunity(store, "rate-limit")
    path, _ = initial_preview(client, opportunity["id"], "rate-limited-search")

    first = search_confirm(client, path, "rate-limited-search")
    second = search_confirm(client, path, "rate-limited-search")
    assert first.status_code == 422
    assert first.json()["code"] == "rate_limited"
    assert second.status_code == 503
    assert second.json()["code"] == "rate_limited"
    assert len(search.calls) == 1


def test_search_timeout_is_outcome_unknown_and_never_replayed(tmp_path, monkeypatch):
    search = CountingFakeSearchProvider(error=SearchProviderError("timeout", outcome_unknown=True))
    client, store = client_for(tmp_path, monkeypatch, search)
    opportunity = make_opportunity(store, "timeout")
    path, _ = initial_preview(client, opportunity["id"], "timeout-search")

    first = search_confirm(client, path, "timeout-search")
    second = search_confirm(client, path, "timeout-search")
    assert first.status_code == 409 and first.json()["status"] == "outcome_unknown"
    assert second.status_code == 409 and second.json()["state"] == "outcome_unknown"
    assert len(search.calls) == 1


def test_local_only_cannot_search_even_after_secret_maintenance_is_available(tmp_path, monkeypatch):
    class TrackedSecrets(MemorySecretStore):
        def __init__(self):
            super().__init__()
            self.get_refs = []

        def get(self, ref):
            self.get_refs.append(ref)
            return super().get(ref)

    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    secrets = TrackedSecrets()
    search = CountingFakeSearchProvider()
    store = Store(tmp_path / "data", TestProvider(), secrets, search_provider=search)
    client = TestClient(create_app(store), headers=HEADERS)
    opportunity = make_opportunity(store, "local-only")
    path, _ = initial_preview(client, opportunity["id"], "local-only-search")

    response = search_confirm(client, path, "local-only-search")

    assert response.status_code == 503
    assert response.json()["code"] == "local_only_disabled"
    assert search.calls == []
    assert secrets.get_refs == []
    with store.connect(False) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ai_operations").fetchone()[0] == 0


def test_configured_tavily_search_uses_fake_key_and_network_trap_once(tmp_path, monkeypatch):
    class TrackedSecrets(MemorySecretStore):
        def __init__(self):
            super().__init__()
            self.get_refs = []

        def get(self, ref):
            self.get_refs.append(ref)
            return super().get(ref)

    secret_store = TrackedSecrets()
    model = CountingModelProvider()
    monkeypatch.setenv("CAREER_AI_MODE", "AI_ENABLED")
    store = Store(
        tmp_path / "data", model, secret_store,
    )
    app = create_app(store)
    client = TestClient(app, headers=HEADERS)
    fake_key = "fake-tv-key-7"
    configured = client.put("/api/research/search-provider", json={"api_key": fake_key, "expected_revision": 0})
    assert configured.status_code == 200, configured.text
    config_body = configured.json()
    assert "api_key" not in configured.text and "secret_ref" not in configured.text
    expected_ref = next(iter(secret_store.values))
    assert secret_store.get_refs == [expected_ref]

    requests = []

    def network_trap(request):
        requests.append(request)
        return httpx.Response(200, json={"results": [{
            "title": "虚构公开来源", "url": "https://example.test/open", "content": "公开摘要",
        }]})

    monkeypatch.setattr(
        research, "TavilySearchProvider",
        lambda key: TavilySearchProvider(key, transport=httpx.MockTransport(network_trap)),
    )
    opportunity = make_opportunity(store, "network-trap")
    path, preview = initial_preview(client, opportunity["id"], "real-adapter-fake-transport")
    assert requests == []
    assert secret_store.get_refs == [expected_ref]
    prepared = search_confirm(client, path, "real-adapter-fake-transport")

    assert prepared.status_code == 409, prepared.text
    assert len(requests) == 1
    assert requests[0].url == "https://api.tavily.com/search"
    assert requests[0].headers["Authorization"] == f"Bearer {fake_key}"
    assert PRIVATE_MARKER not in requests[0].content.decode()
    assert json_loads(requests[0].content)["query"] == preview["query"]
    assert secret_store.get_refs == [expected_ref, expected_ref]
    assert model.call_count == 0
    assert fake_key not in prepared.text
    with store.connect(False) as connection:
        persisted = "\n".join(row[0] for row in connection.execute("SELECT body FROM current"))
        persisted += "\n" + "\n".join(row[0] for row in connection.execute("SELECT body FROM records"))
    assert fake_key not in persisted
    assert fake_key.encode() not in store.db.read_bytes()


def json_loads(value):
    return json.loads(value)
