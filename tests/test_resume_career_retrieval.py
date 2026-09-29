"""Resume retrieval searches IDs first and reads only selected current knowledge."""

import pytest
import json
from fastapi.testclient import TestClient

from workbench.core import Invalid
from workbench.app import create_app
from workbench.core import Store
from workbench.opportunity import create_opportunity
from workbench.providers import TestProvider
from workbench.resume_career_retrieval import read_selected_knowledge, search_candidates
from test_wiki_d1 import make_client, make_knowledge, make_project, make_raw
from test_t08_resume_suggestions import resume_fixture
from workbench.core import digest


def test_search_returns_only_ids_then_reads_selected_current_wiki(tmp_path, monkeypatch):
    client, store = make_client(tmp_path)
    target = create_opportunity(store, {
        "company_name": "虚构招聘方 A", "title": "虚构岗位", "jd": "跨团队推动",
        "idempotency_key": "resume-retrieval-target",
    })
    other = create_opportunity(store, {
        "company_name": "虚构招聘方 B", "title": "私有岗位", "jd": "不应读入",
        "idempotency_key": "resume-retrieval-other",
    })
    project = make_project(client, "虚构项目 A")
    raw = make_raw(client, "project", project["id"], "跨团队原文细节只留在 Raw", "rr-raw-a")
    relevant = make_knowledge(
        client, "project", project["id"], [raw["source_ref"]], "rr-wiki-a",
        content="跨团队推动交付，先对齐责任边界。",
    )
    private = make_knowledge(
        client, "opportunity", other["id"], [], "rr-other-private",
        content="跨团队但仅属于机会 B 的私有知识。",
    )
    retired = make_knowledge(
        client, "project", project["id"], [], "rr-retired",
        content="跨团队的已退休旧说法。",
    )
    response = client.post(f"/api/wiki/{retired['id']}", json={
        "knowledge_type": "fact", "content": retired["content"], "tags": [],
        "source_refs": [], "status": "retired", "expected_revision": retired["revision"],
        "idempotency_key": "rr-retire",
    })
    assert response.status_code == 200

    current = store._current
    def refuse_unscoped_wiki_read(connection, kind):
        if kind == "wiki_knowledge":
            raise AssertionError("其他 Opportunity 的 Wiki 不得被整表读入")
        return current(connection, kind)
    monkeypatch.setattr(store, "_current", refuse_unscoped_wiki_read)

    with store.connect(False) as connection:
        candidates = search_candidates(store, connection, target["id"], "跨团队", limit=5)
        assert relevant["id"] in {item["id"] for item in candidates}
        assert private["id"] not in {item["id"] for item in candidates}
        assert retired["id"] not in {item["id"] for item in candidates}
        assert all(set(item) == {"kind", "id", "revision"} for item in candidates)
        assert "原文细节" not in str(candidates)

        selected = read_selected_knowledge(
            store, connection, target["id"], candidates, [relevant["id"]],
        )
        assert len(selected) == 1
        assert selected[0]["content"] == relevant["content"]
        assert selected[0]["source_refs"] == [raw["source_ref"]]
        assert "原文细节" not in str(selected)
        with pytest.raises(Invalid):
            read_selected_knowledge(store, connection, target["id"], candidates, [private["id"]])


def test_ai_can_request_bounded_career_search_before_suggesting_changes(tmp_path):
    provider = TestProvider()
    calls = []

    def complete(payload):
        calls.append(payload)
        if len(calls) == 2:
            return {
                "changes": [], "suggestions": [], "claims": [], "retrieval_requests": [],
                "evidence_requests": [{
                    "source_kind": "raw_material", "source_id": raw["id"],
                    "reason": "核对项目贡献的原始依据",
                }],
            }
        if len(calls) == 3:
            return {
                "changes": [{
                    "change_id": "add-sourced-project", "operation": "add",
                    "section_type": "projects", "proposed_text": "跨团队推动虚构交付。",
                    "source_refs": [{"id": knowledge["id"], "revision": knowledge["revision"]}],
                    "reason": "补上当前稿缺少的项目经历", "requires_fact_check": False,
                }],
                "suggestions": [], "claims": [], "retrieval_requests": [],
            }
        return {
            "changes": [], "suggestions": [], "claims": [],
            "retrieval_requests": [{"need": "缺少跨团队经历证据", "query": "跨团队"}],
        }

    provider.complete = complete
    store = Store(tmp_path / "data", provider)
    client = TestClient(create_app(store), headers={"X-Career-Request": "1"})
    target = create_opportunity(store, {
        "company_name": "虚构公司", "title": "虚构岗位", "jd": "需要跨团队推动经验",
        "idempotency_key": "resume-gap-target",
    })
    started = client.post(f"/api/opportunities/{target['id']}/resume/start", json={
        "expected_opportunity_revision": target["revision"],
        "idempotency_key": "resume-gap-start", "source": {"kind": "blank"},
    })
    assert started.status_code == 200, started.text
    project = client.post("/api/work/projects", json={
        "name": "虚构跨团队项目", "idempotency_key": "resume-gap-project",
    }).json()
    raw = client.post("/api/raw", json={
        "scope_type": "project", "scope_id": project["id"], "source_kind": "manual_text",
        "title": "虚构原文", "content": "PRIVATE_RAW_NOT_FOR_INITIAL_SEARCH",
        "idempotency_key": "resume-gap-raw",
    }).json()
    knowledge = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"],
        "knowledge_type": "fact", "content": "跨团队推动虚构交付。",
        "tags": [], "source_refs": [raw["source_ref"]],
        "idempotency_key": "resume-gap-wiki",
    }).json()
    doc_id = started.json()["document_id"]
    seed = {"instruction": "优化当前稿", "idempotency_key": "resume-gap-plan"}
    preview = client.post(f"/api/resume-documents/{doc_id}/ai-suggest", json=seed)
    assert preview.status_code == 409, preview.text
    confirmation = client.post(f"/api/resume-documents/{doc_id}/ai-suggest", json={
        **seed, "prepared_id": preview.json()["prepared_id"],
        "payload_hash": preview.json()["payload_hash"], "confirm_outbound": True,
    })
    assert confirmation.status_code == 200, confirmation.text
    plan = confirmation.json()
    assert plan["status"] == "needs_retrieval"
    assert knowledge["id"] in [candidate["id"] for candidate in plan["candidates"]]
    assert all(set(candidate) == {"kind", "id", "revision"} for candidate in plan["candidates"])
    assert "PRIVATE_RAW_NOT_FOR_INITIAL_SEARCH" not in str(plan)
    labels = client.get(f"/api/resume-documents/{doc_id}/ai-retrieval-plans/{plan['id']}/labels")
    assert labels.status_code == 200, labels.text
    assert knowledge["content"] in labels.json()["labels"][knowledge["id"]]
    assert "PRIVATE_RAW_NOT_FOR_INITIAL_SEARCH" not in str(labels.json())
    assert client.get(f"/api/resume-documents/{doc_id}/ai-proposals").json() == []
    assert len(calls) == 1

    followup = client.post(f"/api/resume-documents/{doc_id}/ai-suggest", json={
        "instruction": "依据找到的证据提出逐条简历建议",
        "idempotency_key": "resume-gap-followup",
        "retrieval_plan_id": plan["id"],
        "selected_candidate_ids": [knowledge["id"]],
    })
    assert followup.status_code == 409, followup.text
    payload = followup.json()["payload_preview"]
    packet = json.loads(payload["messages"][1]["content"])
    career = [source for source in packet["sources"] if source["purpose"] == "career_wiki"]
    assert len(career) == 1
    assert career[0]["id"] == knowledge["id"]
    assert career[0]["selected_content"]["content"] == knowledge["content"]
    assert "PRIVATE_RAW_NOT_FOR_INITIAL_SEARCH" not in str(payload)
    assert len(calls) == 1  # Preparing the second Preview does not dispatch.

    from_project = client.post(f"/api/resume-documents/{doc_id}/ai-suggest", json={
        "instruction": "读取所选项目的当前知识", "idempotency_key": "resume-gap-project-preview",
        "retrieval_plan_id": plan["id"], "selected_candidate_ids": [project["id"]],
    })
    assert from_project.status_code == 409, from_project.text
    project_packet = json.loads(from_project.json()["payload_preview"]["messages"][1]["content"])
    assert any(source["purpose"] == "career_project" and source["id"] == project["id"] for source in project_packet["sources"])
    assert any(source["purpose"] == "career_wiki" and source["id"] == knowledge["id"] for source in project_packet["sources"])
    assert "PRIVATE_RAW_NOT_FOR_INITIAL_SEARCH" not in str(project_packet)

    generated = client.post(f"/api/resume-documents/{doc_id}/ai-suggest", json={
        "instruction": "依据找到的证据提出逐条简历建议",
        "idempotency_key": "resume-gap-followup",
        "retrieval_plan_id": plan["id"],
        "selected_candidate_ids": [knowledge["id"]],
        "prepared_id": followup.json()["prepared_id"],
        "payload_hash": followup.json()["payload_hash"], "confirm_outbound": True,
    })
    assert generated.status_code == 200, generated.text
    evidence_plan = generated.json()
    assert evidence_plan["status"] == "needs_evidence"
    assert [item["source_id"] for item in evidence_plan["requests"]] == [raw["id"]]
    assert "PRIVATE_RAW_NOT_FOR_INITIAL_SEARCH" not in str(evidence_plan)
    assert client.get(f"/api/resume-documents/{doc_id}").json()["document"]["sections"][2]["items"] == []

    evidence_seed = {
        "instruction": "核对指定原文后再提出逐条建议", "idempotency_key": "resume-gap-evidence",
        "evidence_plan_id": evidence_plan["id"], "selected_evidence_ids": [raw["id"]],
    }
    evidence_preview = client.post(f"/api/resume-documents/{doc_id}/ai-suggest", json=evidence_seed)
    assert evidence_preview.status_code == 409, evidence_preview.text
    evidence_packet = json.loads(evidence_preview.json()["payload_preview"]["messages"][1]["content"])
    raw_sources = [source for source in evidence_packet["sources"] if source["purpose"] == "career_evidence"]
    assert len(raw_sources) == 1 and raw_sources[0]["id"] == raw["id"]
    assert raw_sources[0]["selected_content"]["content"] == "PRIVATE_RAW_NOT_FOR_INITIAL_SEARCH"
    assert len(calls) == 2
    generated = client.post(f"/api/resume-documents/{doc_id}/ai-suggest", json={
        **evidence_seed, "prepared_id": evidence_preview.json()["prepared_id"],
        "payload_hash": evidence_preview.json()["payload_hash"], "confirm_outbound": True,
    })
    assert generated.status_code == 200, generated.text
    proposal = generated.json()
    assert proposal["changes"][0]["operation"] == "add"
    assert client.get(f"/api/resume-documents/{doc_id}").json()["document"]["sections"][2]["items"] == []
    accepted = client.post(
        f"/api/resume-documents/{doc_id}/ai-proposals/{proposal['id']}/changes/add-sourced-project/resolve",
        json={"decision": "accept", "proposed_text": "跨团队推动虚构交付（已核对）。"},
    )
    assert accepted.status_code == 200, accepted.text
    project_items = accepted.json()["document"]["document"]["sections"][2]["items"]
    assert len(project_items) == 1
    assert project_items[0]["bullets"][0]["content"] == "跨团队推动虚构交付（已核对）。"
    assert any(ref["source_id"] == knowledge["id"] for ref in accepted.json()["document"]["document"]["meta"]["source_refs"])
    assert len(calls) == 3


def test_explicit_rewrite_and_delete_are_resolved_one_at_a_time(tmp_path):
    provider = TestProvider()
    calls = []

    def complete(payload):
        calls.append(payload)
        return {
            "changes": [
                {"change_id": "rewrite-skill", "operation": "rewrite", "item_id": "t08-skill",
                 "field": "content", "before_hash": digest("Python"),
                 "proposed_text": "Python 与自动化测试", "source_refs": [],
                 "reason": "表达更清楚", "requires_fact_check": False},
                {"change_id": "delete-project", "operation": "delete", "item_id": "t08-project",
                 "before_hash": digest(project), "source_refs": [],
                 "reason": "与本岗位无关", "requires_fact_check": False},
            ], "suggestions": [], "claims": [], "retrieval_requests": [],
        }

    client, _, before = resume_fixture(tmp_path, provider)
    project = next(section for section in before["document"]["sections"] if section["type"] == "projects")["items"][0]
    provider.complete = complete
    doc_id = before["document_id"]
    seed = {"instruction": "逐条建议", "idempotency_key": "per-change-ops"}
    preview = client.post(f"/api/resume-documents/{doc_id}/ai-suggest", json=seed).json()
    generated = client.post(f"/api/resume-documents/{doc_id}/ai-suggest", json={
        **seed, "prepared_id": preview["prepared_id"],
        "payload_hash": preview["payload_hash"], "confirm_outbound": True,
    })
    assert generated.status_code == 200, generated.text
    proposal = generated.json()
    assert proposal["resolution_mode"] == "per_change"
    bulk = client.post(f"/api/resume-documents/{doc_id}/ai-proposals/{proposal['id']}/resolve", json={
        "decision": "accept", "changes": [],
    })
    assert bulk.status_code == 409

    first = client.post(
        f"/api/resume-documents/{doc_id}/ai-proposals/{proposal['id']}/changes/rewrite-skill/resolve",
        json={"decision": "accept", "proposed_text": "Python 与隔离测试"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["proposal"]["status"] == "pending"
    assert first.json()["document"]["document"]["sections"][0]["items"][0]["content"] == "Python 与隔离测试"
    second = client.post(
        f"/api/resume-documents/{doc_id}/ai-proposals/{proposal['id']}/changes/delete-project/resolve",
        json={"decision": "accept"},
    )
    assert second.status_code == 200, second.text
    assert second.json()["proposal"]["status"] == "accepted"
    assert next(section for section in second.json()["document"]["document"]["sections"] if section["type"] == "projects")["items"] == []
    assert second.json()["document"]["revision"] == before["revision"] + 2
    assert len(calls) == 1
