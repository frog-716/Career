"""The old knowledge intake cannot create new facts after D1 Raw/Wiki takes over."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from workbench.core import Conflict, Invalid, Missing, Store
from workbench.knowledge import knowledge_router, selected_wiki_sources
from workbench.providers import TestProvider


def fixture(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    app = FastAPI()
    for error, code in ((Invalid, 422), (Conflict, 409), (Missing, 404)):
        async def handle(request, exc, status=code):
            return JSONResponse({"detail": str(exc)}, status_code=status)
        app.add_exception_handler(error, handle)
    app.include_router(knowledge_router(store))
    with store.connect() as connection:
        source = {
            "id": "legacy-source", "title": "旧访谈", "content": "虚构原文",
            "source_type": "text", "locator": "", "scope_type": "personal",
            "scope_id": "", "created_at": "2026-01-01T00:00:00Z",
        }
        store._record(connection, "knowledge_source", source)
        candidate = store._save(connection, "knowledge_candidate", {
            "id": "legacy-candidate", "source_ids": [source["id"]],
            "entry_type": "experience", "title": "旧候选", "content": "虚构候选",
            "scope_type": "personal", "scope_id": "", "status": "pending",
            "entry_id": None, "created_at": "2026-01-01T00:00:00Z",
        }, 0)
        entry = store._save(connection, "wiki_entry", {
            "id": "legacy-entry", "title": "已确认旧事实", "content": "虚构事实",
            "entry_type": "experience", "scope_type": "personal", "scope_id": "",
            "source_ids": [source["id"]], "status": "active",
            "verification": "user_asserted", "created_at": "2026-01-01T00:00:00Z",
        }, 0)
    return TestClient(app), store, source, candidate, entry


def fingerprint(store):
    with store.connect(False) as connection:
        return {
            "epoch": store._epoch(connection),
            "current": connection.execute(
                "SELECT id,kind,revision,body FROM current ORDER BY id").fetchall(),
            "records": connection.execute(
                "SELECT id,kind,body FROM records ORDER BY id").fetchall(),
            "revisions": connection.execute(
                "SELECT id,revision,body FROM revisions ORDER BY id,revision").fetchall(),
        }


def test_new_legacy_source_and_candidate_are_rejected_without_any_write(tmp_path):
    client, store, source, candidate, _ = fixture(tmp_path)
    before = fingerprint(store)
    attempts = [
        ("/api/knowledge/sources", {
            "title": "新旧来源", "content": "不能保存", "source_type": "text",
            "scope_type": "personal", "scope_id": "", "idempotency_key": "new-source"}),
        ("/api/knowledge/candidates", {
            "source_ids": [source["id"]], "entry_type": "experience",
            "title": "新旧候选", "content": "不能保存", "scope_type": "personal",
            "scope_id": "", "idempotency_key": "new-candidate"}),
        (f"/api/knowledge/candidates/{candidate['id']}", {
            "source_ids": [source["id"]], "entry_type": "experience",
            "title": "改写旧候选", "content": "不能保存", "scope_type": "personal",
            "scope_id": "", "expected_revision": candidate["revision"],
            "idempotency_key": "edit-candidate"}),
        (f"/api/knowledge/candidates/{candidate['id']}/resolve", {
            "decision": "confirm", "expected_revision": candidate["revision"],
            "idempotency_key": "confirm-candidate"}),
    ]
    for route, payload in attempts:
        response = client.post(route, json=payload)
        assert response.status_code == 409, (route, response.text)
        assert "retired" in response.json()["detail"]
        assert fingerprint(store) == before


def test_legacy_read_history_and_protective_reject_and_withdraw_still_work(tmp_path):
    client, store, source, candidate, entry = fixture(tmp_path)
    state = client.get("/api/knowledge").json()
    assert state["sources"] == [source]
    assert state["candidates"] == [candidate]
    assert state["entries"] == [entry]
    assert client.get(f"/api/knowledge/entries/{entry['id']}/history").json() == {
        "revisions": [entry]}
    with store.connect(False) as connection:
        selected = selected_wiki_sources(store, connection, [entry["id"]], None)
    assert selected[0]["id"] == entry["id"]

    reject = {"decision": "reject", "expected_revision": candidate["revision"],
              "idempotency_key": "reject-existing"}
    response = client.post(
        f"/api/knowledge/candidates/{candidate['id']}/resolve", json=reject)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"
    assert client.post(
        f"/api/knowledge/candidates/{candidate['id']}/resolve", json=reject
    ).json() == response.json()

    correction = client.post(f"/api/knowledge/entries/{entry['id']}", json={
        "title": "已纠正旧事实", "content": "纠正后的虚构事实",
        "entry_type": "experience", "status": "active",
        "expected_revision": entry["revision"],
    })
    assert correction.status_code == 200, correction.text
    assert correction.json()["revision"] == 2
    withdrawn = client.post(f"/api/knowledge/entries/{entry['id']}", json={
        "title": correction.json()["title"], "content": correction.json()["content"],
        "entry_type": "experience", "status": "withdrawn",
        "expected_revision": correction.json()["revision"],
    })
    assert withdrawn.status_code == 200, withdrawn.text
    history = client.get(f"/api/knowledge/entries/{entry['id']}/history").json()
    assert [row["revision"] for row in history["revisions"]] == [1, 2, 3]
    with store.connect(False) as connection:
        assert store._get(connection, source["id"], "knowledge_source", True) == source
        assert store._get(connection, entry["id"], "wiki_entry")["status"] == "withdrawn"
        assert store._current(connection, "wiki_entry") == [withdrawn.json()]
