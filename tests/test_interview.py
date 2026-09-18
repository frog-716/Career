"""Batch E Interview vertical over isolated synthetic data."""
import json

from test_communication import setup_submitted, create as create_communication


def confirm(client, opportunity, key="real-1", **extra):
    body = {
        "name": extra.pop("name", "业务一面"),
        "expected_opportunity_revision": opportunity["revision"],
        "idempotency_key": key,
        **extra,
    }
    return client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/real", json=body
    )


def test_confirm_without_date_multiround_and_status_isolation(tmp_path):
    client, store, submitted = setup_submitted(tmp_path / "data")
    created = confirm(client, submitted)
    assert created.status_code == 200, created.text
    first = created.json()["interview"]
    opportunity = created.json()["opportunity"]
    assert first["type"] == "real" and first["status"] == "pending"
    assert first["scheduled_on"] is None and first["scheduled_at"] is None
    assert opportunity["phase"] == "interview"
    assert opportunity["phase_changed_on"] == first["confirmed_on"]
    first_phase_date = opportunity["phase_changed_on"]
    first_op_revision = opportunity["revision"]

    scheduled = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{first['id']}/schedule",
        json={"scheduled_on": "2026-09-25", "scheduled_at": None,
              "expected_revision": first["revision"], "idempotency_key": "schedule"},
    )
    assert scheduled.status_code == 200, scheduled.text
    first = scheduled.json()
    assert first["status"] == "scheduled" and first["scheduled_on"] == "2026-09-25"
    moved = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{first['id']}/schedule",
        json={"scheduled_on": "2026-09-27", "scheduled_at": "2026-09-27T14:00:00+08:00",
              "expected_revision": first["revision"], "idempotency_key": "reschedule"},
    ).json()
    pending = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{first['id']}/pending",
        json={"expected_revision": moved["revision"], "idempotency_key": "pending"},
    ).json()
    assert pending["id"] == first["id"] and pending["status"] == "pending"
    assert pending["scheduled_on"] is None and pending["scheduled_at"] is None
    completed = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{first['id']}/complete",
        json={"completed_on": "2026-09-28", "expected_revision": pending["revision"],
              "idempotency_key": "complete"},
    ).json()
    assert completed["status"] == "completed"
    unchanged = client.get(f"/api/opportunities/{opportunity['id']}").json()
    assert unchanged["revision"] == first_op_revision
    assert unchanged["phase"] == "interview" and unchanged["result"] == "active"

    second = confirm(client, unchanged, "real-2", name="业务二面").json()
    assert second["interview"]["status"] == "pending"
    assert second["opportunity"]["phase_changed_on"] == first_phase_date
    assert second["opportunity"]["revision"] == first_op_revision
    assert len(client.get(f"/api/opportunities/{opportunity['id']}/interviews").json()) == 2
    assert client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{second['interview']['id']}/cancel",
        json={"cancelled_on": "2026-09-29", "expected_revision": 0,
              "idempotency_key": "cancel"},
    ).json()["status"] == "cancelled"
    with store.connect(False) as connection:
        assert connection.execute("SELECT count(*) FROM records WHERE kind='offer'").fetchone()[0] == 0


def test_simulation_parent_preparation_raw_review_and_zero_patch(tmp_path):
    client, store, submitted = setup_submitted(tmp_path / "data")
    result = confirm(client, submitted).json()
    real, opportunity = result["interview"], result["opportunity"]

    preparation = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{real['id']}/preparation",
        json={"focus": "系统设计", "expected_questions": [], "priority_projects": [],
              "risks": [], "notes": "", "expected_revision": 0,
              "idempotency_key": "prep"},
    )
    assert preparation.status_code == 200, preparation.text
    assert preparation.json()["focus"] == "系统设计"
    assert preparation.json()["notes"] == ""

    simulation_body = {"selected_review_ids": [], "communication_ids": [], "wiki_ids": [],
                       "idempotency_key": "sim-1"}
    simulation = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{real['id']}/simulations",
        json=simulation_body,
    )
    assert simulation.status_code == 200, simulation.text
    sim = simulation.json()["interview"]
    assert sim["type"] == "simulation" and sim["target_real_interview_id"] == real["id"]
    assert client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{sim['id']}/preparation",
        json={"focus": "no", "expected_questions": [], "priority_projects": [],
              "risks": [], "notes": "", "expected_revision": 0,
              "idempotency_key": "bad-prep"},
    ).status_code == 409

    raw1 = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{sim['id']}/raw",
        json={"content": "[00:01] 我：旧回答", "expected_revision": 0,
              "idempotency_key": "sim-raw-1"},
    ).json()
    review = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{sim['id']}/final-review",
        json={"summary": "当前结论", "key_qa": [], "patterns": [], "discoveries": [],
              "next_actions": [], "expected_revision": 0, "idempotency_key": "sim-review"},
    ).json()
    raw2 = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{sim['id']}/raw",
        json={"content": "[00:01] 我：修正回答", "expected_revision": raw1["revision"],
              "idempotency_key": "sim-raw-2"},
    ).json()
    assert raw2["revision"] == 2
    assert client.get(
        f"/api/opportunities/{opportunity['id']}/interviews/{sim['id']}/final-review"
    ).json() == review
    blocked = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{sim['id']}/generate-research-patch",
        json={"idempotency_key": "no-sim-patch"},
    )
    assert blocked.status_code == 409
    with store.connect(False) as connection:
        assert connection.execute("SELECT count(*) FROM records WHERE kind='patch_proposal'").fetchone()[0] == 0
        rows = [row[0] for row in connection.execute("SELECT body FROM revisions UNION ALL SELECT body FROM records WHERE kind IN ('interview_command','patch_proposal')")]
    assert not any("旧回答" in row for row in rows)
    ended = client.post(
        f"/api/opportunities/{opportunity['id']}/end",
        json={"result": "withdrawn", "expected_revision": opportunity["revision"],
              "idempotency_key": "end-after-simulation"},
    )
    assert ended.status_code == 200
    replay = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{real['id']}/simulations",
        json=simulation_body,
    )
    assert replay.status_code == 200 and replay.json()["interview"]["id"] == sim["id"]


def test_context_pack_review_selection_and_ai_intents_are_separate(tmp_path):
    client, store, submitted = setup_submitted(tmp_path / "data")
    first_result = confirm(client, submitted).json()
    first, opportunity = first_result["interview"], first_result["opportunity"]
    real_raw = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{first['id']}/raw",
        json={"content": "[00:01] 面试官：团队负责虚构业务。", "expected_revision": 0,
              "idempotency_key": "real-raw"},
    ).json()
    first_review = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{first['id']}/final-review",
        json={"summary": "一面复盘", "key_qa": ["问答"], "patterns": [], "discoveries": [],
              "next_actions": ["准备二面"], "expected_revision": 0,
              "idempotency_key": "review-1"},
    ).json()
    second_result = confirm(client, opportunity, "real-2", name="业务二面").json()
    second = second_result["interview"]

    sim0 = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{second['id']}/simulations",
        json={"selected_review_ids": [], "communication_ids": [], "wiki_ids": [],
              "idempotency_key": "sim-0"},
    ).json()
    assert sim0["context_pack"]["selected_review_ids"] == []
    sim1 = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{second['id']}/simulations",
        json={"selected_review_ids": [first_review["id"]], "communication_ids": [],
              "wiki_ids": [], "idempotency_key": "sim-1"},
    ).json()
    assert sim1["context_pack"]["selected_review_ids"] == [first_review["id"]]
    encoded = json.dumps(sim1["context_pack"], ensure_ascii=False)
    assert "一面复盘" in encoded and "团队负责虚构业务" not in encoded
    assert all(source["purpose"] != "current_resume_document" for source in sim1["context_pack"]["sources"])
    assert "resume_snapshot" in encoded and "本次无简历" in encoded
    simulation_review = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{sim1['interview']['id']}/final-review",
        json={"summary": "模拟复盘", "key_qa": [], "patterns": [], "discoveries": [],
              "next_actions": [], "expected_revision": 0, "idempotency_key": "sim-review-n"},
    ).json()
    sim_n_body = {"selected_review_ids": [first_review["id"], simulation_review["id"]],
                  "communication_ids": [], "wiki_ids": [], "idempotency_key": "sim-n"}
    sim_n = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{second['id']}/simulations",
        json=sim_n_body,
    ).json()
    assert sim_n["context_pack"]["selected_review_ids"] == [first_review["id"], simulation_review["id"]]
    replay_n = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{second['id']}/simulations",
        json=sim_n_body,
    ).json()
    assert replay_n["context_snapshot_id"] == sim_n["context_snapshot_id"]

    generated_review = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{first['id']}/generate-final-review",
        json={"communication_ids": [], "wiki_ids": [], "idempotency_key": "generate-review"},
    )
    assert generated_review.status_code == 200, generated_review.text
    suggestion = generated_review.json()
    assert suggestion["mode"] == "test" and set(suggestion["suggestion"]) == {
        "summary", "key_qa", "patterns", "discoveries", "next_actions"
    }
    with store.connect(False) as connection:
        assert connection.execute("SELECT count(*) FROM records WHERE kind='patch_proposal'").fetchone()[0] == 0
        snapshots = connection.execute("SELECT count(*) FROM records WHERE kind='context_snapshot'").fetchone()[0]
    assert client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{first['id']}/generate-final-review",
        json={"communication_ids": [], "wiki_ids": [], "idempotency_key": "generate-review"},
    ).json() == suggestion
    with store.connect(False) as connection:
        assert connection.execute("SELECT count(*) FROM records WHERE kind='context_snapshot'").fetchone()[0] == snapshots

    generated_patch = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{first['id']}/generate-research-patch",
        json={"communication_ids": [], "wiki_ids": [], "idempotency_key": "generate-patch"},
    )
    assert generated_patch.status_code == 200, generated_patch.text
    proposal = generated_patch.json()["proposal"]
    assert proposal["status"] == "pending" and proposal["origin_interview_id"] == first["id"]
    edited = client.put(
        f"/api/opportunities/{opportunity['id']}/research-patches/{proposal['id']}",
        json={"items": [{"category": "team", "content": "用户核对后的虚构团队信息"}],
              "expected_revision": proposal["revision"], "idempotency_key": "edit-patch"},
    ).json()
    applied = client.post(
        f"/api/opportunities/{opportunity['id']}/research-patches/{proposal['id']}/resolve",
        json={"decision": "accept", "expected_revision": edited["revision"],
              "idempotency_key": "accept-patch"},
    )
    assert applied.status_code == 200, applied.text
    research = client.get(f"/api/opportunities/{opportunity['id']}/research").json()
    assert research["items"][0]["content"] == "用户核对后的虚构团队信息"
    assert client.get(f"/api/opportunities/{opportunity['id']}").json()["phase"] == "interview"

    # A later Raw correction invalidates a still-pending real proposal, not the applied one.
    pending = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{first['id']}/generate-research-patch",
        json={"communication_ids": [], "wiki_ids": [], "idempotency_key": "generate-patch-2"},
    ).json()["proposal"]
    corrected = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{first['id']}/raw",
        json={"content": "[00:01] 面试官：已修正的信息。", "expected_revision": real_raw["revision"],
              "idempotency_key": "real-raw-correct"},
    )
    assert corrected.status_code == 200
    patches = client.get(f"/api/opportunities/{opportunity['id']}/research-patches").json()
    assert next(item for item in patches if item["id"] == pending["id"])["status"] == "stale"
    with store.connect(False) as connection:
        all_bodies = [row[0] for table in ("current", "revisions", "records")
                      for row in connection.execute(f"SELECT body FROM {table}")]
    assert not any("团队负责虚构业务" in body for body in all_bodies)


def test_explicit_legacy_upgrade_preserves_id_and_never_guesses(tmp_path):
    client, store, submitted = setup_submitted(tmp_path / "data")
    with store.connect() as connection:
        store._record(connection, "interview", {
            "id": "legacy-round", "opportunity_id": submitted["id"], "round": "一面 / 模拟?",
            "occurred_at": "2026-09-01T10:00:00+08:00", "raw_note_id": "missing-note",
            "revision": 0,
        })
    legacy = client.get(f"/api/opportunities/{submitted['id']}/interviews/legacy-round").json()
    assert legacy["legacy"] is True and legacy["type"] is None and legacy["status"] is None
    upgraded = client.post(
        f"/api/opportunities/{submitted['id']}/interviews/legacy-round/upgrade",
        json={"type": "real", "name": "用户确认的一面", "status": "completed",
              "confirmed_on": "2026-09-01", "scheduled_on": None, "scheduled_at": None,
              "completed_on": "2026-09-01", "cancelled_on": None,
              "target_real_interview_id": None, "expected_revision": 0,
              "expected_opportunity_revision": submitted["revision"],
              "idempotency_key": "upgrade-legacy"},
    )
    assert upgraded.status_code == 200, upgraded.text
    current = upgraded.json()["interview"]
    assert current["id"] == "legacy-round" and current["type"] == "real"
    assert current["legacy_provenance"]["round"] == "一面 / 模拟?"
    assert upgraded.json()["opportunity"]["phase"] == "interview"


def test_interview_timeline_and_archived_communication_source(tmp_path):
    client, store, submitted = setup_submitted(tmp_path / "data")
    communication = create_communication(client, submitted, key="source").json()
    result = confirm(client, submitted, source_communication_id=communication["id"]).json()
    real, opportunity = result["interview"], result["opportunity"]
    archived = client.post(
        f"/api/opportunities/{opportunity['id']}/communications/{communication['id']}/delete",
        json={"expected_revision": communication["revision"], "idempotency_key": "archive-source"},
    )
    assert archived.status_code == 200
    detail = client.get(f"/api/opportunities/{opportunity['id']}/interviews/{real['id']}").json()
    assert detail["source_communication"]["archived"] is True
    timeline = client.get(f"/api/opportunities/{opportunity['id']}/timeline").json()
    interview_items = [item for item in timeline["items"] if item["source_type"] == "interview"]
    assert len(interview_items) == 1 and interview_items[0]["object_id"] == real["id"]
    with store.connect(False) as connection:
        assert connection.execute("SELECT count(*) FROM records WHERE kind='timeline_event'").fetchone()[0] == 0


def test_context_uses_frozen_submission_resume_not_later_draft(tmp_path):
    from test_record_submitted import client_at, opportunity as make_opportunity, start, save, submit, PDF

    client, _ = client_at(tmp_path / "data")
    opportunity = make_opportunity(client, "冻结简历上下文")
    document = save(client, start(client, opportunity), "投递时姓名")
    sent = submit(client, opportunity, {
        "mode": "draft", "document_id": document["document_id"],
        "expected_document_revision": document["revision"], "document": document["document"],
        "pdf_base64": PDF,
    }).json()
    changed = save(client, document, "投递后当前稿姓名")
    real = confirm(client, sent["opportunity"]).json()["interview"]
    simulation = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{real['id']}/simulations",
        json={"selected_review_ids": [], "communication_ids": [], "wiki_ids": [],
              "idempotency_key": "frozen-resume-context"},
    )
    assert simulation.status_code == 200, simulation.text
    encoded = json.dumps(simulation.json()["context_pack"], ensure_ascii=False)
    assert "投递时姓名" in encoded and "投递后当前稿姓名" not in encoded
    assert changed["revision"] > document["revision"]


def test_without_interview_model_manual_vertical_stays_available(tmp_path):
    from workbench.providers import RealProvider

    client, store, submitted = setup_submitted(tmp_path / "data")
    real_result = confirm(client, submitted).json()
    real, opportunity = real_result["interview"], real_result["opportunity"]
    raw = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{real['id']}/raw",
        json={"content": "纯手工 Raw", "expected_revision": 0, "idempotency_key": "manual-raw"},
    )
    assert raw.status_code == 200
    store.provider = RealProvider("https://api.openai.com/v1", "", "")
    generated = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/{real['id']}/generate-final-review",
        json={"communication_ids": [], "wiki_ids": [], "idempotency_key": "no-model"},
    )
    assert generated.status_code == 503
    assert client.get(f"/api/opportunities/{opportunity['id']}/interviews").status_code == 200
    saved = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{real['id']}/final-review",
        json={"summary": "手工复盘", "key_qa": [], "patterns": [], "discoveries": [],
              "next_actions": [], "expected_revision": 0, "idempotency_key": "manual-review"},
    )
    assert saved.status_code == 200
