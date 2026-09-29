"""Old Note-to-Candidate intake cannot bypass the retired knowledge writer."""

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


HEADERS = {"X-Career-Request": "1"}


def snapshot(store):
    with store.connect(False) as db:
        return {
            "epoch": store._epoch(db),
            "current": db.execute("SELECT id,kind,revision,body FROM current ORDER BY id").fetchall(),
            "records": db.execute("SELECT id,kind,body FROM records ORDER BY id").fetchall(),
            "revisions": db.execute("SELECT id,revision,body FROM revisions ORDER BY id,revision").fetchall(),
        }


def test_note_candidate_writer_is_retired_without_changing_note_or_old_knowledge(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    client = TestClient(create_app(store))
    episode_response = client.post("/api/journey/episodes", json={
        "company": "虚构公司", "role": "研究员", "focus": "虚构阶段",
    }, headers=HEADERS)
    assert episode_response.status_code == 200, episode_response.text
    episode_id = episode_response.json()["id"]
    note_response = client.post("/api/journey/notes", json={
        "scope_type": "episode", "scope_id": episode_id, "kind": "reflection",
        "title": "原题", "content": "虚构原始记录", "idempotency_key": "note",
    }, headers=HEADERS)
    assert note_response.status_code == 200, note_response.text
    note_id = note_response.json()["id"]
    correction = client.post(f"/api/journey/notes/{note_id}/correct", json={
        "expected_revision": 0, "title": "更正标题", "content": "虚构更正内容",
        "idempotency_key": "correction",
    }, headers=HEADERS)
    assert correction.status_code == 200, correction.text

    with store.connect() as db:
        source = {
            "id": "historical-source", "title": "旧资料", "content": "虚构历史来源",
            "source_type": "text", "scope_type": "episode", "scope_id": episode_id,
        }
        store._record(db, "knowledge_source", source)
        candidate = store._save(db, "knowledge_candidate", {
            "id": "historical-candidate", "source_ids": [source["id"]],
            "entry_type": "experience", "title": "旧候选", "content": "虚构旧候选",
            "scope_type": "episode", "scope_id": episode_id, "status": "pending",
            "entry_id": None,
        }, 0)
    before = snapshot(store)

    body = {
        "expected_revision": 1, "title": "新旧候选", "content": "虚构新选段",
        "entry_type": "experience", "scope_type": "episode", "scope_id": episode_id,
        "promote_to_personal": False, "idempotency_key": "candidate",
    }
    for _ in range(2):
        response = client.post(f"/api/journey/notes/{note_id}/candidate", json=body, headers=HEADERS)
        assert response.status_code == 409, response.text
        assert "retired" in response.text
        assert snapshot(store) == before

    assert client.get(f"/api/journey/notes/{note_id}/history").json()["revisions"][-1]["content"] == "虚构更正内容"
    old_knowledge = client.get("/api/knowledge").json()
    assert source in old_knowledge["sources"]
    assert candidate in old_knowledge["candidates"]
