"""T02 Research identity, manifest and proposal safety over synthetic data."""
import json

import pytest
from fastapi.testclient import TestClient

from workbench import interview, research
from workbench import research_store as research_store_module
from workbench.app import create_app
from workbench.core import Store
from workbench.opportunity import create_opportunity
from workbench.providers import TestProvider
from search_fakes import FakeSearchProvider


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


def client_for(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    return TestClient(create_app(store), headers=HEADERS), store


def make_opportunity(store, company, key):
    return create_opportunity(store, {
        "company_name": company, "title": "T02岗位", "jd": "T02 JD",
        "idempotency_key": key,
    })


def ai_confirm(client, path, body):
    prepared = client.post(path, json=body)
    if prepared.status_code == 409 and prepared.json().get("status") == "context_confirmation_required":
        value = prepared.json()
        return client.post(path, json={**body, "prepared_id": value["prepared_id"],
                                      "payload_hash": value["payload_hash"], "confirm_outbound": True})
    return prepared


def research_confirm(client, opportunity_id, key):
    path = f"/api/opportunities/{opportunity_id}/research/update"
    body = {"idempotency_key": key}
    first = client.post(path, json=body)
    assert first.status_code == 409 and first.json().get("status") == "search_confirmation_required"
    prepared = client.post(path, json={**body, "search_confirmed": True})
    assert prepared.status_code == 409, prepared.text
    value = prepared.json()
    return client.post(path, json={**body, "search_confirmed": True,
                                  "prepared_id": value["prepared_id"],
                                  "payload_hash": value["payload_hash"],
                                  "confirm_outbound": True})


def test_research_is_shared_and_alias_owner_never_creates_second_record(tmp_path):
    client, store = client_for(tmp_path)
    first = make_opportunity(store, "同一虚构公司", "op-1")
    second = make_opportunity(store, "同一虚构公司", "op-2")
    saved = client.post(f"/api/opportunities/{first['id']}/research/items", json={
        "scope": "company", "category": "company_business", "classification": "unknown",
        "content": "同一份虚构公司研究", "expected_revision": 0, "idempotency_key": "company-item",
    })
    assert saved.status_code == 200, saved.text
    overview = client.get(f"/api/opportunities/{second['id']}/research-overview").json()
    assert overview["company"]["items"][0]["content"] == "同一份虚构公司研究"

    alias_id = next(
        item for item in research_store_module.legacy_ids("opportunity_research", first["id"])
        if item != research_store_module.research_id("opportunity_research", first["id"])
    )
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO current VALUES(?,?,?,?)",
            (alias_id, "opportunity_research", 0, json.dumps({
                "id": alias_id, "opportunity_id": first["id"],
                "items": [{"category": "role", "content": "旧格式岗位研究"}], "revision": 0,
            })),
        )
    research_view = client.get(f"/api/opportunities/{first['id']}/research-overview")
    assert research_view.status_code == 200
    assert research_view.json()["opportunity"]["id"] == alias_id
    legacy_item = research_view.json()["opportunity"]["items"][0]
    assert legacy_item["classification"] == "unknown" and legacy_item["source_refs"] == []
    assert client.get(f"/api/opportunities/{first['id']}/research-overview").json()["opportunity"]["revision"] == 0
    duplicate_company_id = "company_research:legacy-duplicate"
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO current VALUES(?,?,?,?)",
            (duplicate_company_id, "company_research", 0, json.dumps({
                "id": duplicate_company_id, "company_id": first["company_id"], "items": [], "revision": 0,
            })),
        )
    research_view = client.get(f"/api/opportunities/{second['id']}/research-overview")
    assert research_view.status_code == 409
    assert "research_owner_conflict" in research_view.text


def test_research_update_manifest_rejects_changed_target_and_reject_is_always_available(tmp_path, monkeypatch):
    client, store = client_for(tmp_path)
    opportunity = make_opportunity(store, "研究虚构公司", "research-1")
    store.search_provider = FakeSearchProvider([{
        "url": "https://example.test/t02", "title": "虚构来源",
        "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])
    created = research_confirm(client, opportunity["id"], "research-proposal-1").json()
    assert created["manifest"]["manifest_version"] == 1
    assert created["manifest"]["target"]["id"] == opportunity["id"]
    changed = client.post(f"/api/opportunities/{opportunity['id']}", json={
        "title": opportunity["title"], "jd": "T02 JD 已变更",
        "expected_revision": opportunity["revision"], "idempotency_key": "op-update-1",
    })
    assert changed.status_code == 200, changed.text
    listed = client.get(f"/api/opportunities/{opportunity['id']}/research-proposals").json()
    assert listed[0]["stale"] is True and "target_changed" in listed[0]["stale_reason"]
    accepted = client.post(
        f"/api/opportunities/{opportunity['id']}/research-proposals/{created['id']}/resolve",
        json={"decision": "accept"},
    )
    assert accepted.status_code == 409 and any(code in accepted.text for code in ("target_changed", "source_changed"))
    assert not client.get(f"/api/opportunities/{opportunity['id']}/research-overview").json()["items"]
    rejected = client.post(
        f"/api/opportunities/{opportunity['id']}/research-proposals/{created['id']}/resolve",
        json={"decision": "reject"},
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"


def test_research_proposal_rejects_company_switch_and_preserves_new_company(tmp_path, monkeypatch):
    client, store = client_for(tmp_path)
    first = make_opportunity(store, "公司 A（虚构）", "company-switch-a")
    second = make_opportunity(store, "公司 B（虚构）", "company-switch-b")
    saved = client.post(f"/api/opportunities/{second['id']}/research/items", json={
        "scope": "company", "category": "company_business", "classification": "unknown",
        "content": "公司 B 的既有研究不能被 A 的提案覆盖", "expected_revision": 0,
        "idempotency_key": "company-b-existing",
    })
    assert saved.status_code == 200, saved.text
    store.search_provider = FakeSearchProvider([{
        "url": "https://example.test/company-a", "title": "A 来源",
        "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])
    proposal = research_confirm(client, first["id"], "company-switch-proposal").json()
    moved = client.post(f"/api/opportunities/{first['id']}", json={
        "company_id": second["company_id"], "title": first["title"], "jd": first["jd"],
        "expected_revision": first["revision"], "idempotency_key": "company-switch",
    })
    assert moved.status_code == 200, moved.text
    accepted = client.post(
        f"/api/opportunities/{first['id']}/research-proposals/{proposal['id']}/resolve",
        json={"decision": "accept"},
    )
    assert accepted.status_code == 409 and "target_changed" in accepted.text
    current_b = client.get(f"/api/opportunities/{second['id']}/research-overview").json()
    assert [item["content"] for item in current_b["company"]["items"]] == [
        "公司 B 的既有研究不能被 A 的提案覆盖"
    ]


def test_old_proposal_without_manifest_can_be_rejected_but_not_accepted(tmp_path):
    client, store = client_for(tmp_path)
    opportunity = make_opportunity(store, "旧提案虚构公司", "legacy-proposal")
    with store.connect() as connection:
        store._record(connection, "research_proposal", {
            "id": "legacy-research-proposal", "opportunity_id": opportunity["id"],
            "company_id": opportunity["company_id"], "company_items": [], "opportunity_items": [],
            "expected_company_revision": 0, "expected_opportunity_revision": 0,
            "status": "pending", "created_at": "2026-09-19T00:00:00+00:00",
        })
    accepted = client.post(
        f"/api/opportunities/{opportunity['id']}/research-proposals/legacy-research-proposal/resolve",
        json={"decision": "accept"},
    )
    assert accepted.status_code == 409 and "proposal_requires_regeneration" in accepted.text
    rejected = client.post(
        f"/api/opportunities/{opportunity['id']}/research-proposals/legacy-research-proposal/resolve",
        json={"decision": "reject"},
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"


def test_research_accept_is_atomic_when_second_owner_write_fails(tmp_path, monkeypatch):
    client, store = client_for(tmp_path)
    opportunity = make_opportunity(store, "原子性虚构公司", "atomic-1")
    store.search_provider = FakeSearchProvider([{
        "url": "https://example.test/atomic", "title": "来源", "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])
    proposal = research_confirm(client, opportunity["id"], "atomic-proposal").json()
    original_save = store._save
    calls = {"research": 0}

    def fail_second(connection, kind, obj, expected):
        if kind in {"company_research", "opportunity_research"}:
            calls["research"] += 1
            if calls["research"] == 2:
                raise RuntimeError("synthetic second Research write failure")
        return original_save(connection, kind, obj, expected)

    monkeypatch.setattr(store, "_save", fail_second)
    with pytest.raises(RuntimeError):
        client.post(
            f"/api/opportunities/{opportunity['id']}/research-proposals/{proposal['id']}/resolve",
            json={"decision": "accept"},
        )
    overview = client.get(f"/api/opportunities/{opportunity['id']}/research-overview").json()
    assert overview["company"]["items"] == [] and overview["opportunity"]["items"] == []
    assert client.get(f"/api/opportunities/{opportunity['id']}/research-proposals").json()[0]["status"] == "pending"


def test_research_dependency_change_is_stale_and_reject_does_not_bump(tmp_path, monkeypatch):
    client, store = client_for(tmp_path)
    opportunity = make_opportunity(store, "Research 来源变化虚构公司", "research-source-change")
    initial = client.post(f"/api/opportunities/{opportunity['id']}/research/items", json={
        "scope": "opportunity", "category": "role", "classification": "unknown",
        "content": "提案创建前的既有岗位研究", "expected_revision": 0,
        "idempotency_key": "research-source-initial",
    })
    assert initial.status_code == 200
    store.search_provider = FakeSearchProvider([{
        "url": "https://example.test/research-source", "title": "岗位来源",
        "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])
    proposal = research_confirm(client, opportunity["id"], "research-source-proposal").json()
    changed = client.post(f"/api/opportunities/{opportunity['id']}/research/items", json={
        "scope": "opportunity", "category": "role", "classification": "unknown",
        "content": "提案生成后新增的岗位研究", "expected_revision": 1,
        "idempotency_key": "research-source-changed",
    })
    assert changed.status_code == 200
    listed = client.get(f"/api/opportunities/{opportunity['id']}/research-proposals").json()
    assert listed[0]["stale"] is True and "source_changed" in listed[0]["stale_reason"]
    accepted = client.post(
        f"/api/opportunities/{opportunity['id']}/research-proposals/{proposal['id']}/resolve",
        json={"decision": "accept"},
    )
    assert accepted.status_code == 409 and "source_changed" in accepted.text
    before_reject = client.get(f"/api/opportunities/{opportunity['id']}/research-overview").json()
    rejected = client.post(
        f"/api/opportunities/{opportunity['id']}/research-proposals/{proposal['id']}/resolve",
        json={"decision": "reject"},
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    after_reject = client.get(f"/api/opportunities/{opportunity['id']}/research-overview").json()
    assert after_reject["opportunity"]["revision"] == before_reject["opportunity"]["revision"]


def test_interview_and_research_routes_share_one_opportunity_research_identity(tmp_path):
    from test_interview import confirm
    from test_communication import setup_submitted

    client, store, submitted = setup_submitted(tmp_path / "interview")
    created = confirm(client, submitted).json()
    interview_session, opportunity = created["interview"], created["opportunity"]
    raw = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{interview_session['id']}/raw",
        json={"content": "虚构面试 Raw", "expected_revision": 0, "idempotency_key": "raw-t02"},
    )
    assert raw.status_code == 200, raw.text
    proposal = ai_confirm(client,
        f"/api/opportunities/{opportunity['id']}/interviews/{interview_session['id']}/generate-research-patch",
        {"communication_ids": [], "wiki_ids": [], "idempotency_key": "patch-t02"})
    assert proposal.status_code == 200, proposal.text
    patch = proposal.json()["proposal"]
    overview = client.get(f"/api/opportunities/{opportunity['id']}/research-overview").json()
    interview_research = client.get(f"/api/opportunities/{opportunity['id']}/research").json()
    assert patch["target_id"] == interview_research["id"] == overview["opportunity"]["id"]
    assert patch["manifest"]["target"]["id"] == interview_research["id"]


def test_manual_research_is_idempotent_and_resume_proposal_binds_research_and_jd(tmp_path):
    client, store = client_for(tmp_path)
    opportunity = make_opportunity(store, "简历研究虚构公司", "resume-research")
    item = {
        "scope": "company", "category": "company_business", "classification": "unknown",
        "content": "简历提案读取的虚构公司研究", "expected_revision": 0,
        "idempotency_key": "manual-research-1",
    }
    first = client.post(f"/api/opportunities/{opportunity['id']}/research/items", json=item)
    second = client.post(f"/api/opportunities/{opportunity['id']}/research/items", json=item)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    started = client.post(f"/api/opportunities/{opportunity['id']}/resume/start", json={
        "expected_opportunity_revision": opportunity["revision"],
        "idempotency_key": "resume-start-t02", "source": {"kind": "blank"},
    })
    assert started.status_code == 200, started.text
    document_id = started.json()["document_id"]
    resume_path = f"/api/resume-documents/{document_id}/ai-suggest"
    resume_body = {"instruction": "依据当前岗位研究给出虚构建议", "idempotency_key": "resume-ai-t02"}
    prepared_resume = client.post(resume_path, json=resume_body)
    assert prepared_resume.status_code == 409, prepared_resume.text
    resume_info = prepared_resume.json()
    proposal = client.post(resume_path, json={**resume_body, "prepared_id": resume_info["prepared_id"],
                                              "payload_hash": resume_info["payload_hash"],
                                              "confirm_outbound": True})
    assert proposal.status_code == 200, proposal.text
    proposal_body = proposal.json()
    manifest = proposal_body["manifest"]
    assert manifest["target"]["id"] == document_id
    research_dependencies = [x for x in manifest["dependencies"] if x["kind"] == "company_research"]
    assert research_dependencies and not research_dependencies[0].get("expected_absent", False)
    changed = client.post(f"/api/opportunities/{opportunity['id']}", json={
        "title": opportunity["title"], "jd": "T02 JD 发生新变化",
        "expected_revision": opportunity["revision"], "idempotency_key": "resume-op-update",
    })
    assert changed.status_code == 200, changed.text
    listed = client.get(f"/api/resume-documents/{document_id}/ai-proposals").json()
    assert listed[0]["stale"] is True
    accepted = client.post(
        f"/api/resume-documents/{document_id}/ai-proposals/{proposal_body['id']}/resolve",
        json={"decision": "accept"},
    )
    assert accepted.status_code == 409 and any(code in accepted.text for code in ("target_changed", "source_changed"))
    rejected = client.post(
        f"/api/resume-documents/{document_id}/ai-proposals/{proposal_body['id']}/resolve",
        json={"decision": "reject"},
    )
    assert rejected.status_code == 200 and rejected.json()["proposal"]["status"] == "rejected"


def test_web_research_and_interview_patch_work_in_both_orders(tmp_path, monkeypatch):
    from test_interview import confirm
    from test_communication import setup_submitted

    fake_search = FakeSearchProvider([{
        "url": "https://example.test/order", "title": "顺序测试来源",
        "retrieved_at": "2026-09-19T00:00:00+00:00",
    }])

    first_client, first_store, submitted = setup_submitted(tmp_path / "web-first", "web-first")
    first_store.search_provider = fake_search
    first_interview = confirm(first_client, submitted).json()
    first_opp = first_interview["opportunity"]
    first_raw = first_client.put(
        f"/api/opportunities/{first_opp['id']}/interviews/{first_interview['interview']['id']}/raw",
        json={"content": "网页优先顺序的虚构面试 Raw", "expected_revision": 0, "idempotency_key": "web-first-raw"},
    )
    assert first_raw.status_code == 200
    web_proposal = research_confirm(first_client, first_opp["id"], "web-first-research").json()
    assert first_client.post(
        f"/api/opportunities/{first_opp['id']}/research-proposals/{web_proposal['id']}/resolve",
        json={"decision": "accept"},
    ).status_code == 200
    patch = ai_confirm(first_client,
        f"/api/opportunities/{first_opp['id']}/interviews/{first_interview['interview']['id']}/generate-research-patch",
        {"communication_ids": [], "wiki_ids": [], "idempotency_key": "web-first-patch"}).json()["proposal"]
    patched = first_client.put(f"/api/opportunities/{first_opp['id']}/research-patches/{patch['id']}", json={
        "items": [{"category": "team", "content": "网页优先后确认的面试团队信息"}],
        "expected_revision": patch["revision"], "idempotency_key": "web-first-patch-edit",
    })
    assert patched.status_code == 200
    assert first_client.post(
        f"/api/opportunities/{first_opp['id']}/research-patches/{patch['id']}/resolve",
        json={"decision": "accept", "expected_revision": patched.json()["revision"], "idempotency_key": "web-first-patch-accept"},
    ).status_code == 200
    current = first_client.get(f"/api/opportunities/{first_opp['id']}/research").json()
    assert {item["content"] for item in current["items"]} >= {"网页优先后确认的面试团队信息"}
    started = first_client.post(f"/api/opportunities/{first_opp['id']}/resume/start", json={
        "expected_opportunity_revision": first_client.get(f"/api/opportunities/{first_opp['id']}").json()["revision"],
        "idempotency_key": "web-first-resume", "source": {"kind": "blank"},
    })
    assert started.status_code == 200
    resume_path = f"/api/resume-documents/{started.json()['document_id']}/ai-suggest"
    resume_body = {"instruction": "读取当前岗位研究", "idempotency_key": "web-first-resume-ai"}
    resume_prepared = first_client.post(resume_path, json=resume_body).json()
    resume_proposal = first_client.post(resume_path, json={**resume_body, "prepared_id": resume_prepared["prepared_id"],
                                                           "payload_hash": resume_prepared["payload_hash"],
                                                           "confirm_outbound": True})
    assert resume_proposal.status_code == 200
    assert any(item["kind"] == "opportunity_research" for item in resume_proposal.json()["manifest"]["dependencies"])

    second_client, second_store, submitted = setup_submitted(tmp_path / "patch-first", "patch-first")
    second_store.search_provider = fake_search
    second_interview = confirm(second_client, submitted).json()
    second_opp = second_interview["opportunity"]
    raw = second_client.put(
        f"/api/opportunities/{second_opp['id']}/interviews/{second_interview['interview']['id']}/raw",
        json={"content": "面试优先顺序的虚构 Raw", "expected_revision": 0, "idempotency_key": "patch-first-raw"},
    )
    assert raw.status_code == 200
    patch = ai_confirm(second_client,
        f"/api/opportunities/{second_opp['id']}/interviews/{second_interview['interview']['id']}/generate-research-patch",
        {"communication_ids": [], "wiki_ids": [], "idempotency_key": "patch-first-patch"}).json()["proposal"]
    assert second_client.post(
        f"/api/opportunities/{second_opp['id']}/research-patches/{patch['id']}/resolve",
        json={"decision": "accept", "expected_revision": patch["revision"], "idempotency_key": "patch-first-accept"},
    ).status_code == 200
    web_proposal = research_confirm(second_client, second_opp["id"], "patch-first-research").json()
    assert second_client.post(
        f"/api/opportunities/{second_opp['id']}/research-proposals/{web_proposal['id']}/resolve",
        json={"decision": "accept"},
    ).status_code == 200
    current = second_client.get(f"/api/opportunities/{second_opp['id']}/research").json()
    assert len(current["items"]) >= 2


def test_interview_patch_sources_stale_when_selected_communication_or_wiki_changes(tmp_path):
    from test_interview import confirm
    from test_communication import setup_submitted

    client, store, submitted = setup_submitted(tmp_path / "selected-source")
    communication = client.post(f"/api/opportunities/{submitted['id']}/communications", json={
        "type": "text", "occurred_on": "2026-09-19", "content": "初始沟通内容",
        "idempotency_key": "source-stale-communication",
    })
    assert communication.status_code == 200, communication.text
    event = communication.json()
    created = confirm(client, submitted).json()
    opportunity = created["opportunity"]
    interview_id = created["interview"]["id"]
    raw = client.put(
        f"/api/opportunities/{opportunity['id']}/interviews/{interview_id}/raw",
        json={"content": "来源 stale 测试 Raw", "expected_revision": 0, "idempotency_key": "source-stale-raw"},
    )
    assert raw.status_code == 200
    source = client.post("/api/knowledge/sources", json={
        "title": "来源 stale Wiki 原文", "content": "初始 Wiki 内容", "source_type": "text",
        "locator": "", "scope_type": "personal", "scope_id": "", "idempotency_key": "source-stale-wiki-source",
    })
    assert source.status_code == 200, source.text
    candidate = client.post("/api/knowledge/candidates", json={
        "source_ids": [source.json()["id"]], "entry_type": "project", "title": "来源 stale Wiki 条目",
        "content": "初始 Wiki 内容", "scope_type": "personal", "scope_id": "",
        "idempotency_key": "source-stale-wiki-candidate",
    })
    assert candidate.status_code == 200, candidate.text
    resolved = client.post(f"/api/knowledge/candidates/{candidate.json()['id']}/resolve", json={
        "decision": "confirm", "expected_revision": candidate.json()["revision"],
        "idempotency_key": "source-stale-wiki-confirm",
    })
    assert resolved.status_code == 200, resolved.text
    wiki_id = resolved.json()["entry_id"]
    wiki = client.get("/api/knowledge").json()["entries"]
    wiki_entry = next(item for item in wiki if item["id"] == wiki_id)

    communication_patch = ai_confirm(client,
        f"/api/opportunities/{opportunity['id']}/interviews/{interview_id}/generate-research-patch",
        {"communication_ids": [event["id"]], "wiki_ids": [],
         "idempotency_key": "source-stale-communication-patch"}).json()["proposal"]
    changed_communication = client.put(
        f"/api/opportunities/{opportunity['id']}/communications/{event['id']}",
        json={"type": "text", "occurred_on": event["occurred_on"], "content": "更正后的沟通内容",
              "expected_revision": event["revision"], "idempotency_key": "source-stale-communication-edit"},
    )
    assert changed_communication.status_code == 200
    listed = client.get(f"/api/opportunities/{opportunity['id']}/research-patches").json()
    communication_view = next(item for item in listed if item["id"] == communication_patch["id"])
    assert communication_view["stale"] is True and "source_changed" in communication_view["stale_reason"]
    assert client.post(
        f"/api/opportunities/{opportunity['id']}/research-patches/{communication_patch['id']}/resolve",
        json={"decision": "accept", "expected_revision": 0, "idempotency_key": "source-stale-communication-accept"},
    ).status_code == 409
    assert client.post(
        f"/api/opportunities/{opportunity['id']}/research-patches/{communication_patch['id']}/resolve",
        json={"decision": "reject", "expected_revision": 0, "idempotency_key": "source-stale-communication-reject"},
    ).status_code == 200

    wiki_patch = ai_confirm(client,
        f"/api/opportunities/{opportunity['id']}/interviews/{interview_id}/generate-research-patch",
        {"communication_ids": [], "wiki_ids": [wiki_id],
         "idempotency_key": "source-stale-wiki-patch"}).json()["proposal"]
    changed_wiki = client.post(f"/api/knowledge/entries/{wiki_id}", json={
        "title": wiki_entry["title"], "content": "更正后的 Wiki 内容", "entry_type": wiki_entry["entry_type"],
        "status": "active", "expected_revision": wiki_entry["revision"],
    })
    assert changed_wiki.status_code == 200, changed_wiki.text
    listed = client.get(f"/api/opportunities/{opportunity['id']}/research-patches").json()
    wiki_view = next(item for item in listed if item["id"] == wiki_patch["id"])
    assert wiki_view["stale"] is True and "source_changed" in wiki_view["stale_reason"]
    assert client.post(
        f"/api/opportunities/{opportunity['id']}/research-patches/{wiki_patch['id']}/resolve",
        json={"decision": "reject", "expected_revision": 0, "idempotency_key": "source-stale-wiki-reject"},
    ).status_code == 200
