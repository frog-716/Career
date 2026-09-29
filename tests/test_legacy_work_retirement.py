"""Phase E: old work objects remain readable sources but cannot gain new facts."""

import json

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


def fixture(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    client = TestClient(create_app(store), base_url="http://127.0.0.1", headers=HEADERS)
    project = client.post("/api/work/projects", json={
        "name": "虚构项目", "description": "", "tags": [], "status": "completed",
        "status_note": "", "idempotency_key": "retirement-project",
    }).json()
    with store.connect() as connection:
        achievement = store._save(connection, "work_achievement", {
            "id": "old-achievement", "project_id": project["id"], "title": "旧成果",
            "content": "虚构旧内容", "created_at": "2026-01-01T00:00:00Z",
        }, 0)
        event = {"id": "old-event", "target_type": "project", "target_id": project["id"],
                 "title": "旧事件", "kind": "delivery", "content": "虚构事件原文",
                 "created_at": "2026-01-01T00:00:00Z"}
        evidence = {"id": "old-evidence", "scope_type": "project", "scope_id": project["id"],
                    "title": "旧证据", "source_type": "document", "content": "虚构证据原文",
                    "created_at": "2026-01-01T00:00:00Z"}
        store._record(connection, "work_event", event)
        store._record(connection, "work_evidence", evidence)
        store._record(connection, "work_evidence_link", {
            "id": "old-link", "achievement_id": achievement["id"], "evidence_id": evidence["id"],
            "achievement_revision": achievement["revision"],
            "evidence_created_at": evidence["created_at"], "created_at": evidence["created_at"],
        })
    return client, store, project, achievement, event, evidence


def fingerprint(store):
    with store.connect(False) as connection:
        return {
            "epoch": connection.execute("SELECT epoch FROM meta WHERE id=1").fetchone()[0],
            "current": connection.execute("SELECT id,kind,revision,body FROM current ORDER BY id").fetchall(),
            "records": connection.execute("SELECT id,kind,body FROM records ORDER BY id").fetchall(),
        }


@pytest.mark.parametrize("action", [
    "event", "achievement", "achievement_edit", "evidence", "evidence_link", "reuse",
])
def test_legacy_work_writes_are_closed_without_changing_existing_records(tmp_path, action):
    client, store, project, achievement, _, evidence = fixture(tmp_path)
    routes = {
        "event": ("/api/work/events", {"project_id": project["id"], "title": "新事件",
                                      "kind": "delivery", "content": "不应写入", "idempotency_key": action}),
        "achievement": ("/api/work/achievements", {"project_id": project["id"],
                                                   "title": "新成果", "content": "不应写入", "idempotency_key": action}),
        "achievement_edit": (f"/api/work/achievements/{achievement['id']}", {
            "title": "改写成果", "content": "不应写入", "expected_revision": achievement["revision"],
            "idempotency_key": action}),
        "evidence": ("/api/work/evidence", {"scope_type": "project", "scope_id": project["id"],
                                            "title": "新证据", "source_type": "document",
                                            "content": "不应写入", "idempotency_key": action}),
        "evidence_link": ("/api/work/evidence-links", {"achievement_id": achievement["id"],
                                                      "evidence_id": evidence["id"], "idempotency_key": action}),
        "reuse": (f"/api/work/achievements/{achievement['id']}/reuse", {
            "expected_revision": achievement["revision"], "title": "旧复用表达",
            "content": "不应写入", "allow_resume_reuse": True, "idempotency_key": action}),
    }
    before = fingerprint(store)
    route, payload = routes[action]
    response = client.post(route, json=payload)
    assert response.status_code == 409, response.text
    assert "retired" in response.json()["detail"]
    assert fingerprint(store) == before


def test_legacy_work_remains_readable_as_raw_and_existing_reuse_can_be_revoked(tmp_path):
    client, store, project, achievement, event, evidence = fixture(tmp_path)
    with store.connect() as connection:
        approved = store._save(connection, "wiki_entry", {
            "id": "old-approved-reuse", "title": "已批准旧表达", "content": "虚构已批准表达",
            "entry_type": "achievement", "scope_type": "personal", "scope_id": "",
            "source_ids": [], "status": "active", "verification": "user_asserted",
            "fact_status": "confirmed", "reuse_status": "approved", "allowed_uses": ["resume"],
            "reuse_provenance": {"kind": "work_achievement_reuse", "source": {
                "kind": "work_achievement", "id": achievement["id"],
                "revision": achievement["revision"], "hash": "synthetic"}},
            "created_at": "2026-01-01T00:00:00Z",
        }, 0)

    domain = client.get("/api/work-domain").json()
    assert next(item for item in domain["events"] if item["id"] == event["id"])["content"] == event["content"]
    assert next(item for item in domain["evidence"] if item["id"] == evidence["id"])["content"] == evidence["content"]
    assert next(item for item in domain["achievements"] if item["id"] == achievement["id"])["content"] == achievement["content"]
    for kind, item in (("work_event", event), ("work_evidence", evidence)):
        response = client.get(f"/api/raw/{kind}/{item['id']}")
        assert response.status_code == 200, response.text
        assert item["content"] in json.dumps(response.json(), ensure_ascii=False)

    response = client.post(f"/api/work/reuses/{approved['id']}/revoke", json={
        "expected_revision": approved["revision"], "idempotency_key": "revoke-existing",
    })
    assert response.status_code == 200, response.text
    assert response.json()["reuse_status"] == "revoked"
    with store.connect(False) as connection:
        assert store._get(connection, achievement["id"], "work_achievement") == achievement
        assert store._get(connection, evidence["id"], "work_evidence", True) == evidence
