"""T03 AI operation deduplication and conservative recovery over fake providers."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.model_gateway import GatewayError
from workbench.opportunity import create_opportunity
from workbench.providers import TestProvider
from workbench import ai_operations
from workbench.research import update as research_update


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


class CountingFakeProvider(TestProvider):
    """A deterministic fake that counts actual provider.complete calls."""

    def __init__(self, *, delay=0, entered=None, release=None, error=None):
        self.call_count = 0
        self.call_numbers = []
        self.lock = threading.Lock()
        self.delay = delay
        self.entered = entered
        self.release = release
        self.error = error

    def complete(self, payload):
        with self.lock:
            self.call_count += 1
            number = self.call_count
            self.call_numbers.append(number)
        if self.entered:
            self.entered.set()
        if self.release:
            assert self.release.wait(5)
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        result = super().complete(payload)
        packet = json.loads(payload["messages"][1]["content"])
        task = packet.get("task_type")
        if task == "research_update":
            result["company_items"][0]["content"] = f"假供应商 Research 第 {number} 次"
            result["opportunity_items"][0]["content"] = f"假供应商岗位研究第 {number} 次"
        elif task == "interview_final_review":
            result["summary"] = f"假供应商 Final Review 第 {number} 次"
        elif task == "interview_research_patch":
            result["items"][0]["content"] = f"假供应商 Patch 第 {number} 次"
        elif task == "resume_optimization":
            result["suggestions"] = [f"假供应商 Resume 第 {number} 次"]
        elif task == "legacy_analysis":
            if packet.get("taskKind") == "resume":
                result["draft"] = f"假供应商 legacy Resume 第 {number} 次"
            else:
                result["core_goal"] = f"假供应商 legacy Analysis 第 {number} 次"
        return result


def client_for(tmp_path, provider=None):
    store = Store(tmp_path / "data", provider or CountingFakeProvider())
    return TestClient(create_app(store), headers=HEADERS), store


def opportunity_for(store, key="op"):
    return create_opportunity(store, {
        "company_name": "T03 虚构公司 " + key,
        "title": "T03 虚构岗位",
        "jd": "只用于 T03 的假 JD",
        "idempotency_key": "create-" + key,
    })


def prepare_research(client, opportunity_id, key, *, model_config_id=None):
    body = {"idempotency_key": key}
    initial = client.post(f"/api/opportunities/{opportunity_id}/research/update", json=body)
    assert initial.status_code == 409
    searched = client.post(f"/api/opportunities/{opportunity_id}/research/update", json={
        **body, "search_confirmed": True, **({"model_config_id": model_config_id} if model_config_id else {}),
    })
    assert searched.status_code == 409, searched.text
    prepared = searched.json()
    return {**body, "search_confirmed": True, "prepared_id": prepared["prepared_id"],
            "payload_hash": prepared["payload_hash"], "confirm_outbound": True,
            **({"model_config_id": model_config_id} if model_config_id else {})}


def prepare_analysis(client, job_id, key, *, kind="job"):
    body = {"job_id": job_id, "kind": kind, "idempotency_key": key}
    prepared_response = client.post("/api/analysis", json=body)
    assert prepared_response.status_code == 409, prepared_response.text
    prepared = prepared_response.json()
    return {**body, "prepared_id": prepared["prepared_id"],
            "payload_hash": prepared["payload_hash"], "confirm_outbound": True}


def prepare_final_review(client, opportunity_id, interview_id, key):
    body = {"communication_ids": [], "wiki_ids": [], "idempotency_key": key}
    response = client.post(
        f"/api/opportunities/{opportunity_id}/interviews/{interview_id}/generate-final-review", json=body
    )
    assert response.status_code == 409, response.text
    prepared = response.json()
    return {**body, "prepared_id": prepared["prepared_id"],
            "payload_hash": prepared["payload_hash"], "confirm_outbound": True}


def test_all_generation_paths_deduplicate_before_provider_and_reject_different_input(tmp_path, monkeypatch):
    provider = CountingFakeProvider()
    client, store = client_for(tmp_path, provider)
    opportunity = opportunity_for(store, "all-paths")
    search_calls = []
    monkeypatch.setattr("workbench.research.web_search", lambda *args: [{
        "url": "https://example.test/t03", "title": "假来源",
        "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])
    original_search = __import__("workbench.research", fromlist=["web_search"]).web_search
    monkeypatch.setattr("workbench.research.web_search", lambda *args: (search_calls.append(args) or original_search(*args)))

    research_body = prepare_research(client, opportunity['id'], "same-research")
    first = client.post(f"/api/opportunities/{opportunity['id']}/research/update", json=research_body)
    second = client.post(f"/api/opportunities/{opportunity['id']}/research/update", json=research_body)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert client.post(f"/api/opportunities/{opportunity['id']}/research/update", json={
        **research_body, "model_config_id": "different-input",
    }).status_code == 409
    assert provider.call_count == 1

    started = client.post(f"/api/opportunities/{opportunity['id']}/resume/start", json={
        "expected_opportunity_revision": opportunity["revision"],
        "idempotency_key": "resume-start", "source": {"kind": "blank"},
    }).json()
    resume_seed = {"instruction": "假 Resume 指令", "idempotency_key": "same-resume"}
    prepared_resume = client.post(f"/api/resume-documents/{started['document_id']}/ai-suggest", json=resume_seed)
    assert prepared_resume.status_code == 409
    resume_body = {**resume_seed, **{k: prepared_resume.json()[k] for k in ("prepared_id", "payload_hash")}, "confirm_outbound": True}
    first_resume = client.post(f"/api/resume-documents/{started['document_id']}/ai-suggest", json=resume_body)
    second_resume = client.post(f"/api/resume-documents/{started['document_id']}/ai-suggest", json=resume_body)
    assert first_resume.status_code == second_resume.status_code == 200
    assert first_resume.json() == second_resume.json()
    assert client.post(f"/api/resume-documents/{started['document_id']}/ai-suggest", json={
        **resume_body, "instruction": "不同实质输入",
    }).status_code == 409
    assert provider.call_count == 2

    submitted = client.post(f"/api/opportunities/{opportunity['id']}/submitted", json={
        "expected_revision": opportunity["revision"], "idempotency_key": "submit",
        "resume": {"mode": "none"},
    }).json()["opportunity"]
    interview = client.post(f"/api/opportunities/{submitted['id']}/interviews/real", json={
        "name": "T03 一面", "expected_opportunity_revision": submitted["revision"],
        "idempotency_key": "confirm",
    }).json()["interview"]
    raw = client.put(f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/raw", json={
        "content": "假面试 Raw", "expected_revision": 0, "idempotency_key": "raw",
    })
    assert raw.status_code == 200
    review_body = prepare_final_review(client, submitted['id'], interview['id'], "same-review")
    first_review = client.post(f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/generate-final-review", json=review_body)
    second_review = client.post(f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/generate-final-review", json=review_body)
    assert first_review.status_code == second_review.status_code == 200
    assert first_review.json() == second_review.json()

    patch_seed = {"communication_ids": [], "wiki_ids": [], "idempotency_key": "same-patch"}
    patch_prepared = client.post(f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/generate-research-patch", json=patch_seed)
    assert patch_prepared.status_code == 409
    patch_body = {**patch_seed, **{k: patch_prepared.json()[k] for k in ("prepared_id", "payload_hash")}, "confirm_outbound": True}
    first_patch = client.post(f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/generate-research-patch", json=patch_body)
    second_patch = client.post(f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/generate-research-patch", json=patch_body)
    assert first_patch.status_code == second_patch.status_code == 200
    assert first_patch.json() == second_patch.json()
    assert provider.call_count == 4
    assert len(search_calls) == 1
    with store.connect(False) as connection:
        operations = connection.execute("SELECT task_type,state,dispatched_payload_hash FROM ai_operations ORDER BY rowid").fetchall()
    assert [row[0] for row in operations] == [
        "research_update", "resume_optimization", "interview_final_review", "interview_research_patch"
    ]
    assert all(row[1] == "succeeded" and row[2] for row in operations)


def test_serial_duplicate_five_times_calls_provider_once(tmp_path, monkeypatch):
    provider = CountingFakeProvider()
    client, store = client_for(tmp_path, provider)
    opportunity = opportunity_for(store, "serial-five")
    monkeypatch.setattr("workbench.research.web_search", lambda *args: [{
        "url": "https://example.test/serial-five", "title": "假来源", "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])
    body = prepare_research(client, opportunity['id'], "serial-five-key")

    responses = [client.post(f"/api/opportunities/{opportunity['id']}/research/update", json=body)
                 for _ in range(5)]

    assert [response.status_code for response in responses] == [200] * 5
    assert all(response.json() == responses[0].json() for response in responses)
    assert provider.call_count == 1
    assert provider.call_numbers == [1]


def test_concurrent_duplicate_five_times_calls_provider_once(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    duplicates_entered = threading.Event()
    duplicate_count = 0
    duplicate_lock = threading.Lock()
    provider = CountingFakeProvider(entered=entered, release=release)
    client, store = client_for(tmp_path, provider)
    opportunity = opportunity_for(store, "concurrent")
    monkeypatch.setattr("workbench.research.web_search", lambda *args: [{
        "url": "https://example.test/concurrent", "title": "假来源", "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])
    body = prepare_research(client, opportunity['id'], "concurrent-key")

    original_existing = ai_operations._existing

    def observe_existing(operation_store, row, intent_hash):
        nonlocal duplicate_count
        result = original_existing(operation_store, row, intent_hash)
        with duplicate_lock:
            duplicate_count += 1
            if duplicate_count == 4:
                duplicates_entered.set()
        return result

    monkeypatch.setattr(ai_operations, "_existing", observe_existing)

    def send():
        return research_update(store, opportunity["id"], body)

    def payload(response):
        if hasattr(response, "body"):
            return json.loads(response.body)
        return response

    with ThreadPoolExecutor(max_workers=5) as pool:
        first = pool.submit(send)
        assert entered.wait(5)
        rest = [pool.submit(send) for _ in range(4)]
        assert duplicates_entered.wait(5)
        release.set()
        first_response = first.result(timeout=5)
        rest_responses = [future.result(timeout=5) for future in rest]
    assert provider.call_count == 1
    assert duplicate_count == 4
    responses = [first_response, *rest_responses]
    assert {payload(response).get("operation_id") for response in responses} == {
        payload(first_response).get("operation_id")
    }
    assert provider.call_numbers == [1]


def test_running_operation_is_visible_and_never_recharged(tmp_path):
    entered, release = threading.Event(), threading.Event()
    provider = CountingFakeProvider(entered=entered, release=release)
    client, store = client_for(tmp_path, provider)
    opportunity = opportunity_for(store, "running")
    store.save_profile("T03 legacy 假候选人资料", 0)
    legacy_job = store.save_job({
        "company": "T03 legacy 虚构公司", "title": "T03 legacy 虚构岗位",
        "jd": "仅用于 legacy analysis 的假 JD", "url": "https://example.test/job",
        "idempotency_key": "legacy-running-job",
    })
    request = prepare_analysis(client, legacy_job["id"], "running-key")

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(client.post, "/api/analysis", json=request)
        assert entered.wait(5)
        running = client.post("/api/analysis", json=request)
        assert running.status_code == 202
        assert running.json()["status"] == "running"
        release.set()
        completed = first.result(timeout=5)
    assert completed.status_code == 200
    assert provider.call_count == 1


def test_timeout_becomes_outcome_unknown_and_same_key_does_not_retry(tmp_path, monkeypatch):
    provider = CountingFakeProvider(error=GatewayError("timeout", "synthetic timeout"))
    client, store = client_for(tmp_path, provider)
    opportunity = opportunity_for(store, "timeout")
    monkeypatch.setattr("workbench.research.web_search", lambda *args: [{
        "url": "https://example.test/timeout", "title": "假来源", "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])
    body = prepare_research(client, opportunity['id'], "timeout-key")
    first = client.post(f"/api/opportunities/{opportunity['id']}/research/update", json=body)
    second = client.post(f"/api/opportunities/{opportunity['id']}/research/update", json=body)
    assert first.status_code == 503
    assert second.status_code == 409
    assert second.json()["status"] == "outcome_unknown"
    assert provider.call_count == 1
    with store.connect(False) as connection:
        assert connection.execute("SELECT state,error_code FROM ai_operations").fetchone() == ("outcome_unknown", "timeout")


def test_succeeded_replay_after_restart_does_not_recharge(tmp_path, monkeypatch):
    provider = CountingFakeProvider()
    client, store = client_for(tmp_path, provider)
    opportunity = opportunity_for(store, "succeeded-restart")
    monkeypatch.setattr("workbench.research.web_search", lambda *args: [{
        "url": "https://example.test/succeeded-restart", "title": "假来源", "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])
    body = prepare_research(client, opportunity['id'], "succeeded-restart-key")
    first = client.post(f"/api/opportunities/{opportunity['id']}/research/update", json=body)
    assert first.status_code == 200
    assert provider.call_count == 1

    ai_operations._VOLATILE_RESULTS.clear()
    restarted_store = Store(tmp_path / "data", provider)
    restarted_client = TestClient(create_app(restarted_store), headers=HEADERS)
    replay = restarted_client.post(f"/api/opportunities/{opportunity['id']}/research/update", json=body)

    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert provider.call_count == 1
    assert provider.call_numbers == [1]


def test_successful_provider_then_persistence_failure_is_unknown_after_restart(tmp_path, monkeypatch):
    provider = CountingFakeProvider()
    client, store = client_for(tmp_path, provider)
    opportunity = opportunity_for(store, "persist-failure")
    monkeypatch.setattr("workbench.research.web_search", lambda *args: [{
        "url": "https://example.test/persist", "title": "假来源", "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])
    original_record = store._record

    def fail_proposal(connection, kind, obj):
        if kind == "research_proposal":
            raise RuntimeError("synthetic proposal persistence failure")
        return original_record(connection, kind, obj)

    body = prepare_research(client, opportunity['id'], "persist-key")
    monkeypatch.setattr(store, "_record", fail_proposal)
    with pytest.raises(RuntimeError):
        client.post(f"/api/opportunities/{opportunity['id']}/research/update", json=body)
    assert provider.call_count == 1
    with store.connect(False) as connection:
        state = connection.execute("SELECT state,error_code FROM ai_operations").fetchone()
    assert state == ("outcome_unknown", "persistence_unknown")

    restarted_store = Store(tmp_path / "data", provider)
    restarted_client = TestClient(create_app(restarted_store), headers=HEADERS)
    replay = restarted_client.post(f"/api/opportunities/{opportunity['id']}/research/update", json=body)
    assert replay.status_code == 409 and replay.json()["status"] == "outcome_unknown"
    assert provider.call_count == 1


def test_restart_marks_dispatching_unknown_without_provider_call(tmp_path):
    provider = CountingFakeProvider()
    client, store = client_for(tmp_path, provider)
    opportunity = opportunity_for(store, "restart-marker")
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO ai_operations(
                op_id,task_type,target_kind,target_id,idempotency_key,client_intent_hash,
                state,dispatch_marker,created_at,reserved_at,dispatched_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            ("ai-operation:synthetic-dispatching", "research_update", "opportunity", opportunity["id"],
             "restart-key", "synthetic-intent", "dispatching", "synthetic-marker",
             "2026-09-19T00:00:00+00:00", "2026-09-19T00:00:00+00:00", "2026-09-19T00:00:00+00:00"),
        )
    restarted_store = Store(tmp_path / "data", provider)
    with restarted_store.connect(False) as connection:
        assert connection.execute("SELECT state,error_code FROM ai_operations WHERE op_id=?", ("ai-operation:synthetic-dispatching",)).fetchone() == (
            "outcome_unknown", "process_interrupted"
        )
    assert provider.call_count == 0


def test_busy_outbound_slot_fails_before_second_provider_call(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    provider = CountingFakeProvider(entered=entered, release=release)
    client, store = client_for(tmp_path, provider)
    opportunity = opportunity_for(store, "busy")
    monkeypatch.setattr("workbench.research.web_search", lambda *args: [{
        "url": "https://example.test/busy", "title": "假来源", "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])

    with ThreadPoolExecutor(max_workers=1) as pool:
        first_body = prepare_research(client, opportunity['id'], "busy-first")
        first = pool.submit(client.post, f"/api/opportunities/{opportunity['id']}/research/update",
                            json=first_body)
        assert entered.wait(5)
        second_body = prepare_research(client, opportunity['id'], "busy-second")
        second = client.post(f"/api/opportunities/{opportunity['id']}/research/update",
                             json=second_body)
        assert second.status_code == 429
        assert second.json()["status"] == "failed"
        release.set()
        assert first.result(timeout=5).status_code == 200
    assert provider.call_count == 1
    with store.connect(False) as connection:
        assert connection.execute(
            "SELECT state,error_code FROM ai_operations WHERE idempotency_key=?",
            ("busy-second",),
        ).fetchone() == ("failed", "busy")


def test_empty_research_stops_before_model_and_marks_failed(tmp_path, monkeypatch):
    provider = CountingFakeProvider()
    client, store = client_for(tmp_path, provider)
    opportunity = opportunity_for(store, "empty-search")
    monkeypatch.setattr("workbench.research.web_search", lambda *args: [])

    initial = client.post(f"/api/opportunities/{opportunity['id']}/research/update",
                          json={"idempotency_key": "empty-search-key"})
    assert initial.status_code == 409
    response = client.post(f"/api/opportunities/{opportunity['id']}/research/update",
                           json={"idempotency_key": "empty-search-key", "search_confirmed": True})
    assert response.status_code == 422
    assert provider.call_count == 0
    with store.connect(False) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ai_operations").fetchone()[0] == 0


def test_final_review_result_is_unknown_after_restart_without_recharge(tmp_path):
    provider = CountingFakeProvider()
    client, store = client_for(tmp_path, provider)
    opportunity = opportunity_for(store, "review-restart")
    submitted = client.post(f"/api/opportunities/{opportunity['id']}/submitted", json={
        "expected_revision": opportunity["revision"], "idempotency_key": "submit-review-restart",
        "resume": {"mode": "none"},
    }).json()["opportunity"]
    interview = client.post(f"/api/opportunities/{submitted['id']}/interviews/real", json={
        "name": "T03 重启复盘", "expected_opportunity_revision": submitted["revision"],
        "idempotency_key": "confirm-review-restart",
    }).json()["interview"]
    assert client.put(f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/raw", json={
        "content": "假 Raw", "expected_revision": 0, "idempotency_key": "raw-review-restart",
    }).status_code == 200
    body = prepare_final_review(client, submitted['id'], interview['id'], "review-restart-key")
    assert client.post(f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/generate-final-review",
                       json=body).status_code == 200
    assert provider.call_count == 1

    ai_operations._VOLATILE_RESULTS.clear()
    restarted_store = Store(tmp_path / "data", provider)
    restarted_client = TestClient(create_app(restarted_store), headers=HEADERS)
    replay = restarted_client.post(
        f"/api/opportunities/{submitted['id']}/interviews/{interview['id']}/generate-final-review",
        json=body,
    )
    assert replay.status_code == 409
    assert replay.json()["status"] == "outcome_unknown"
    assert provider.call_count == 1
