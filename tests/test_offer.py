"""Batch F Offer vertical over isolated synthetic data."""
import json
from concurrent.futures import ThreadPoolExecutor

from test_communication import setup_submitted
from test_interview import confirm
from workbench.core import digest, dump


def terms(**extra):
    value = {
        "offered_role_title": "",
        "location": "",
        "start_date": None,
        "employment_type": "",
        "probation": "",
        "benefits": "",
        "compensation": {
            "guaranteed_cash": "",
            "variable_cash": "",
            "equity": "",
            "one_time": "",
            "notes": "",
        },
        "other_terms": "",
    }
    value.update(extra)
    return value


def record(client, opportunity, key="record-offer", **extra):
    body = {
        "received_on": "2026-09-30",
        "terms": terms(),
        "expected_opportunity_revision": opportunity["revision"],
        "idempotency_key": key,
        **extra,
    }
    return client.post(f"/api/opportunities/{opportunity['id']}/offer", json=body)


def test_record_offer_is_atomic_unique_and_never_copies_context(tmp_path):
    client, store, submitted = setup_submitted(tmp_path / "data")
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: record(client, submitted, "same-click"), range(2)))
    assert all(response.status_code == 200 for response in responses)
    offer_ids = {response.json()["offer"]["id"] for response in responses}
    assert len(offer_ids) == 1
    result = responses[0].json()
    offer, opportunity = result["offer"], result["opportunity"]
    assert offer["offer_format"] == 2 and offer["revision"] == 0
    assert offer["terms"]["offered_role_title"] == ""
    assert offer["terms"]["location"] == ""
    assert opportunity["phase"] == "offer"
    assert opportunity["phase_changed_on"] != offer["received_on"]
    assert opportunity["confirmed_offer_id"] == offer["id"]
    assert record(client, submitted, "second-offer").status_code == 409
    alias = opportunity["id"].removeprefix("opportunity:")
    assert client.get(f"/api/opportunities/{alias}/offer").json()["id"] == offer["id"]
    with store.connect(False) as connection:
        assert connection.execute("SELECT count(*) FROM records WHERE kind='offer'").fetchone()[0] == 1


def test_record_offer_from_interview_does_not_require_completed_round(tmp_path):
    client, _, submitted = setup_submitted(tmp_path / "data")
    interview_result = confirm(client, submitted).json()
    real, opportunity = interview_result["interview"], interview_result["opportunity"]
    assert real["status"] == "pending"
    response = record(client, opportunity, terms=terms(offered_role_title="正式岗位名称"))
    assert response.status_code == 200, response.text
    assert response.json()["opportunity"]["phase"] == "offer"
    assert response.json()["offer"]["terms"]["offered_role_title"] == "正式岗位名称"


def test_update_is_current_only_cas_and_does_not_change_result(tmp_path):
    client, store, submitted = setup_submitted(tmp_path / "data")
    result = record(client, submitted, terms=terms(
        compensation={"guaranteed_cash": "25k/月 × 14，税前，CNY", "variable_cash": "15%奖金",
                      "equity": "", "one_time": "", "notes": ""},
    )).json()
    offer, opportunity = result["offer"], result["opportunity"]
    changed_terms = terms(
        offered_role_title="高级工程师",
        location="上海",
        compensation={"guaranteed_cash": "28k/月 × 14，税前，CNY", "variable_cash": "15%奖金",
                      "equity": "待确认", "one_time": "签字费20k", "notes": "不计算总包"},
    )
    response = client.put(f"/api/opportunities/{opportunity['id']}/offer/{offer['id']}", json={
        "received_on": offer["received_on"], "terms": changed_terms,
        "expected_revision": offer["revision"], "idempotency_key": "update-offer",
    })
    assert response.status_code == 200, response.text
    current = response.json()
    assert current["revision"] == 1 and current["terms"] == changed_terms
    assert client.get(f"/api/opportunities/{opportunity['id']}").json()["result"] == "active"
    stale = client.put(f"/api/opportunities/{opportunity['id']}/offer/{offer['id']}", json={
        "received_on": offer["received_on"], "terms": terms(location="过期窗口"),
        "expected_revision": 0, "idempotency_key": "stale-update",
    })
    assert stale.status_code == 409
    replay = client.put(f"/api/opportunities/{opportunity['id']}/offer/{offer['id']}", json={
        "received_on": offer["received_on"], "terms": changed_terms,
        "expected_revision": offer["revision"], "idempotency_key": "update-offer",
    })
    assert replay.status_code == 200 and replay.json()["id"] == offer["id"]
    with store.connect(False) as connection:
        bodies = [row[0] for table in ("current", "revisions", "records")
                  for row in connection.execute(f"SELECT body FROM {table}")]
    assert not any("25k/月" in body for body in bodies)
    assert sum("28k/月" in body for body in bodies) == 1
    assert not any("offer_version" in body for body in bodies)


def test_negotiation_communication_is_separate_from_offer(tmp_path):
    client, _, submitted = setup_submitted(tmp_path / "data")
    result = record(client, submitted).json()
    offer, opportunity = result["offer"], result["opportunity"]
    before = client.get(f"/api/opportunities/{opportunity['id']}/offer").json()
    events = []
    for index, content in enumerate(("HR提出25k", "HR确认最多28k"), 1):
        response = client.post(f"/api/opportunities/{opportunity['id']}/communications", json={
            "type": "phone", "purpose": "negotiation", "occurred_on": f"2026-10-0{index}",
            "content": content, "idempotency_key": f"negotiation-{index}",
        })
        assert response.status_code == 200, response.text
        events.append(response.json())
    assert all(event["purpose"] == "negotiation" for event in events)
    assert client.get(f"/api/opportunities/{opportunity['id']}/offer").json() == before
    assert client.get(f"/api/opportunities/{opportunity['id']}").json()["result"] == "active"
    other_client, _, other_submitted = setup_submitted(tmp_path / "other", "other")
    assert other_client.post(f"/api/opportunities/{other_submitted['id']}/communications", json={
        "type": "text", "purpose": "negotiation", "occurred_on": "2026-10-01",
        "content": "错误阶段", "idempotency_key": "bad-negotiation",
    }).status_code == 409
    update = client.put(f"/api/opportunities/{opportunity['id']}/communications/{events[0]['id']}", json={
        "type": "text", "occurred_on": "2026-10-01", "content": "历史更正",
        "expected_revision": events[0]["revision"], "idempotency_key": "correct-negotiation",
    })
    assert update.status_code == 200 and update.json()["purpose"] == "negotiation"
    assert client.put(f"/api/opportunities/{opportunity['id']}/communications/{events[1]['id']}", json={
        "type": "text", "purpose": "general", "occurred_on": "2026-10-02", "content": "改purpose",
        "expected_revision": events[1]["revision"], "idempotency_key": "bad-purpose",
    }).status_code == 422


def test_accept_reject_withdraw_and_zero_employment_side_effect(tmp_path):
    client, store, submitted = setup_submitted(tmp_path / "data", "accepted")
    result = record(client, submitted).json()
    offer, opportunity = result["offer"], result["opportunity"]
    before_work = client.get("/api/work-domain").json()
    body = {"expected_opportunity_revision": opportunity["revision"],
            "expected_offer_revision": offer["revision"], "idempotency_key": "accept"}
    accepted = client.post(
        f"/api/opportunities/{opportunity['id']}/offer/{offer['id']}/accept", json=body
    )
    assert accepted.status_code == 200, accepted.text
    ended = accepted.json()
    assert ended["phase"] == "offer" and ended["result"] == "accepted"
    assert client.post(
        f"/api/opportunities/{opportunity['id']}/offer/{offer['id']}/accept", json=body
    ).json() == ended
    assert client.get("/api/work-domain").json() == before_work
    assert client.put(f"/api/opportunities/{opportunity['id']}/offer/{offer['id']}", json={
        "received_on": offer["received_on"], "terms": offer["terms"],
        "expected_revision": offer["revision"], "idempotency_key": "ended-update",
    }).status_code == 409
    assert client.post(f"/api/opportunities/{opportunity['id']}/communications", json={
        "type": "phone", "purpose": "negotiation", "occurred_on": "2026-10-01",
        "content": "结束后新增", "idempotency_key": "ended-communication",
    }).status_code == 409
    with store.connect(False) as connection:
        assert connection.execute("SELECT count(*) FROM current WHERE kind='employment'").fetchone()[0] == 0

    for decision in ("rejected", "withdrawn"):
        other_client, _, other = setup_submitted(tmp_path / decision, decision)
        offer_result = record(other_client, other).json()
        ended_response = other_client.post(f"/api/opportunities/{other['id']}/end", json={
            "result": decision, "expected_revision": offer_result["opportunity"]["revision"],
            "idempotency_key": "end-" + decision,
        })
        assert ended_response.status_code == 200, ended_response.text
        assert ended_response.json()["phase"] == "offer"
        assert ended_response.json()["result"] == decision


def test_legacy_end_accepted_route_delegates_to_canonical_accept(tmp_path):
    client, _, submitted = setup_submitted(tmp_path / "data")
    result = record(client, submitted).json()
    offer, opportunity = result["offer"], result["opportunity"]
    response = client.post(f"/api/opportunities/{opportunity['id']}/end", json={
        "result": "accepted", "offer_id": offer["id"],
        "expected_revision": opportunity["revision"],
        "expected_offer_revision": offer["revision"],
        "idempotency_key": "legacy-accept-adapter",
    })
    assert response.status_code == 200, response.text
    assert response.json()["phase"] == "offer"
    assert response.json()["result"] == "accepted"


def test_legacy_end_accepted_rejects_stale_offer_revision(tmp_path):
    client, _, submitted = setup_submitted(tmp_path / "data")
    result = record(client, submitted).json()
    offer, opportunity = result["offer"], result["opportunity"]
    updated = client.put(
        f"/api/opportunities/{opportunity['id']}/offer/{offer['id']}",
        json={
            "received_on": offer["received_on"],
            "terms": terms(location="上海"),
            "expected_revision": offer["revision"],
            "idempotency_key": "offer-change-before-legacy-accept",
        },
    )
    assert updated.status_code == 200 and updated.json()["revision"] == 1
    stale = client.post(f"/api/opportunities/{opportunity['id']}/end", json={
        "result": "accepted", "offer_id": offer["id"],
        "expected_revision": opportunity["revision"],
        "expected_offer_revision": offer["revision"],
        "idempotency_key": "stale-legacy-accept",
    })
    assert stale.status_code == 409
    assert client.get(f"/api/opportunities/{opportunity['id']}").json()["result"] == "active"

    missing = client.post(f"/api/opportunities/{opportunity['id']}/end", json={
        "result": "accepted", "offer_id": offer["id"],
        "expected_revision": opportunity["revision"],
        "idempotency_key": "missing-offer-revision",
    })
    assert missing.status_code == 422
    assert client.get(f"/api/opportunities/{opportunity['id']}").json()["result"] == "active"


def test_accept_withdraw_concurrency_has_one_final_result(tmp_path):
    client, _, submitted = setup_submitted(tmp_path / "data")
    result = record(client, submitted).json()
    offer, opportunity = result["offer"], result["opportunity"]

    def accept():
        return client.post(f"/api/opportunities/{opportunity['id']}/offer/{offer['id']}/accept", json={
            "expected_opportunity_revision": opportunity["revision"],
            "expected_offer_revision": offer["revision"], "idempotency_key": "race-accept",
        })

    def withdraw():
        return client.post(f"/api/opportunities/{opportunity['id']}/end", json={
            "result": "withdrawn", "expected_revision": opportunity["revision"],
            "idempotency_key": "race-withdraw",
        })

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [pool.submit(accept), pool.submit(withdraw)]
        statuses = sorted(f.result().status_code for f in responses)
    assert statuses == [200, 409]
    assert client.get(f"/api/opportunities/{opportunity['id']}").json()["result"] in {"accepted", "withdrawn"}


def test_timeline_projects_offer_negotiation_and_result_without_fact_rows(tmp_path):
    client, store, submitted = setup_submitted(tmp_path / "data")
    result = record(client, submitted, terms=terms(offered_role_title="明确Offer岗位")).json()
    offer, opportunity = result["offer"], result["opportunity"]
    communication = client.post(f"/api/opportunities/{opportunity['id']}/communications", json={
        "type": "phone", "purpose": "negotiation", "occurred_on": "2026-10-01",
        "content": "谈薪沟通", "idempotency_key": "timeline-negotiation",
    }).json()
    accepted = client.post(f"/api/opportunities/{opportunity['id']}/offer/{offer['id']}/accept", json={
        "expected_opportunity_revision": opportunity["revision"],
        "expected_offer_revision": offer["revision"], "idempotency_key": "timeline-accept",
    }).json()
    timeline = client.get(f"/api/opportunities/{opportunity['id']}/timeline").json()
    source_types = [item["source_type"] for item in timeline["items"]]
    assert source_types.count("offer") == 1 and source_types.count("opportunity_result") == 1
    negotiation = next(item for item in timeline["items"] if item["object_id"] == communication["id"])
    assert negotiation["title"] == "谈薪沟通"
    result_item = next(item for item in timeline["items"] if item["source_type"] == "opportunity_result")
    assert result_item["title"] == "接受 Offer" and accepted["result"] == "accepted"
    with store.connect(False) as connection:
        persisted_kinds = {row[0] for row in connection.execute("SELECT kind FROM records")}
    assert not persisted_kinds.intersection({"timeline_event", "offer_timeline_event", "decision_event", "result_event"})


def test_legacy_offer_is_unknown_and_explicit_upgrade_reuses_id(tmp_path):
    client, store, submitted = setup_submitted(tmp_path / "data")
    alias = submitted["id"].removeprefix("opportunity:")
    note = {"id": "legacy-offer-note", "scope_type": "job", "scope_id": alias, "kind": "offer",
            "title": "历史Offer", "content": "历史原文", "created_at": "2026-09-20T00:00:00+00:00"}
    legacy = {"id": "legacy-offer", "opportunity_id": submitted["id"],
              "occurred_at": "2026-09-20T08:00:00+08:00", "terms": {"薪酬": "旧待核对"},
              "status": "accepted", "raw_note_id": note["id"], "created_at": note["created_at"]}
    with store.connect() as connection:
        store._record(connection, "journey_note", note)
        store._record(connection, "offer", legacy)
    read = client.get(f"/api/opportunities/{submitted['id']}/offer").json()
    assert read["id"] == legacy["id"] and read["legacy"] is True
    assert read["terms"] is None and read["decision"] == "active"
    assert client.get(f"/api/opportunities/{submitted['id']}").json()["phase"] == "submitted"
    response = client.post(
        f"/api/opportunities/{submitted['id']}/offer/{legacy['id']}/upgrade",
        json={"received_on": "2026-09-20", "terms": terms(offered_role_title="用户确认岗位"),
              "expected_opportunity_revision": submitted["revision"],
              "expected_legacy_hash": digest(legacy), "idempotency_key": "upgrade-offer",
              "confirmed": True},
    )
    assert response.status_code == 200, response.text
    upgraded = response.json()["offer"]
    assert upgraded["id"] == legacy["id"] and upgraded["offer_format"] == 2
    assert upgraded["legacy_provenance"]["original_body"] == legacy
    assert client.get(f"/api/opportunities/{submitted['id']}").json()["phase"] == "offer"
    assert client.post("/api/opportunity-activity/offer", json={
        "opportunity_id": submitted["id"], "content": "旁路", "idempotency_key": "old-offer",
    }).status_code == 409
    assert client.post("/api/journey/notes", json={
        "scope_type": "job", "scope_id": alias, "kind": "offer", "content": "旁路",
        "idempotency_key": "old-note-offer",
    }).status_code == 409


def test_legacy_note_only_and_multiple_offer_block_record(tmp_path):
    client, store, submitted = setup_submitted(tmp_path / "data")
    alias = submitted["id"].removeprefix("opportunity:")
    with store.connect() as connection:
        store._record(connection, "journey_note", {"id": "offer-note-only", "scope_type": "job",
            "scope_id": alias, "kind": "offer", "title": "只有原件", "content": "待核对",
            "created_at": "2026-09-20T00:00:00+00:00"})
    response = record(client, submitted)
    assert response.status_code == 409
    with store.connect() as connection:
        store._record(connection, "offer", {"id": "legacy-a", "opportunity_id": submitted["id"],
            "terms": {}, "status": "pending", "created_at": "2026-09-20T00:00:00+00:00"})
        store._record(connection, "offer", {"id": "legacy-b", "opportunity_id": submitted["id"],
            "terms": {}, "status": "pending", "created_at": "2026-09-21T00:00:00+00:00"})
    read = client.get(f"/api/opportunities/{submitted['id']}/offer")
    assert read.status_code == 409


def test_terms_reject_unknown_shape_and_offer_does_not_follow_opportunity_edit(tmp_path):
    client, _, submitted = setup_submitted(tmp_path / "data")
    invalid = record(client, submitted, terms={**terms(), "role_title": "旧错误字段"})
    assert invalid.status_code == 422
    result = record(client, submitted, "valid-empty").json()
    offer, opportunity = result["offer"], result["opportunity"]
    updated_opportunity = client.post(f"/api/opportunities/{opportunity['id']}", json={
        "company_id": opportunity["company_id"], "title": "修改后的Opportunity岗位",
        "jd": opportunity["jd"], "action_url": opportunity["action_url"],
        "expected_revision": opportunity["revision"], "idempotency_key": "edit-op-title",
    })
    assert updated_opportunity.status_code == 200, updated_opportunity.text
    current = client.get(f"/api/opportunities/{opportunity['id']}/offer/{offer['id']}").json()
    assert current["terms"]["offered_role_title"] == "" and current["terms"]["location"] == ""
