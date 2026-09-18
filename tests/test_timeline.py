"""Timeline is a read projection over real source objects."""
import json

from test_communication import setup_submitted, create
from workbench.core import dump


def test_timeline_projects_sources_updates_and_archive(tmp_path):
    client, store, opportunity = setup_submitted(tmp_path / "data")
    event = create(client, opportunity, content="  确认后续\n会安排业务面  ").json()
    response = client.get("/api/opportunities/" + opportunity["id"] + "/timeline")
    assert response.status_code == 200, response.text
    timeline = response.json()
    assert {item["source_type"] for item in timeline["items"]} == {"opportunity_created", "submission", "communication"}
    item = next(item for item in timeline["items"] if item["source_type"] == "communication")
    assert item["object_id"] == event["id"] and item["summary"] == "确认后续 会安排业务面"
    assert item["target"] == {"kind": "communication", "id": event["id"]}
    submission = next(item for item in timeline["items"] if item["source_type"] == "submission")
    assert submission["target"]["kind"] == "submission"
    with store.connect(False) as connection:
        assert connection.execute("SELECT count(*) FROM records WHERE kind='timeline_event'").fetchone()[0] == 0

    updated = client.put("/api/opportunities/" + opportunity["id"] + "/communications/" + event["id"], json={
        "type": "phone", "occurred_on": "2026-09-16", "content": "新的摘要",
        "expected_revision": 0, "idempotency_key": "update-timeline",
    }).json()
    timeline = client.get("/api/opportunities/" + opportunity["id"] + "/timeline").json()
    communications = [item for item in timeline["items"] if item["source_type"] == "communication"]
    assert len(communications) == 1 and communications[0]["summary"] == "新的摘要"
    client.post("/api/opportunities/" + opportunity["id"] + "/communications/" + event["id"] + "/delete", json={
        "expected_revision": updated["revision"], "idempotency_key": "archive-timeline",
    })
    timeline = client.get("/api/opportunities/" + opportunity["id"] + "/timeline").json()
    assert {item["source_type"] for item in timeline["items"]} == {"opportunity_created", "submission"}


def test_unknown_legacy_date_is_not_invented(tmp_path):
    client, store, opportunity = setup_submitted(tmp_path / "data")
    with store.connect() as connection:
        store._record(connection, "communication", {
            "id": "unknown-date", "opportunity_id": opportunity["id"], "occurred_at": "无法核对",
            "channel": "", "participants": [], "outcome": "", "created_at": "2026-09-14T00:00:00+00:00",
        })
    timeline = client.get("/api/opportunities/" + opportunity["id"] + "/timeline").json()
    assert not any(item["object_id"] == "unknown-date" for item in timeline["items"])
    assert timeline["unknown_date_items"][0]["object_id"] == "unknown-date"
    assert timeline["unknown_date_items"][0]["occurred_on"] is None


def test_unknown_legacy_opportunity_created_date_is_grouped_unknown(tmp_path):
    client, store, opportunity = setup_submitted(tmp_path / "data")
    with store.connect() as connection:
        raw = json.loads(connection.execute(
            "SELECT body FROM current WHERE kind='opportunity' AND id=?", (opportunity["id"],)
        ).fetchone()[0])
        raw["created_on"] = None
        connection.execute("UPDATE current SET body=? WHERE id=?", (dump(raw), opportunity["id"]))
    timeline = client.get("/api/opportunities/" + opportunity["id"] + "/timeline").json()
    assert not any(item["source_type"] == "opportunity_created" for item in timeline["items"])
    assert any(item["source_type"] == "opportunity_created" for item in timeline["unknown_date_items"])
