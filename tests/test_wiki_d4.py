"""D4 Cognition tests use isolated v6 stores and TestProvider only."""
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


def _harness(tmp_path, result=None):
    provider = TestProvider()
    store = Store(tmp_path / "data", provider)
    client = TestClient(
        create_app(store, allow_retired_cognition_compiler=True), base_url="http://127.0.0.1",
        headers={"X-Career-Request": "1"},
    )
    calls = []

    def complete(payload):
        calls.append(deepcopy(payload))
        return deepcopy(result if result is not None else {"patches": []})

    provider.complete = complete
    return client, store, calls


def _project(client, name):
    response = client.post("/api/work/projects", json={
        "name": name, "idempotency_key": "project-" + name,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _employment(client, company):
    response = client.post("/api/employments", json={
        "company": company, "role": "虚构角色", "idempotency_key": "employment-" + company,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _opportunity(client):
    response = client.post("/api/opportunities", json={
        "company_name": "D4 虚构公司", "title": "D4 虚构岗位",
        "jd": "完全虚构，仅用于隔离测试。", "idempotency_key": "d4-test-opportunity",
    })
    assert response.status_code == 200, response.text
    return response.json()


def _wiki(client, scope_type, scope_id, content, source_refs=None):
    response = client.post("/api/wiki", json={
        "scope_type": scope_type, "scope_id": scope_id,
        "knowledge_type": "observation", "content": content,
        "tags": ["#d4-fixture"], "source_refs": source_refs or [],
        "idempotency_key": "wiki-" + content,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _raw(client, project, title, content):
    response = client.post("/api/raw", json={
        "scope_type": "project", "scope_id": project["id"],
        "source_kind": "manual_text", "title": title, "content": content,
        "idempotency_key": "raw-" + title,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _source_ref(item):
    from workbench.core import digest
    return {"kind": "wiki_knowledge", "id": item["id"],
            "revision": item["revision"], "hash": digest(item)}


def _seed_cognition(client, content, refs, key="seed-cognition"):
    response = client.post("/api/wiki", json={
        "scope_type": "cognition", "scope_id": "",
        "knowledge_type": "hypothesis", "content": content,
        "tags": ["#d4-fixture"], "source_refs": [_source_ref(item) for item in refs],
        "idempotency_key": key,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _resolve(client, proposal, patch, decision, key, *, content=None):
    body = {"decision": decision, "idempotency_key": key}
    if content is not None:
        body["content"] = content
    return client.post(
        f"/api/wiki/compiler/proposals/{proposal['id']}/patches/{patch['id']}/resolve",
        json=body,
    )


def _prepare(client, experiences, key="d4-prepare"):
    return client.post("/api/wiki/cognition/compiler/prepare", json={
        "selected_experiences": experiences, "idempotency_key": key,
    })


def _execute(client, prepared, key="d4-prepare"):
    return client.post("/api/wiki/cognition/compiler/execute", json={
        "selected_experiences": prepared["selected_experiences"],
        "idempotency_key": key,
        "prepared_id": prepared["prepared_id"],
        "payload_hash": prepared["payload_hash"],
        "confirm_outbound": True,
    })


def _add(content, *knowledge_ids):
    return {
        "operation": "add", "knowledge_type": "hypothesis", "content": content,
        "tags": ["#长期认知"],
        "source_refs": [{"knowledge_id": item} for item in knowledge_ids],
        "reason": "至少两个不同经历中出现相似模式。",
    }


def _records(store, kind):
    with store.connect(False) as connection:
        return store._records(connection, kind)


def test_one_experience_or_two_knowledge_items_in_one_project_cannot_form_cognition(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client, "D4 单项目虚构经历")
    _wiki(client, "project", project["id"], "先划边界，再拆任务。")
    _wiki(client, "project", project["id"], "先定义边界，再开始开发。")

    one = _prepare(client, [{"type": "project", "id": project["id"]}])
    duplicate = _prepare(client, [
        {"type": "project", "id": project["id"]},
        {"type": "project", "id": project["id"]},
    ], "d4-duplicate-experience")

    assert one.status_code == 422
    assert duplicate.status_code == 422
    assert calls == []
    assert not _records(store, "wiki_compiler_proposal")
    store.shutdown()


@pytest.mark.parametrize("experience_types", [
    ("project", "project"), ("project", "employment"), ("employment", "employment"),
])
def test_two_distinct_project_and_employment_combinations_prepare(tmp_path, experience_types):
    client, store, calls = _harness(tmp_path)
    experiences = []
    for index, kind in enumerate(experience_types):
        if kind == "project":
            obj = _project(client, f"D4 经历 {index}")
            identifier = obj["id"]
        else:
            obj = _employment(client, f"D4 虚构公司 {index}")
            identifier = obj["id"]
        _wiki(client, kind, identifier, f"第 {index} 段经历的虚构观察。")
        experiences.append({"type": kind, "id": identifier})

    response = _prepare(client, experiences, "d4-combination")

    assert response.status_code == 200, response.text
    body = response.json()
    assert calls == [], "Prepare 只能生成预览，不得调用 Provider"
    assert len(body["readable_context"]["selected_experiences"]) == 2
    assert {item["type"] for item in body["readable_context"]["selected_experiences"]} == set(experience_types)
    assert "raw" not in body["readable_context"]
    assert body["preview"]["other_career_data_included"] is False
    with store.connect(False) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
    store.shutdown()


@pytest.mark.parametrize("experience_types", [
    ("project", "project"), ("project", "employment"), ("employment", "employment"),
])
def test_two_independent_experiences_can_support_and_save_a_candidate(tmp_path, experience_types):
    client, store, calls = _harness(tmp_path)
    experiences, sources_by_index = [], []
    for index, kind in enumerate(experience_types):
        obj = _project(client, f"D4 可支持经历 {index}") if kind == "project" else _employment(client, f"D4 可支持公司 {index}")
        knowledge = _wiki(client, kind, obj["id"], f"独立经历 {index} 的虚构观察。")
        experiences.append({"type": kind, "id": obj["id"]})
        sources_by_index.append(knowledge)
    provider = store.provider
    provider.complete = lambda payload: calls.append(deepcopy(payload)) or {
        "patches": [_add("两个经历都出现先明确边界再开始实施。",
                         *(item["id"] for item in sources_by_index))]
    }

    preview = _prepare(client, experiences, "d4-supported-candidate")
    assert preview.status_code == 200, preview.text
    assert calls == []
    result = _execute(client, preview.json(), "d4-supported-candidate")
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "proposal_pending"
    assert len(calls) == 1
    assert client.get("/api/wiki/cognition/workspace").json()["knowledge"] == []

    proposal = result.json()["proposal"]
    accepted = _resolve(client, proposal, proposal["patches"][0], "accept", "d4-accept-supported")
    assert accepted.status_code == 200, accepted.text
    saved = client.get("/api/wiki/cognition/workspace").json()["knowledge"]
    assert len(saved) == 1
    assert saved[0]["content"] == "两个经历都出现先明确边界再开始实施。"
    assert {item["id"] for item in saved[0]["supporting_experiences"]} == {
        item["id"] for item in experiences
    }
    store.shutdown()


def test_context_excludes_raw_and_private_scopes_and_candidate_is_pending_until_accepted(tmp_path):
    client, store, calls = _harness(tmp_path)
    project_a = _project(client, "D4 项目甲")
    project_b = _project(client, "D4 项目乙")
    wiki_a = _wiki(client, "project", project_a["id"], "先明确模块边界，再拆工作。")
    wiki_b = _wiki(client, "project", project_b["id"], "先划清系统边界，再分解任务。")
    raw = client.post("/api/raw", json={
        "scope_type": "project", "scope_id": project_a["id"],
        "source_kind": "manual_text", "title": "D4 虚构原文",
        "content": "D4 RAW MUST NOT BE SENT: fabricated detail.",
        "idempotency_key": "d4-no-raw",
    }).json()
    opportunity = _opportunity(client)
    _wiki(client, "opportunity", opportunity["id"], "不应进入机会资料。")
    experience_ids = [
        {"type": "project", "id": project_a["id"]},
        {"type": "project", "id": project_b["id"]},
    ]
    provider_result = {"patches": [_add("可能先建立边界再拆解任务。", wiki_a["id"], wiki_b["id"])]}
    provider = store.provider
    provider.complete = lambda payload: calls.append(deepcopy(payload)) or deepcopy(provider_result)

    preview = _prepare(client, experience_ids, "d4-cross-project")

    assert preview.status_code == 200, preview.text
    assert calls == []
    preview_text = json.dumps(preview.json(), ensure_ascii=False)
    assert "D4 RAW MUST NOT BE SENT" not in preview_text
    assert "不应进入机会资料" not in preview_text
    assert "先明确模块边界" in preview_text and "先划清系统边界" in preview_text

    execute = _execute(client, preview.json(), "d4-cross-project")
    assert execute.status_code == 200, execute.text
    assert execute.json()["status"] == "proposal_pending"
    assert len(calls) == 1
    packet = json.loads(calls[0]["messages"][1]["content"])
    assert packet["task"] == "synthesize_long_term_cognition"
    assert "raw" not in packet
    assert {item["id"] for item in packet["selected_experiences"]} == {project_a["id"], project_b["id"]}
    assert all(set(item) == {"knowledge_id", "type", "content", "tags"}
               for experience in packet["selected_experiences"]
               for item in experience["current_knowledge"])
    assert "D4 RAW MUST NOT BE SENT" not in json.dumps(packet, ensure_ascii=False)
    assert opportunity["id"] not in json.dumps(packet, ensure_ascii=False)
    workspace = client.get("/api/wiki/cognition/workspace")
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["knowledge"] == []

    proposal = execute.json()["proposal"]
    patch = proposal["patches"][0]
    assert patch["status"] == "pending"
    accepted = client.post(
        f"/api/wiki/compiler/proposals/{proposal['id']}/patches/{patch['id']}/resolve",
        json={"decision": "accept", "idempotency_key": "d4-accept-one"},
    )
    assert accepted.status_code == 200, accepted.text
    workspace = client.get("/api/wiki/cognition/workspace").json()
    assert len(workspace["knowledge"]) == 1
    cognition = workspace["knowledge"][0]
    assert cognition["content"] == "可能先建立边界再拆解任务。"
    assert {item["type"] for item in cognition["supporting_experiences"]} == {"project"}
    assert {item["id"] for item in cognition["supporting_experiences"]} == {project_a["id"], project_b["id"]}
    refs = cognition["source_refs"]
    assert {ref["id"] for ref in refs} == {wiki_a["id"], wiki_b["id"]}
    assert all(ref["kind"] == "wiki_knowledge" for ref in refs)
    assert all(raw["id"] != ref["id"] for ref in refs)
    store.shutdown()


def test_empty_result_is_successful_and_idempotent_without_writing_cognition(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project_a = _project(client, "D4 无变化项目甲")
    project_b = _project(client, "D4 无变化项目乙")
    _wiki(client, "project", project_a["id"], "项目甲的虚构观察。")
    _wiki(client, "project", project_b["id"], "项目乙的另一种虚构观察。")
    selected = [
        {"type": "project", "id": project_a["id"]},
        {"type": "project", "id": project_b["id"]},
    ]
    preview = _prepare(client, selected, "d4-empty-result")
    assert preview.status_code == 200, preview.text
    assert calls == []
    first = _execute(client, preview.json(), "d4-empty-result")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "no_changes"
    assert len(calls) == 1
    replay = _execute(client, preview.json(), "d4-empty-result")
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "no_changes"
    assert len(calls) == 1, "同一确认请求的幂等重放不能再调用 Provider"
    assert not _records(store, "wiki_compiler_proposal")
    assert client.get("/api/wiki/cognition/workspace").json()["knowledge"] == []
    store.shutdown()


def test_rewrite_add_edit_accept_and_reject_are_individual_decisions(tmp_path):
    client, store, calls = _harness(tmp_path)
    project_a = _project(client, "D4 审批项目甲")
    project_b = _project(client, "D4 审批项目乙")
    wiki_a = _wiki(client, "project", project_a["id"], "甲项目的虚构观察。")
    wiki_b = _wiki(client, "project", project_b["id"], "乙项目的虚构观察。")
    existing = _wiki(client, "cognition", "", "旧的跨经历虚构判断。")
    selected = [
        {"type": "project", "id": project_a["id"]},
        {"type": "project", "id": project_b["id"]},
    ]
    rewrite = {
        "operation": "rewrite", "target_knowledge_id": existing["id"],
        "before_revision": existing["revision"],
        "content": "改写后的跨经历观察。",
        "source_refs": [{"knowledge_id": wiki_a["id"]}, {"knowledge_id": wiki_b["id"]}],
        "reason": "两个所选经历都出现了相近做法。",
    }
    accepted_add = _add("候选后由用户编辑并接受。", wiki_a["id"], wiki_b["id"])
    rejected_add = _add("候选后由用户拒绝。", wiki_a["id"], wiki_b["id"])
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {
        "patches": [rewrite, accepted_add, rejected_add]
    }

    preview = _prepare(client, selected, "d4-mixed-decisions")
    assert preview.status_code == 200, preview.text
    before = client.get("/api/wiki/cognition/workspace").json()["knowledge"]
    assert len(before) == 1 and before[0]["content"] == "旧的跨经历虚构判断。"
    result = _execute(client, preview.json(), "d4-mixed-decisions")
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "proposal_pending"
    proposal = result.json()["proposal"]
    assert [item["operation"] for item in proposal["patches"]] == ["rewrite", "add", "add"]
    assert all(item["status"] == "pending" for item in proposal["patches"])
    assert (
        len(client.get("/api/wiki/cognition/workspace").json()["knowledge"]) == 1
    ), "pending Patch 不能修改正式 Cognition"
    bulk = client.post(f"/api/wiki/compiler/proposals/{proposal['id']}/resolve", json={
        "decision": "accept_all", "idempotency_key": "d4-no-bulk",
    })
    assert bulk.status_code in {404, 405}

    rewrite_result = _resolve(client, proposal, proposal["patches"][0], "accept", "d4-accept-rewrite")
    assert rewrite_result.status_code == 200, rewrite_result.text
    rewritten = rewrite_result.json()["patch"]["resolution"]["result"]
    assert rewritten["knowledge_id"] == existing["id"]
    assert rewritten["revision"] == existing["revision"] + 1
    edit_result = _resolve(
        client, proposal, proposal["patches"][1], "edit_accept", "d4-edit-accept-add",
        content="用户确认后的最终版本。",
    )
    assert edit_result.status_code == 200, edit_result.text
    user_version_id = edit_result.json()["patch"]["resolution"]["result"]["knowledge_id"]
    reject_result = _resolve(client, proposal, proposal["patches"][2], "reject", "d4-reject-add")
    assert reject_result.status_code == 200, reject_result.text
    assert reject_result.json()["patch"]["status"] == "rejected"

    workspace = client.get("/api/wiki/cognition/workspace").json()
    assert len(workspace["knowledge"]) == 2
    by_id = {item["id"]: item for item in workspace["knowledge"]}
    assert by_id[existing["id"]]["content"] == "改写后的跨经历观察。"
    assert by_id[user_version_id]["content"] == "用户确认后的最终版本。"
    assert all("用户拒绝" not in item["content"] for item in workspace["knowledge"])
    history = client.get(f"/api/wiki/{existing['id']}/history").json()["revisions"]
    assert [item["content"] for item in history] == ["旧的跨经历虚构判断。", "改写后的跨经历观察。"]
    saved_proposal = next(item for item in _records(store, "wiki_compiler_proposal")
                          if item["id"] == proposal["id"])
    assert saved_proposal["status"] == "resolved"
    assert [item["status"] for item in saved_proposal["patches"]] == ["accepted", "accepted", "rejected"]
    assert len(calls) == 1
    store.shutdown()


def test_retire_is_pending_until_accepted_and_keeps_history(tmp_path):
    client, store, calls = _harness(tmp_path)
    project_a = _project(client, "D4 退役旧经历")
    project_b = _project(client, "D4 退役新经历甲")
    project_c = _project(client, "D4 退役新经历乙")
    wiki_a = _wiki(client, "project", project_a["id"], "旧模式的虚构支撑。")
    wiki_b = _wiki(client, "project", project_b["id"], "新证据显示旧模式不普遍。")
    wiki_c = _wiki(client, "project", project_c["id"], "另一段经历也提供反例。")
    existing = _seed_cognition(client, "需要重新核对的旧判断。", [wiki_a], "d4-seed-retire")
    selected = [
        {"type": "project", "id": project_b["id"]},
        {"type": "project", "id": project_c["id"]},
    ]
    retire = {
        "operation": "retire", "target_knowledge_id": existing["id"],
        "before_revision": existing["revision"],
        "source_refs": [{"knowledge_id": wiki_b["id"]}],
        "reason": "新经历提供了与旧判断冲突的证据。",
    }
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {"patches": [retire]}
    preview = _prepare(client, selected, "d4-retire")
    assert preview.status_code == 200, preview.text
    response = _execute(client, preview.json(), "d4-retire")
    assert response.status_code == 200, response.text
    proposal = response.json()["proposal"]
    assert proposal["patches"][0]["status"] == "pending"
    assert client.get("/api/wiki/cognition/workspace").json()["knowledge"][0]["status"] == "current"

    accepted = _resolve(client, proposal, proposal["patches"][0], "accept", "d4-accept-retire")
    assert accepted.status_code == 200, accepted.text
    workspace = client.get("/api/wiki/cognition/workspace").json()
    assert workspace["knowledge"] == []
    assert len(workspace["retired"]) == 1
    assert workspace["retired"][0]["id"] == existing["id"]
    assert workspace["retired"][0]["status"] == "retired"
    history = client.get(f"/api/wiki/{existing['id']}/history").json()["revisions"]
    assert len(history) == 2 and history[-1]["status"] == "retired"
    assert len(calls) == 1
    store.shutdown()


def test_cognition_source_trace_preserves_lineage_without_loading_raw_until_requested(tmp_path, monkeypatch):
    client, store, calls = _harness(tmp_path)
    project_a = _project(client, "D4 来源链甲")
    project_b = _project(client, "D4 来源链乙")
    raw_a = _raw(client, project_a, "D4 虚构原始资料 A", "不可发送的虚构原文 A。")
    raw_b = _raw(client, project_b, "D4 虚构原始资料 B", "不可发送的虚构原文 B。")
    wiki_a = _wiki(client, "project", project_a["id"], "来源链 Wiki A。", [raw_a["source_ref"]])
    wiki_b = _wiki(client, "project", project_b["id"], "来源链 Wiki B。", [raw_b["source_ref"]])
    selected = [
        {"type": "project", "id": project_a["id"]},
        {"type": "project", "id": project_b["id"]},
    ]
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {
        "patches": [_add("两段经历共同支持的虚构观察。", wiki_a["id"], wiki_b["id"])]
    }
    preview = _prepare(client, selected, "d4-lineage")
    assert preview.status_code == 200, preview.text
    assert calls == []
    response = _execute(client, preview.json(), "d4-lineage")
    assert response.status_code == 200, response.text
    packet = json.loads(calls[0]["messages"][1]["content"])
    assert set(packet) == {"task", "selected_experiences", "existing_cognition"}
    assert all(set(item) == {"type", "id", "name", "current_knowledge"}
               for item in packet["selected_experiences"])
    assert "不可发送的虚构原文" not in json.dumps(packet, ensure_ascii=False)
    proposal = response.json()["proposal"]
    accepted = _resolve(client, proposal, proposal["patches"][0], "accept", "d4-lineage-accept")
    assert accepted.status_code == 200, accepted.text
    knowledge_id = accepted.json()["patch"]["resolution"]["result"]["knowledge_id"]
    from workbench.wiki import cognition, sources
    resolve_source = sources.resolve_source

    def refuse_raw_read(store_value, connection, kind, identifier):
        assert kind not in sources.RAW_RECORD_KINDS, "打开来源目录时不得读取 Raw 正文"
        return resolve_source(store_value, connection, kind, identifier)

    monkeypatch.setattr(cognition.sources, "resolve_source", refuse_raw_read)
    traces = client.get(f"/api/wiki/cognition/knowledge/{knowledge_id}/sources").json()["sources"]
    assert {item["experience"]["id"] for item in traces} == {project_a["id"], project_b["id"]}
    assert {item["wiki_knowledge"]["id"] for item in traces} == {wiki_a["id"], wiki_b["id"]}
    raw_refs = {
        item["raw_sources"][0]["source_ref"]["id"] for item in traces
    }
    assert raw_refs == {raw_a["id"], raw_b["id"]}
    assert all(set(item["raw_sources"][0]) == {"source_ref"} for item in traces)
    assert all(item["wiki_knowledge"]["source_ref"]["hash"] for item in traces)
    monkeypatch.setattr(cognition.sources, "resolve_source", resolve_source)
    assert client.get(f"/api/raw/raw_material/{raw_a['id']}").json()["content"] == raw_a["content"]
    assert client.get(f"/api/raw/raw_material/{raw_b['id']}").json()["content"] == raw_b["content"]
    assert len(calls) == 1
    store.shutdown()


def test_cognition_dto_and_approval_leave_person_opportunity_resume_and_interview_untouched(tmp_path):
    client, store, calls = _harness(tmp_path)
    project_a = _project(client, "D4 私料隔离项目甲")
    project_b = _project(client, "D4 私料隔离项目乙")
    wiki_a = _wiki(client, "project", project_a["id"], "所选项目 Wiki 甲。")
    wiki_b = _wiki(client, "project", project_b["id"], "所选项目 Wiki 乙。")

    private_employment = _employment(client, "D4 不发送的虚构任职")
    person_response = client.post(
        f"/api/work/employments/{private_employment['id']}/persons",
        json={"name": "D4 虚构私有人物", "role": "虚构角色", "idempotency_key": "d4-private-person"},
    )
    assert person_response.status_code == 200, person_response.text
    person = person_response.json()
    person_wiki = _wiki(client, "person", person["id"], "D4 PERSON PRIVATE SENTINEL")

    opportunity = _opportunity(client)
    opportunity_wiki = _wiki(client, "opportunity", opportunity["id"], "D4 OPPORTUNITY PRIVATE SENTINEL")
    resume_start = client.post(
        f"/api/opportunities/{opportunity['id']}/resume/start",
        json={"expected_opportunity_revision": opportunity["revision"],
              "idempotency_key": "d4-private-resume-start", "source": {"kind": "blank"}},
    )
    assert resume_start.status_code == 200, resume_start.text
    document = deepcopy(resume_start.json()["document"])
    document["profile"]["name"] = "D4 RESUME PRIVATE SENTINEL"
    resume_id = resume_start.json()["document_id"]
    saved_resume = client.put(f"/api/resume-documents/{resume_id}", json={
        "document": document, "expected_revision": resume_start.json()["revision"],
    })
    assert saved_resume.status_code == 200, saved_resume.text

    submission = client.post(f"/api/opportunities/{opportunity['id']}/submitted", json={
        "expected_revision": opportunity["revision"], "idempotency_key": "d4-private-submit",
        "resume": {"mode": "none"},
    })
    assert submission.status_code == 200, submission.text
    submitted_opportunity = submission.json()["opportunity"]
    interview_response = client.post(
        f"/api/opportunities/{opportunity['id']}/interviews/real",
        json={"name": "D4 虚构私有面试", "expected_opportunity_revision": submitted_opportunity["revision"],
              "idempotency_key": "d4-private-interview"},
    )
    assert interview_response.status_code == 200, interview_response.text
    interview_id = interview_response.json()["interview"]["id"]
    interview_before = client.get(f"/api/opportunities/{opportunity['id']}/interviews/{interview_id}").json()
    resume_before = client.get(f"/api/resume-documents/{resume_id}").json()

    selected = [
        {"type": "project", "id": project_a["id"]},
        {"type": "project", "id": project_b["id"]},
    ]
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {
        "patches": [_add("只由所选项目 Wiki 支撑的虚构观察。", wiki_a["id"], wiki_b["id"])]
    }
    preview = _prepare(client, selected, "d4-private-data-isolation")
    assert preview.status_code == 200, preview.text
    assert calls == []
    result = _execute(client, preview.json(), "d4-private-data-isolation")
    assert result.status_code == 200, result.text
    packet = json.loads(calls[0]["messages"][1]["content"])
    encoded = json.dumps(packet, ensure_ascii=False)
    for forbidden in (
        "D4 PERSON PRIVATE SENTINEL", "D4 OPPORTUNITY PRIVATE SENTINEL",
        "D4 RESUME PRIVATE SENTINEL", "D4 虚构私有人物", opportunity["id"],
    ):
        assert forbidden not in encoded
    proposal = result.json()["proposal"]
    accepted = _resolve(client, proposal, proposal["patches"][0], "accept", "d4-private-accept")
    assert accepted.status_code == 200, accepted.text
    assert client.get(f"/api/resume-documents/{resume_id}").json() == resume_before
    assert client.get(f"/api/opportunities/{opportunity['id']}/interviews/{interview_id}").json() == interview_before
    assert person_wiki["content"] == "D4 PERSON PRIVATE SENTINEL"
    assert opportunity_wiki["content"] == "D4 OPPORTUNITY PRIVATE SENTINEL"
    assert len(calls) == 1
    store.shutdown()


def test_one_project_cannot_be_counted_twice_in_patch_support(tmp_path):
    client, store, calls = _harness(tmp_path)
    project = _project(client, "D4 同经历支撑检查")
    wiki_a = _wiki(client, "project", project["id"], "虚构知识 A")
    wiki_b = _wiki(client, "project", project["id"], "虚构知识 B")
    other = _project(client, "D4 另一段空知识经历")
    _wiki(client, "project", other["id"], "另一段虚构经历知识")
    provider = store.provider
    provider.complete = lambda payload: calls.append(deepcopy(payload)) or {
        "patches": [_add("不应建立的长期认知。", wiki_a["id"], wiki_b["id"])]
    }
    preview = _prepare(client, [
        {"type": "project", "id": project["id"]},
        {"type": "project", "id": other["id"]},
    ], "d4-insufficient-independent-source")
    assert preview.status_code == 200, preview.text
    response = _execute(client, preview.json(), "d4-insufficient-independent-source")
    assert response.status_code in {409, 422, 503}
    assert len(calls) == 1
    assert not _records(store, "wiki_compiler_proposal")
    assert client.get("/api/wiki/cognition/workspace").json()["knowledge"] == []
    store.shutdown()


def test_changed_selected_wiki_after_preview_is_stale_before_provider_call(tmp_path):
    client, store, calls = _harness(tmp_path)
    project_a = _project(client, "D4 stale 甲")
    project_b = _project(client, "D4 stale 乙")
    wiki_a = _wiki(client, "project", project_a["id"], "旧版虚构观察 A")
    _wiki(client, "project", project_b["id"], "虚构观察 B")
    experiences = [
        {"type": "project", "id": project_a["id"]},
        {"type": "project", "id": project_b["id"]},
    ]
    preview = _prepare(client, experiences, "d4-stale-input")
    assert preview.status_code == 200, preview.text
    update = client.post(f"/api/wiki/{wiki_a['id']}", json={
        "knowledge_type": wiki_a["knowledge_type"], "content": "新版虚构观察 A",
        "tags": wiki_a["tags"], "source_refs": wiki_a["source_refs"],
        "status": "current", "expected_revision": wiki_a["revision"],
        "idempotency_key": "d4-stale-wiki-update",
    })
    assert update.status_code == 200, update.text
    response = _execute(client, preview.json(), "d4-stale-input")
    assert response.status_code == 409, response.text
    assert calls == []
    assert not _records(store, "wiki_compiler_proposal")
    store.shutdown()


def test_changed_selected_experience_and_changed_selection_are_stale_before_provider(tmp_path):
    client, store, calls = _harness(tmp_path)
    project_a = _project(client, "D4 经历 stale 甲")
    project_b = _project(client, "D4 经历 stale 乙")
    project_c = _project(client, "D4 经历 stale 丙")
    for item in (project_a, project_b, project_c):
        _wiki(client, "project", item["id"], f"{item['name']} 的虚构 Wiki。")
    selected = [
        {"type": "project", "id": project_a["id"]},
        {"type": "project", "id": project_b["id"]},
    ]
    preview = _prepare(client, selected, "d4-experience-stale")
    assert preview.status_code == 200, preview.text
    renamed = client.post(f"/api/work/projects/{project_a['id']}", json={
        "name": "改名后的 D4 经历 A", "description": project_a.get("description", ""),
        "tags": project_a.get("tags", []), "status": project_a["status"],
        "status_note": project_a.get("status_note", ""),
        "employment_id": project_a.get("employment_id"),
        "expected_revision": project_a["revision"], "idempotency_key": "d4-rename-stale",
    })
    assert renamed.status_code == 200, renamed.text
    response = _execute(client, preview.json(), "d4-experience-stale")
    assert response.status_code == 409, response.text
    assert calls == []
    assert not _records(store, "wiki_compiler_proposal")

    fresh = _prepare(client, selected, "d4-selection-stale")
    assert fresh.status_code == 200, fresh.text
    changed_selection = [selected[0], {"type": "project", "id": project_c["id"]}]
    response = client.post("/api/wiki/cognition/compiler/execute", json={
        "selected_experiences": changed_selection,
        "idempotency_key": "d4-selection-stale",
        "prepared_id": fresh.json()["prepared_id"],
        "payload_hash": fresh.json()["payload_hash"], "confirm_outbound": True,
    })
    assert response.status_code == 409, response.text
    assert calls == []
    assert not _records(store, "wiki_compiler_proposal")
    store.shutdown()


def test_changed_existing_cognition_revision_is_stale_before_provider_call(tmp_path):
    client, store, calls = _harness(tmp_path)
    project_a = _project(client, "D4 认知 stale 甲")
    project_b = _project(client, "D4 认知 stale 乙")
    wiki_a = _wiki(client, "project", project_a["id"], "经历甲虚构观察。")
    _wiki(client, "project", project_b["id"], "经历乙虚构观察。")
    existing = _seed_cognition(client, "预览前的已有认知。", [wiki_a], "d4-seed-current-stale")
    selected = [
        {"type": "project", "id": project_a["id"]},
        {"type": "project", "id": project_b["id"]},
    ]
    preview = _prepare(client, selected, "d4-current-stale")
    assert preview.status_code == 200, preview.text
    update = client.post(f"/api/wiki/{existing['id']}", json={
        "knowledge_type": existing["knowledge_type"], "content": "预览后人工修改的认知。",
        "tags": existing["tags"], "source_refs": existing["source_refs"],
        "status": "current", "expected_revision": existing["revision"],
        "idempotency_key": "d4-update-current-stale",
    })
    assert update.status_code == 200, update.text
    response = _execute(client, preview.json(), "d4-current-stale")
    assert response.status_code == 409, response.text
    assert calls == []
    assert not _records(store, "wiki_compiler_proposal")
    store.shutdown()


@pytest.mark.parametrize("field,value", [
    ("reason", "你属于完美主义人格，领导力评分为82分。"),
    ("tags", ["#沟通能力82分"]),
])
def test_personality_labels_and_scoring_are_rejected_in_all_candidate_text(tmp_path, field, value):
    client, store, calls = _harness(tmp_path)
    project_a = _project(client, "D4 安全输出甲")
    project_b = _project(client, "D4 安全输出乙")
    wiki_a = _wiki(client, "project", project_a["id"], "虚构观察 A。")
    wiki_b = _wiki(client, "project", project_b["id"], "虚构观察 B。")
    candidate = _add("多个经历都出现先明确边界的做法。", wiki_a["id"], wiki_b["id"])
    candidate[field] = value
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {"patches": [candidate]}
    preview = _prepare(client, [
        {"type": "project", "id": project_a["id"]},
        {"type": "project", "id": project_b["id"]},
    ], "d4-reject-profile-output")
    assert preview.status_code == 200, preview.text
    response = _execute(client, preview.json(), "d4-reject-profile-output")
    assert response.status_code in {409, 422, 503}, response.text
    assert len(calls) == 1
    assert not _records(store, "wiki_compiler_proposal")
    assert client.get("/api/wiki/cognition/workspace").json()["knowledge"] == []
    store.shutdown()


def test_model_output_error_stores_only_safe_code_and_field_path(tmp_path):
    client, store, calls = _harness(tmp_path)
    project_a = _project(client, "D4 安全诊断经历 A")
    project_b = _project(client, "D4 安全诊断经历 B")
    wiki_a = _wiki(client, "project", project_a["id"], "虚构观察 A。")
    wiki_b = _wiki(client, "project", project_b["id"], "虚构观察 B。")
    candidate = _add("多个经历中先明确边界再开始实现。", wiki_a["id"], wiki_b["id"])
    candidate["reason"] = "你属于完美主义人格，这是不能保存的模型文本。"
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {"patches": [candidate]}
    experiences = [
        {"type": "project", "id": project_a["id"]},
        {"type": "project", "id": project_b["id"]},
    ]
    preview = _prepare(client, experiences, "d4-safe-error-path")
    assert preview.status_code == 200, preview.text
    response = _execute(client, preview.json(), "d4-safe-error-path")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "content_policy_violation"
    assert body["diagnostics"] == {"field_path": "$.patches[0].reason"}
    assert body["detail"] == "AI 返回的结果无法安全使用，本次没有修改长期认知。"
    assert len(calls) == 1
    assert not _records(store, "wiki_compiler_proposal")
    assert client.get("/api/wiki/cognition/workspace").json()["knowledge"] == []
    with store.connect(False) as connection:
        row = connection.execute(
            "SELECT error_code,error_message FROM ai_operations WHERE task_type=? AND idempotency_key=?",
            ("wiki_cognition_compiler", "d4-safe-error-path"),
        ).fetchone()
    assert tuple(row) == ("content_policy_violation", "$.patches[0].reason")
    assert "完美主义" not in row[1]
    assert "完美主义" not in json.dumps(_records(store, "ai_call"), ensure_ascii=False)
    store.shutdown()


def test_cognition_schema_has_complete_dynamic_contract_and_legal_example(tmp_path):
    from workbench.model_gateway import OpenAICompatibleAdapter
    from workbench.runtime_mode import resolve_runtime_mode
    from workbench.wiki.cognition import _latest_context, _schema

    client, store, _calls = _harness(tmp_path)
    project_a = _project(client, "D4 schema 虚构经历 A")
    project_b = _project(client, "D4 schema 虚构经历 B")
    wiki_a = _wiki(client, "project", project_a["id"], "虚构来源 A。")
    wiki_b = _wiki(client, "project", project_b["id"], "虚构来源 B。")
    selected = [{"type": "project", "id": project_a["id"]}, {"type": "project", "id": project_b["id"]}]
    dto, _manifest, *_rest = _latest_context(store, selected)
    schema = _schema(dto)
    example_patch = schema["example"]["patches"][0]
    assert example_patch["operation"] == "add"
    assert {item["knowledge_id"] for item in example_patch["source_refs"]} == {wiki_a["id"], wiki_b["id"]}
    assert set(example_patch) == {"operation", "knowledge_type", "content", "tags", "source_refs", "reason"}
    assert example_patch["knowledge_type"] in {"fact", "observation", "hypothesis"}
    adapter = OpenAICompatibleAdapter(
        {"provider": "deepseek", "base_url": "https://api.deepseek.com", "model": "deepseek-flash"},
        "synthetic-only", runtime_mode=resolve_runtime_mode("AI_ENABLED"),
    )
    prompt = adapter.build_payload(dto, schema)["messages"][0]["content"]
    for required_contract in (
        "source_refs", "knowledge_id", "knowledge_type", "observation", "hypothesis",
        "before_revision", "target_knowledge_id", "null", "额外字段", "两段不同经历",
    ):
        assert required_contract in prompt
    assert json.dumps(schema["example"], ensure_ascii=False, separators=(",", ":")) in prompt
    assert "虚构" in example_patch["content"]
    existing = _seed_cognition(client, "一条虚构的已有认知。", [wiki_a], "d4-schema-existing")
    dto_with_existing, _manifest, *_rest = _latest_context(store, selected)
    operations = _schema(dto_with_existing)["properties"]["patches"]["items"]["oneOf"]
    by_operation = {item["properties"]["operation"]["const"]: item for item in operations}
    assert set(by_operation) == {"add", "rewrite", "retire"}
    assert by_operation["rewrite"]["properties"]["target_knowledge_id"] == {"const": existing["id"]}
    assert by_operation["rewrite"]["properties"]["before_revision"] == {"const": existing["revision"]}
    assert "content" in by_operation["rewrite"]["required"]
    assert "content" not in by_operation["retire"]["required"]
    assert "content" not in by_operation["retire"]["properties"]
    store.shutdown()


def test_d4_contract_failures_have_safe_codes_and_json_paths(tmp_path):
    from workbench.wiki.cognition import CognitionOutputInvalid, _latest_context, _validate_output

    client, store, _calls = _harness(tmp_path)
    project_a = _project(client, "D4 错误分类经历 A")
    project_b = _project(client, "D4 错误分类经历 B")
    wiki_a = _wiki(client, "project", project_a["id"], "错误分类虚构 Wiki A。")
    wiki_b = _wiki(client, "project", project_b["id"], "错误分类虚构 Wiki B。")
    selected = [{"type": "project", "id": project_a["id"]}, {"type": "project", "id": project_b["id"]}]
    dto, _manifest, _selected, source_map, *_rest = _latest_context(store, selected)
    valid = _add("多个虚构经历中先明确边界再开始实现。", wiki_a["id"], wiki_b["id"])

    def assert_rejected(result, code, path, context=dto, sources=source_map):
        with pytest.raises(CognitionOutputInvalid) as raised:
            _validate_output(result, context, sources)
        assert raised.value.code == code
        assert raised.value.diagnostics == {"field_path": path}
        assert "虚构" not in str(raised.value)

    cases = [
        ([], "top_level_invalid", "$"),
        ({}, "patches_missing", "$.patches"),
        ({"patches": {}}, "patch_wrong_type", "$.patches"),
        ({"patches": ["坏 Patch 正文不应进入日志"]}, "patch_wrong_type", "$.patches[0]"),
        ({"patches": [{"operation": "replace"}]}, "operation_invalid", "$.patches[0].operation"),
        ({"patches": [{**valid, "knowledge_type": "Observation"}]}, "knowledge_type_invalid", "$.patches[0].knowledge_type"),
        ({"patches": [{key: value for key, value in valid.items() if key != "content"}]}, "content_missing", "$.patches[0].content"),
        ({"patches": [{**valid, "content": "  "}]}, "content_empty", "$.patches[0].content"),
        ({"patches": [{**valid, "content": ["wrong"]}]}, "content_wrong_type", "$.patches[0].content"),
        ({"patches": [{key: value for key, value in valid.items() if key != "source_refs"}]}, "source_experiences_missing", "$.patches[0].source_refs"),
        ({"patches": [{**valid, "source_refs": [{"knowledge_id": "not-selected"}]}]}, "source_experience_unknown", "$.patches[0].source_refs[0].knowledge_id"),
        ({"patches": [{**valid, "source_refs": [{"knowledge_id": wiki_a["id"]}]}]}, "source_experiences_insufficient", "$.patches[0].source_refs"),
        ({"patches": [{**valid, "source_refs": [{"knowledge_id": wiki_a["id"], "raw_content": "不应进入诊断"}]}]}, "extra_field", "$.patches[0].source_refs[0].<extra_field>"),
        ({"patches": [{**valid, "tags": "不是数组"}]}, "tags_invalid", "$.patches[0].tags"),
        ({"patches": [{**valid, "reason": "  "}]}, "reason_empty", "$.patches[0].reason"),
        ({"patches": [{**valid, "extra": "不记录这段值"}]}, "extra_field", "$.patches[0].<extra_field>"),
        ({"patches": [{**valid, "secret-looking-model-key": "不记录这个值"}]}, "extra_field", "$.patches[0].<extra_field>"),
    ]
    for result, code, path in cases:
        assert_rejected(result, code, path)

    existing = _seed_cognition(client, "一条虚构已有认知。", [wiki_a], "d4-error-target-seed")
    dto_with_existing, _manifest, _selected, source_map_with_existing, *_rest = _latest_context(store, selected)
    rewrite = {
        "operation": "rewrite", "target_knowledge_id": existing["id"],
        "before_revision": existing["revision"], "content": "更新后的虚构认知。",
        "source_refs": [{"knowledge_id": wiki_a["id"]}, {"knowledge_id": wiki_b["id"]}],
        "reason": "两个不同经历共同支持。",
    }
    assert_rejected({"patches": [{**rewrite, "target_knowledge_id": "not-a-target"}]},
                    "target_missing", "$.patches[0].target_knowledge_id", dto_with_existing, source_map_with_existing)
    assert_rejected({"patches": [{key: value for key, value in rewrite.items() if key != "target_knowledge_id"}]},
                    "target_missing", "$.patches[0].target_knowledge_id", dto_with_existing, source_map_with_existing)
    assert_rejected({"patches": [{**rewrite, "before_revision": existing["revision"] + 1}]},
                    "target_revision_mismatch", "$.patches[0].before_revision", dto_with_existing, source_map_with_existing)
    store.shutdown()


def test_cognition_wiki_reference_is_validated_and_traces_to_source_history(tmp_path):
    client, store, _calls = _harness(tmp_path)
    project_a = _project(client, "D4 来源链项目 A")
    project_b = _project(client, "D4 来源链项目 B")
    wiki = _wiki(client, "project", project_a["id"], "来源链里的项目 Wiki。")
    other_wiki = _wiki(client, "project", project_b["id"], "另一段经历的 Wiki。")
    wrong_scope = client.post("/api/wiki", json={
        "scope_type": "cognition", "scope_id": "", "knowledge_type": "observation",
        "content": "无效经历来源。", "tags": [],
        "source_refs": [{"kind": "wiki_knowledge", "id": wiki["id"],
                          "revision": wiki["revision"], "hash": "0" * 64}],
        "idempotency_key": "d4-bad-source-hash",
    })
    assert wrong_scope.status_code == 409
    cognition = client.post("/api/wiki", json={
        "scope_type": "cognition", "scope_id": "", "knowledge_type": "hypothesis",
        "content": "来自两段经历的虚构长期认知。", "tags": [],
        "source_refs": [
            {"kind": "wiki_knowledge", "id": wiki["id"], "revision": wiki["revision"], "hash": _wiki_ref_hash(wiki)},
            {"kind": "wiki_knowledge", "id": other_wiki["id"], "revision": other_wiki["revision"], "hash": _wiki_ref_hash(other_wiki)},
        ],
        "idempotency_key": "d4-good-source-chain",
    })
    assert cognition.status_code == 200, cognition.text
    workspace = client.get("/api/wiki/cognition/workspace")
    assert workspace.status_code == 200, workspace.text
    item = workspace.json()["knowledge"][0]
    assert {source["id"] for source in item["supporting_experiences"]} == {project_a["id"], project_b["id"]}
    catalog = client.get("/api/wiki", params={
        "scope_type": "cognition", "include_source_titles": "true",
    }).json()["source_catalog"]
    assert {source["source_ref"]["id"] for source in catalog} == {wiki["id"], other_wiki["id"]}
    history = client.get(f"/api/wiki/{wiki['id']}/history")
    assert history.status_code == 200
    assert history.json()["revisions"][0]["content"] == "来源链里的项目 Wiki。"
    store.shutdown()


def _wiki_ref_hash(item):
    from workbench.core import digest
    return digest(item)


def test_supersede_out_of_boundary_cognition_proposal_without_rejecting_or_applying(tmp_path):
    from workbench.wiki.cognition import supersede_pending_proposal

    client, store, calls = _harness(tmp_path)
    project_a = _project(client, "D4 supersede 虚构项目 A")
    project_b = _project(client, "D4 supersede 虚构项目 B")
    extra = _project(client, "D4 supersede 额外虚构项目")
    wiki_a = _wiki(client, "project", project_a["id"], "虚构知识 A。")
    wiki_b = _wiki(client, "project", project_b["id"], "虚构知识 B。")
    wiki_extra = _wiki(client, "project", extra["id"], "额外虚构知识。")
    selected = [
        {"type": "project", "id": project_a["id"]},
        {"type": "project", "id": project_b["id"]},
        {"type": "project", "id": extra["id"]},
    ]
    fake_calls = []
    def complete(payload):
        fake_calls.append(deepcopy(payload))
        return {"patches": [_add(
            "仅用于测试的跨经历观察。", wiki_a["id"], wiki_b["id"], wiki_extra["id"],
        )]}
    store.provider.complete = complete
    prepared = _prepare(client, selected, "d4-supersede-prepare").json()
    executed = _execute(client, prepared, "d4-supersede-prepare")
    assert executed.status_code == 200, executed.text
    proposal = executed.json()["proposal"]
    assert proposal["status"] == "pending"
    operation_id = executed.json()["operation_id"]
    with store.connect(False) as c:
        audit_before = len(store._records(c, "ai_audit"))

    outcome = supersede_pending_proposal(
        store, proposal["id"], expected_operation_id=operation_id,
        expected_experiences=[
            {"type": "project", "id": project_a["id"]},
            {"type": "project", "id": project_b["id"]},
        ],
    )

    assert outcome["status"] == "superseded"
    assert outcome["patch_count"] == 1
    with store.connect(False) as c:
        saved = store._get(c, proposal["id"], "wiki_compiler_proposal", True)
        op = c.execute("select state,error_code from ai_operations where op_id=?", (operation_id,)).fetchone()
        audit_after = len(store._records(c, "ai_audit"))
        cognition = [item for item in store._current(c, "wiki_knowledge")
                     if item.get("scope_type") == "cognition"]
    assert saved["status"] == "superseded"
    assert saved["patches"][0]["status"] == "superseded"
    assert saved["system_resolution"] == {
        "from_status": "pending", "to_status": "superseded",
        "reason_code": "smoke_scope_replaced", "operation_id": operation_id,
    }
    assert "decision" not in saved["patches"][0]
    assert tuple(op) == ("succeeded", None)
    assert audit_after == audit_before
    assert cognition == []
    assert len(fake_calls) == 1


def test_supersede_refuses_current_two_experience_proposal(tmp_path):
    from workbench.wiki.cognition import supersede_pending_proposal
    from workbench.core import Conflict

    client, store, _calls = _harness(tmp_path)
    project_a = _project(client, "D4 supersede guard 项目 A")
    project_b = _project(client, "D4 supersede guard 项目 B")
    wiki_a = _wiki(client, "project", project_a["id"], "守卫测试虚构知识 A。")
    wiki_b = _wiki(client, "project", project_b["id"], "守卫测试虚构知识 B。")
    selected = [{"type": "project", "id": project_a["id"]}, {"type": "project", "id": project_b["id"]}]
    store.provider.complete = lambda payload: {"patches": [_add(
        "应继续由用户逐条决定的虚构建议。", wiki_a["id"], wiki_b["id"],
    )]}
    prepared = _prepare(client, selected, "d4-supersede-guard-prepare").json()
    executed = _execute(client, prepared, "d4-supersede-guard-prepare").json()
    with pytest.raises(Conflict):
        supersede_pending_proposal(
            store, executed["proposal"]["id"], expected_operation_id=executed["operation_id"],
            expected_experiences=selected,
        )
    with store.connect(False) as c:
        saved = store._get(c, executed["proposal"]["id"], "wiki_compiler_proposal", True)
    assert saved["status"] == "pending"
    store.shutdown()
