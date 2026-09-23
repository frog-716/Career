"""T06 regression contracts for confirmation, scope, audit and budgets."""
import json
import threading

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.opportunity import create_opportunity
from workbench.providers import TestProvider
from search_fakes import FakeSearchProvider


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


class CountingFakeProvider(TestProvider):
    def __init__(self):
        self.call_count = 0
        self.lock = threading.Lock()

    def complete(self, payload):
        with self.lock:
            self.call_count += 1
            number = self.call_count
        result = super().complete(payload)
        packet = json.loads(payload["messages"][1]["content"])
        if packet.get("task_type") == "legacy_analysis":
            result["core_goal"] = f"假供应商第 {number} 次"
        return result


def client_for(tmp_path):
    provider = CountingFakeProvider()
    store = Store(tmp_path / "data", provider)
    return TestClient(create_app(store), headers=HEADERS), store, provider


def test_legacy_analysis_requires_confirmation_and_rechecks_prepared_payload(tmp_path):
    client, store, provider = client_for(tmp_path)
    store.save_profile("虚构候选人经历", 0)
    job = store.save_job({
        "company": "虚构公司",
        "title": "虚构岗位",
        "jd": "只用于 T06 的假 JD",
        "idempotency_key": "t06-job",
    })

    prepared_response = client.post("/api/analysis", json={
        "job_id": job["id"], "kind": "job", "idempotency_key": "t06-analysis",
    })
    assert prepared_response.status_code == 409
    prepared = prepared_response.json()
    assert prepared["status"] == "context_confirmation_required"
    assert provider.call_count == 0
    assert prepared["budget"]["request_bytes"] <= prepared["budget"]["request_bytes_limit"]
    preview = json.dumps(prepared["payload_preview"], ensure_ascii=False)
    assert "Authorization" not in preview
    assert "虚构候选人经历" in preview
    with store.connect(False) as connection:
        preparation_rows = store._records(connection, "ai_preparation")
        audit_rows = store._records(connection, "ai_audit")
    assert "虚构候选人经历" not in json.dumps(preparation_rows + audit_rows, ensure_ascii=False)

    store.save_profile("资料已经变化", 1)
    stale = client.post("/api/analysis", json={
        "job_id": job["id"], "kind": "job", "idempotency_key": "t06-analysis",
        "prepared_id": prepared["prepared_id"],
        "payload_hash": prepared["payload_hash"], "confirm_outbound": True,
    })
    assert stale.status_code == 409
    assert "重新预览" in stale.json()["detail"]
    assert provider.call_count == 0


def test_resume_prepare_redacts_contact_fields_before_confirmation(tmp_path):
    client, store, provider = client_for(tmp_path)
    opportunity = create_opportunity(store, {
        "company_name": "虚构简历公司", "title": "虚构简历岗位",
        "jd": "T06 假 JD", "idempotency_key": "t06-resume-op",
    })
    started = client.post(f"/api/opportunities/{opportunity['id']}/resume/start", json={
        "expected_opportunity_revision": opportunity["revision"],
        "idempotency_key": "t06-resume-start", "source": {"kind": "blank"},
    }).json()
    document = {
        "schemaVersion": 1,
        "profile": {"id": "t06-profile", "name": "虚构姓名", "contacts": [
            {"id": "t06-phone", "kind": "identity", "content": "电话：13800000000", "href": ""},
            {"id": "t06-email", "kind": "identity", "content": "邮箱：candidate@example.test", "href": ""},
        ]},
        "sections": [], "formatting": {}, "meta": {},
    }
    saved = client.put(f"/api/resume-documents/{started['document_id']}", json={
        "document": document, "expected_revision": started["revision"],
    })
    assert saved.status_code == 200, saved.text

    response = client.post(f"/api/resume-documents/{started['document_id']}/ai-suggest", json={
        "instruction": "只优化表达", "idempotency_key": "t06-resume-ai",
    })
    assert response.status_code == 409
    prepared = response.json()
    assert prepared["status"] == "context_confirmation_required"
    preview = json.dumps(prepared["payload_preview"], ensure_ascii=False)
    assert "13800000000" not in preview
    assert "candidate@example.test" not in preview
    assert provider.call_count == 0


def test_research_requires_search_confirmation_then_model_confirmation(tmp_path, monkeypatch):
    client, store, provider = client_for(tmp_path)
    opportunity = create_opportunity(store, {
        "company_name": "虚构研究公司", "title": "虚构研究岗位",
        "jd": "T06 研究 JD", "idempotency_key": "t06-research-op",
    })
    search_calls = []

    def fake_search(*args):
        search_calls.append(args)
        return [{"url": "https://example.test/t06", "title": "假来源", "retrieved_at": "2026-09-19T00:00:00+00:00"}]

    store.search_provider = FakeSearchProvider(fake_search)
    initial = client.post(f"/api/opportunities/{opportunity['id']}/research/update", json={
        "idempotency_key": "t06-research",
    })
    assert initial.status_code == 409
    assert initial.json()["status"] == "search_confirmation_required"
    assert search_calls == []
    assert provider.call_count == 0

    searched = client.post(f"/api/opportunities/{opportunity['id']}/research/update", json={
        "idempotency_key": "t06-research", "search_confirmed": True,
    })
    assert searched.status_code == 409
    prepared = searched.json()
    assert prepared["status"] == "context_confirmation_required"
    assert len(search_calls) == 1
    assert provider.call_count == 0

    searched_again = client.post(f"/api/opportunities/{opportunity['id']}/research/update", json={
        "idempotency_key": "t06-research", "search_confirmed": True,
    })
    assert searched_again.status_code == 409
    assert searched_again.json()["prepared_id"] == prepared["prepared_id"]
    assert len(search_calls) == 1
    assert provider.call_count == 0

    executed = client.post(f"/api/opportunities/{opportunity['id']}/research/update", json={
        "idempotency_key": "t06-research", "search_confirmed": True,
        "prepared_id": prepared["prepared_id"], "payload_hash": prepared["payload_hash"],
        "confirm_outbound": True,
    })
    assert executed.status_code == 200, executed.text
    assert provider.call_count == 1
    assert len(search_calls) == 1


def test_interview_ai_requires_outbound_confirmation(tmp_path):
    client, store, provider = client_for(tmp_path)
    opportunity = create_opportunity(store, {
        "company_name": "虚构面试公司", "title": "虚构面试岗位",
        "jd": "T06 面试 JD", "idempotency_key": "t06-interview-op",
    })
    submitted = client.post(f"/api/opportunities/{opportunity['id']}/submitted", json={
        "expected_revision": opportunity["revision"], "idempotency_key": "t06-interview-submit",
        "resume": {"mode": "none"},
    }).json()["opportunity"]
    interview = client.post(f"/api/opportunities/{submitted['id']}/interviews/real", json={
        "name": "T06 一面", "expected_opportunity_revision": submitted["revision"],
        "idempotency_key": "t06-interview-confirm",
    }).json()["interview"]
    assert client.put(f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/raw", json={
        "content": "虚构面试问答 Raw", "expected_revision": 0, "idempotency_key": "t06-interview-raw",
    }).status_code == 200

    body = {
        "communication_ids": [], "wiki_ids": [], "idempotency_key": "t06-final-review",
    }
    prepared_response = client.post(
        f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/generate-final-review",
        json=body,
    )
    assert prepared_response.status_code == 409
    prepared = prepared_response.json()
    assert prepared["status"] == "context_confirmation_required"
    assert provider.call_count == 0

    executed = client.post(
        f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/generate-final-review",
        json={**body, "prepared_id": prepared["prepared_id"],
              "payload_hash": prepared["payload_hash"], "confirm_outbound": True},
    )
    assert executed.status_code == 200, executed.text
    assert provider.call_count == 1
