from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from workbench.core import Conflict, Invalid, Missing, Store
from workbench.journey import journey_router
from workbench.providers import TestProvider


def make_client(tmp_path):
    store = Store(tmp_path, TestProvider())
    app = FastAPI()
    for cls, code in ((Invalid, 422), (Conflict, 409), (Missing, 404)):
        async def handle(request, exc, status=code):
            return JSONResponse({"detail": str(exc)}, status_code=status)
        app.add_exception_handler(cls, handle)
    app.include_router(journey_router(store))
    return TestClient(app), store


def add_job(store, company="Acme"):
    return store.save_job({"company": company, "title": "工程师", "jd": "JD"})


def test_plan_is_scoped_to_active_job_and_uses_revision_cas(tmp_path):
    client, store = make_client(tmp_path)
    first = add_job(store)
    second = add_job(store, "Beta")
    response = client.post(
        f"/api/journey/plans/{first['id']}",
        json={"stage": "research", "next_action": "查资料", "due_date": "2026-09-20", "expected_revision": 0},
    )
    assert response.status_code == 200
    plan = response.json()
    assert plan["id"] == f"journey:{first['id']}" and plan["revision"] == 1
    assert client.get("/api/journey").json()["plans"] == [plan]
    assert client.post(
        f"/api/journey/plans/{first['id']}",
        json={"stage": "offer", "next_action": "接受", "due_date": None, "expected_revision": 0},
    ).status_code == 409
    assert client.post(
        f"/api/journey/plans/{second['id']}",
        json={"stage": "applied", "next_action": "跟进", "due_date": "2026-09-21", "expected_revision": 0},
    ).status_code == 200
    missing = client.post(
        "/api/journey/plans/missing",
        json={"stage": "research", "next_action": "x", "due_date": None, "expected_revision": 0},
    )
    assert missing.status_code == 404
    store.save_job({"company": "Acme", "title": "工程师", "jd": "JD", "status": "excluded", "expected_revision": first["revision"]}, first["id"])
    assert client.post(f"/api/journey/plans/{first['id']}", json={"stage": "closed", "next_action": "x", "due_date": None, "expected_revision": plan["revision"]}).status_code == 404


def test_invalid_collection_values_are_422(tmp_path):
    client, store = make_client(tmp_path)
    job = add_job(store)
    for payload in ({"stage": [], "next_action": "x", "due_date": None, "expected_revision": 0},
                    {"stage": "research", "next_action": "x", "due_date": None, "expected_revision": 0}):
        if payload["stage"] == "research":
            payload["stage"] = {"bad": 1}
        assert client.post(f"/api/journey/plans/{job['id']}", json=payload).status_code == 422
    assert client.post("/api/journey/notes", json={"scope_type": [], "scope_id": job["id"], "kind": "research", "title": "", "content": "x", "idempotency_key": "t1"}).status_code == 422
    assert client.post("/api/journey/notes", json={"scope_type": "job", "scope_id": job["id"], "kind": {}, "title": "", "content": "x", "idempotency_key": "t2"}).status_code == 422


def test_episode_dates_and_endpoint_reference_are_validated(tmp_path):
    client, store = make_client(tmp_path)
    created = client.post("/api/journey/episodes", json={"company": "Acme", "role": "工程师", "start_date": "2026-09-20", "end_date": "2026-09-19", "focus": "x"})
    assert created.status_code == 422
    created = client.post("/api/journey/episodes", json={"company": "Acme", "role": "工程师", "start_date": "2026-02-30", "end_date": None, "focus": "x"})
    assert created.status_code == 422
    created = client.post("/api/journey/episodes", json={"company": "Acme", "role": "工程师", "start_date": None, "end_date": None, "focus": "x"})
    assert created.status_code == 200
    episode = created.json()
    assert episode["revision"] == 0
    assert client.post(f"/api/journey/episodes/{episode['id']}", json={"company": "Acme", "role": "新角色", "start_date": None, "end_date": None, "focus": "y", "expected_revision": 0}).status_code == 200
    assert client.post(f"/api/journey/episodes/{episode['id']}", json={"company": "Acme", "role": "x", "start_date": None, "end_date": None, "focus": "z", "expected_revision": 0}).status_code == 409
    assert client.post("/api/journey/episodes/missing", json={"company": "Acme", "role": "x", "start_date": None, "end_date": None, "focus": "z", "expected_revision": 0}).status_code == 404


def test_notes_are_immutable_and_idempotent_inside_persistent_store(tmp_path):
    client, store = make_client(tmp_path)
    job = add_job(store)
    body = {"scope_type": "job", "scope_id": job["id"], "kind": "research", "title": " 原话 ", "content": "  保留空白  ", "idempotency_key": "note-1"}
    first = client.post("/api/journey/notes", json=body)
    assert first.status_code == 200 and first.json()["content"] == body["content"]
    assert client.post("/api/journey/notes", json=body).json() == first.json()
    changed = dict(body, content="changed")
    assert client.post("/api/journey/notes", json=changed).status_code == 409
    assert client.post("/api/journey/notes", json=dict(body, scope_id="missing", idempotency_key="note-2")).status_code == 404
    reopened = Store(tmp_path, TestProvider())
    app = FastAPI(); app.include_router(journey_router(reopened))
    assert app is not None
    assert TestClient(app).get("/api/journey").json()["notes"] == [first.json()]
    reopened.save_profile("当前资料", 0)
    assert "保留空白" not in reopened.context(job["id"], "job")["sources"][0]["content"]


def test_get_journey_is_read_only_and_context_excludes_journey_records(tmp_path):
    client, store = make_client(tmp_path)
    job = add_job(store)
    store.save_profile("旧资料 sentinel-profile-old", 0)
    before = store.db.read_bytes()
    episode = client.post("/api/journey/episodes", json={"company": "公司", "role": "角色", "focus": "sentinel-episode"}).json()
    note_payloads = [
        {"scope_type": "job", "scope_id": job["id"], "kind": "research", "title": "研究", "content": "sentinel-job-note", "idempotency_key": "isolate-job"},
        {"scope_type": "episode", "scope_id": episode["id"], "kind": "collaboration", "title": "协作", "content": "sentinel-collaboration", "idempotency_key": "isolate-episode"},
    ]
    for payload in note_payloads:
        assert client.post("/api/journey/notes", json=payload).status_code == 200
    first_run = store.analyze(job["id"], "job", idempotency_key="context-1")
    first_payload = json.dumps(first_run["payload"], ensure_ascii=False)
    assert all(sentinel not in first_payload for sentinel in ("sentinel-episode", "sentinel-job-note", "sentinel-collaboration"))
    store.save_profile("新资料 sentinel-profile-new", 1)
    second_run = store.analyze(job["id"], "job", idempotency_key="context-2")
    second_payload = json.dumps(second_run["payload"], ensure_ascii=False)
    assert "sentinel-profile-old" not in second_payload and "sentinel-profile-new" in second_payload
    after = store.db.read_bytes()
    assert client.get("/api/journey").status_code == 200
    assert store.db.read_bytes() == after
    assert before != after


def test_same_note_key_concurrent_requests_create_one_record(tmp_path):
    client, store = make_client(tmp_path)
    job = add_job(store)
    body = {"scope_type": "job", "scope_id": job["id"], "kind": "research", "title": "并发", "content": "原话", "idempotency_key": "concurrent-note"}
    def submit(_):
        return client.post("/api/journey/notes", json=body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert len({r.json()["id"] for r in responses}) == 1
    assert len([n for n in client.get("/api/journey").json()["notes"] if n["idempotency_key"] == body["idempotency_key"]]) == 1
import json
from concurrent.futures import ThreadPoolExecutor
