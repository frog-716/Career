"""Batch D Communication actions: synthetic data, no external provider."""
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store, dump
from workbench.providers import TestProvider


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


def setup_submitted(path, key="one"):
    store = Store(path, TestProvider())
    client = TestClient(create_app(store), headers=HEADERS)
    created = client.post("/api/opportunities", json={
        "company_name": "虚构招聘公司", "title": "虚构岗位 " + key,
        "jd": "仅供测试的 JD", "idempotency_key": "op-" + key,
    }).json()
    response = client.post("/api/opportunities/" + created["id"] + "/submitted", json={
        "expected_revision": created["revision"], "idempotency_key": "submit-" + key,
        "resume": {"mode": "none"},
    })
    assert response.status_code == 200, response.text
    return client, store, response.json()["opportunity"]


def create(client, opportunity, key="communication", content="HR说周五下午两点业务一面。", kind="phone"):
    return client.post("/api/opportunities/" + opportunity["id"] + "/communications", json={
        "type": kind, "occurred_on": "2026-09-18", "content": content,
        "idempotency_key": key,
    })


def test_create_update_archive_preserves_opportunity_and_source(tmp_path):
    client, store, opportunity = setup_submitted(tmp_path / "data")
    before = client.get("/api/opportunities/" + opportunity["id"]).json()
    response = create(client, opportunity)
    assert response.status_code == 200, response.text
    event = response.json()
    assert event["communication_format"] == 2
    assert event["revision"] == 0 and event["archived"] is False
    assert event["type"] == "phone" and event["occurred_on"] == "2026-09-18"
    assert create(client, opportunity).json() == event
    assert client.get("/api/opportunities/" + opportunity["id"]).json() == before

    with store.connect(False) as connection:
        assert connection.execute("SELECT count(*) FROM records WHERE kind='journey_note'").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM records WHERE kind='interview'").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM records WHERE kind='offer'").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM records WHERE kind='research_snapshot'").fetchone()[0] == 0

    changed = client.put("/api/opportunities/" + opportunity["id"] + "/communications/" + event["id"], json={
        "type": "text", "occurred_on": "2026-09-17", "content": "更正后的当前沟通",
        "expected_revision": 0, "idempotency_key": "update",
    })
    assert changed.status_code == 200, changed.text
    current = changed.json()
    assert current["id"] == event["id"] and current["revision"] == 1
    assert current["content"] == "更正后的当前沟通"
    assert client.put("/api/opportunities/" + opportunity["id"] + "/communications/" + event["id"], json={
        "type": "other", "occurred_on": "2026-09-16", "content": "过期窗口",
        "expected_revision": 0, "idempotency_key": "stale",
    }).status_code == 409

    archived = client.post("/api/opportunities/" + opportunity["id"] + "/communications/" + event["id"] + "/delete", json={
        "expected_revision": 1, "idempotency_key": "archive",
    })
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived"] is True and archived.json()["revision"] == 2
    assert client.get("/api/opportunities/" + opportunity["id"] + "/communications").json() == []
    assert client.get("/api/opportunities/" + opportunity["id"] + "/communications/" + event["id"]).status_code == 404
    assert client.post("/api/opportunities/" + opportunity["id"] + "/communications/" + event["id"] + "/delete", json={
        "expected_revision": 1, "idempotency_key": "archive",
    }).json() == archived.json()
    replayed_update = client.put("/api/opportunities/" + opportunity["id"] + "/communications/" + event["id"], json={
        "type": "text", "occurred_on": "2026-09-17", "content": "更正后的当前沟通",
        "expected_revision": 0, "idempotency_key": "update",
    })
    assert replayed_update.status_code == 200
    assert replayed_update.json()["id"] == event["id"] and replayed_update.json()["archived"] is True
    with store.connect(False) as connection:
        raw = json.loads(connection.execute("SELECT body FROM records WHERE id=? AND kind='communication'", (event["id"],)).fetchone()[0])
    assert raw["archived"] is True and raw["archived_at"]
    assert raw["content"] == "更正后的当前沟通"
    assert client.get("/api/opportunities/" + opportunity["id"]).json() == before


def test_scope_phase_ended_and_concurrency_guards(tmp_path):
    client, store, first = setup_submitted(tmp_path / "data", "first")
    second = client.post("/api/opportunities", json={
        "company_name": "另一虚构公司", "title": "另一岗位", "jd": "虚构 JD", "idempotency_key": "second",
    }).json()
    assert create(client, second, "wrong-phase").status_code == 409

    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(lambda _: create(client, first, "same-key", "同一次双击", "text"), range(3)))
    assert all(response.status_code == 200 for response in responses)
    ids = {response.json()["id"] for response in responses}
    assert len(ids) == 1
    event = responses[0].json()
    assert client.get("/api/opportunities/" + second["id"] + "/communications/" + event["id"]).status_code == 404
    alias = first["id"].removeprefix("opportunity:")
    assert client.get("/api/opportunities/" + alias + "/communications").json() == [event]

    ended = client.post("/api/opportunities/" + first["id"] + "/end", json={
        "result": "withdrawn", "expected_revision": first["revision"], "idempotency_key": "end",
    })
    assert ended.status_code == 200, ended.text
    assert create(client, first, "same-key", "同一次双击", "text").json()["id"] == event["id"]
    assert create(client, first, "after-end").status_code == 409
    corrected = client.put("/api/opportunities/" + first["id"] + "/communications/" + event["id"], json={
        "type": "text", "occurred_on": "2026-09-18", "content": "结束后的历史更正",
        "expected_revision": 0, "idempotency_key": "ended-update",
    })
    assert corrected.status_code == 200, corrected.text
    after = client.get("/api/opportunities/" + first["id"]).json()
    assert after["result"] == "withdrawn" and after["phase"] == "submitted"
    assert after["revision"] == ended.json()["revision"]


def test_legacy_typed_reuses_identity_without_note_double_write(tmp_path):
    client, store, opportunity = setup_submitted(tmp_path / "data")
    alias = opportunity["id"].removeprefix("opportunity:")
    note = {"id": "legacy-note", "scope_type": "job", "scope_id": alias, "kind": "communication",
            "title": "旧沟通", "content": "旧原文", "submission_id": None,
            "idempotency_key": "legacy-note", "created_at": "2026-09-15T03:00:00+00:00"}
    typed = {"id": "legacy-typed", "opportunity_id": opportunity["id"],
             "occurred_at": "2026-09-15T11:00:00+08:00", "channel": "邮件",
             "participants": ["招聘方"], "raw_note_id": note["id"], "outcome": "待确认",
             "created_at": note["created_at"]}
    note_only = dict(note, id="note-only", idempotency_key="note-only", content="只有Note")
    with store.connect() as connection:
        store._record(connection, "journey_note", note)
        store._record(connection, "journey_note", note_only)
        store._record(connection, "communication", typed)
        connection.execute("INSERT INTO current VALUES(?,?,?,?)", (
            "note-revision:" + note["id"], "journey_note_revision", 1,
            dump({"id": "note-revision:" + note["id"], "note_id": note["id"], "title": "旧沟通",
                  "content": "更正后的旧原文", "created_at": "2026-09-16T03:00:00+00:00", "revision": 1}),
        ))
    listing = client.get("/api/opportunities/" + opportunity["id"] + "/communications").json()
    assert len(listing) == 1 and listing[0]["id"] == typed["id"]
    assert listing[0]["content"] == "更正后的旧原文"
    assert listing[0]["type"] is None and listing[0]["legacy"] is True and listing[0]["revision"] == 0
    assert client.post("/api/opportunity-activity/communication", json={
        "opportunity_id": opportunity["id"], "content": "旁路", "idempotency_key": "old",
    }).status_code == 409
    assert client.post("/api/journey/notes", json={
        "scope_type": "job", "scope_id": alias, "kind": "communication", "content": "旁路", "idempotency_key": "old-note",
    }).status_code == 409
    assert client.post("/api/journey/notes/" + note["id"] + "/correct", json={
        "title": "旁路", "content": "旁路", "expected_revision": 1, "idempotency_key": "old-correct",
    }).status_code == 409

    upgraded = client.put("/api/opportunities/" + opportunity["id"] + "/communications/" + typed["id"], json={
        "type": "other", "occurred_on": "2026-09-15", "content": "用户显式核对内容",
        "expected_revision": 0, "idempotency_key": "upgrade",
    })
    assert upgraded.status_code == 200, upgraded.text
    assert upgraded.json()["id"] == typed["id"] and upgraded.json()["communication_format"] == 2
    with store.connect(False) as connection:
        saved_note = json.loads(connection.execute("SELECT body FROM records WHERE id=?", (note["id"],)).fetchone()[0])
    assert saved_note == note


def test_read_only_legacy_communication_detail_stays_reachable(tmp_path):
    client, store, _ = setup_submitted(tmp_path / "data")
    with store.connect() as connection:
        store._save(connection, "job", {
            "id": "legacy-job", "company": "历史公司", "title": "历史岗位",
            "jd": "历史 JD", "url": "", "status": "active",
            "created_at": "2026-09-15T03:00:00+00:00",
        }, 0)
        store._record(connection, "communication", {
            "id": "legacy-detail", "opportunity_id": "opportunity:legacy-job",
            "occurred_at": "2026-09-15T11:00:00+08:00", "content": "历史沟通",
            "created_at": "2026-09-15T03:00:00+00:00",
        })
    response = client.get(
        "/api/opportunities/legacy-job/communications/legacy-detail"
    )
    assert response.status_code == 200, response.text
    assert response.json()["legacy"] is True
    assert client.put(
        "/api/opportunities/legacy-job/communications/legacy-detail",
        json={"type": "other", "occurred_on": "2026-09-15", "content": "写入",
              "expected_revision": 0, "idempotency_key": "blocked"},
    ).status_code == 409
