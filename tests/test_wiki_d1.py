"""D1: Raw references and manually maintained Wiki Knowledge."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from workbench.core import Conflict, Invalid, Missing, Store, digest
from workbench.employment import employment_router
from workbench.journey import journey_router
from workbench.knowledge import knowledge_router
from workbench.providers import TestProvider
from workbench.work import work_router
from workbench.wiki import raw_wiki_router


def make_client(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    app = FastAPI()
    for cls, code in ((Invalid, 422), (Conflict, 409), (Missing, 404)):
        async def handle(request, exc, status=code):
            return JSONResponse({"detail": str(exc)}, status_code=status)
        app.add_exception_handler(cls, handle)
    app.include_router(journey_router(store))
    app.include_router(knowledge_router(store))
    app.include_router(work_router(store))
    app.include_router(employment_router(store))
    app.include_router(raw_wiki_router(store))
    return TestClient(app), store


def make_project(client, name="虚构项目"):
    response = client.post("/api/work/projects", json={
        "name": name, "idempotency_key": "project-" + name,
    })
    assert response.status_code == 200
    return response.json()


def make_employment(client, name="虚构任职"):
    response = client.post("/api/employments", json={
        "company": name, "role": "虚构角色",
    })
    assert response.status_code == 200
    return response.json()


def make_raw(client, scope_type, scope_id, content, key):
    response = client.post("/api/raw", json={
        "scope_type": scope_type, "scope_id": scope_id,
        "source_kind": "manual_text", "title": "虚构原始资料",
        "content": content, "idempotency_key": key,
    })
    assert response.status_code == 200, response.text
    return response.json()


def make_knowledge(client, scope_type, scope_id, source_refs, key,
                   knowledge_type="fact", content="虚构 Wiki 知识"):
    response = client.post("/api/wiki", json={
        "scope_type": scope_type, "scope_id": scope_id,
        "knowledge_type": knowledge_type, "content": content,
        "tags": ["#D1"], "source_refs": source_refs,
        "idempotency_key": key,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_project_raw_has_stable_identity_and_cannot_be_changed_by_wiki(tmp_path):
    client, store = make_client(tmp_path)
    project = make_project(client)
    content = "虚构原始记录：周五提交方案。"
    raw = make_raw(client, "project", project["id"], content, "raw-1")

    assert raw["id"] and raw["source_kind"] == "manual_text"
    assert raw["scope_type"] == "project" and raw["scope_id"] == project["id"]
    assert raw["revision"] == 1 and raw["hash"] == digest({
        "source_kind": "manual_text", "scope_type": "project",
        "scope_id": project["id"], "title": raw["title"], "content": content,
    })
    assert raw["provenance"] == {"kind": "user"}
    retry = client.post("/api/raw", json={
        "scope_type": "project", "scope_id": project["id"],
        "source_kind": "manual_text", "title": raw["title"],
        "content": content, "idempotency_key": "raw-1",
    })
    assert retry.status_code == 200 and retry.json()["id"] == raw["id"]
    assert client.post("/api/raw", json={
        "scope_type": "project", "scope_id": project["id"],
        "source_kind": "manual_text", "title": raw["title"],
        "content": "换了内容但复用旧请求号", "idempotency_key": "raw-1",
    }).status_code == 409
    listed = client.get(f"/api/raw?scope_type=project&scope_id={project['id']}").json()["items"]
    summary = next(item for item in listed if item["id"] == raw["id"])
    assert "content" not in summary
    assert client.post(f"/api/raw/{raw['id']}", json={"content": "不可编辑"}).status_code == 404

    entry = make_knowledge(client, "project", project["id"], [raw["source_ref"]], "wiki-1")
    edited = client.post(f"/api/wiki/{entry['id']}", json={
        "knowledge_type": "observation", "content": "修改后的虚构观察。",
        "tags": ["#修改"], "source_refs": [raw["source_ref"]],
        "expected_revision": entry["revision"], "idempotency_key": "wiki-edit-1",
    })
    assert edited.status_code == 200
    retired = client.post(f"/api/wiki/{entry['id']}", json={
        "knowledge_type": "observation", "content": "修改后的虚构观察。",
        "tags": ["#修改"], "source_refs": [raw["source_ref"]],
        "status": "retired", "expected_revision": edited.json()["revision"],
        "idempotency_key": "wiki-retire-1",
    })
    assert retired.status_code == 200 and retired.json()["status"] == "retired"

    fetched = client.get(f"/api/raw/{raw['source_ref']['kind']}/{raw['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["content"] == content and fetched.json()["hash"] == raw["hash"]
    assert client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}&limit=50").json()["items"] == []
    assert client.get(
        f"/api/wiki?scope_type=project&scope_id={project['id']}&status=retired&limit=50"
    ).json()["items"][0]["id"] == entry["id"]
    history = client.get(f"/api/wiki/{entry['id']}/history").json()["revisions"]
    assert [item["content"] for item in history] == [entry["content"], edited.json()["content"], edited.json()["content"]]
    with store.connect(False) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 6
        assert store._get(c, raw["id"], "raw_material", True)["hash"] == raw["hash"]


def test_fact_observation_hypothesis_are_the_only_semantic_types(tmp_path):
    client, _ = make_client(tmp_path)
    project = make_project(client)
    for index, kind in enumerate(("fact", "observation", "hypothesis")):
        item = make_knowledge(client, "project", project["id"], [], f"type-{index}", kind)
        assert item["knowledge_type"] == kind
        assert item["provenance"] == {"kind": "user"}
        assert item["source_refs"] == []
    invalid = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"],
        "knowledge_type": "achievement", "content": "不可当作类型",
        "tags": [], "source_refs": [], "idempotency_key": "bad-type",
    })
    assert invalid.status_code == 422


def test_scope_validation_person_is_never_created_by_wiki_and_opportunities_are_isolated(tmp_path):
    client, store = make_client(tmp_path)
    employment_a = make_employment(client, "虚构任职 A")
    employment_b = make_employment(client, "虚构任职 B")
    person_a = client.post(f"/api/work/employments/{employment_a['id']}/persons", json={
        "name": "虚构人物 A", "role": "虚构角色", "idempotency_key": "person-a",
    }).json()
    raw_a = make_raw(client, "employment", employment_a["id"], "任职 A 原文", "employment-raw-a")
    before_people = len(client.get("/api/work-domain").json()["persons"])

    person_entry = make_knowledge(
        client, "person", person_a["id"], [raw_a["source_ref"]], "person-wiki",
    )
    assert person_entry["scope_type"] == "person" and person_entry["scope_id"] == person_a["id"]
    missing_person = client.post("/api/wiki", json={
        "scope_type": "person", "scope_id": "missing-person",
        "knowledge_type": "fact", "content": "不得借 Wiki 建人物",
        "tags": [], "source_refs": [], "idempotency_key": "missing-person-wiki",
    })
    assert missing_person.status_code == 404
    assert len(client.get("/api/work-domain").json()["persons"]) == before_people

    opportunity_a = store.save_opportunity({
        "company_name": "虚构机会 A", "title": "虚构岗位 A", "jd": "虚构岗位说明 A",
        "idempotency_key": "opportunity-a",
    })
    opportunity_b = store.save_opportunity({
        "company_name": "虚构机会 B", "title": "虚构岗位 B", "jd": "虚构岗位说明 B",
        "idempotency_key": "opportunity-b",
    })
    raw_op_a = make_raw(client, "opportunity", opportunity_a["id"], "机会 A 原文", "op-raw-a")
    raw_op_b = make_raw(client, "opportunity", opportunity_b["id"], "机会 B 原文", "op-raw-b")
    entry_a = make_knowledge(
        client, "opportunity", opportunity_a["id"], [raw_op_a["source_ref"]], "op-wiki-a",
    )
    cross = client.post("/api/wiki", json={
        "scope_type": "opportunity", "scope_id": opportunity_a["id"],
        "knowledge_type": "fact", "content": "不能跨机会引用",
        "tags": [], "source_refs": [raw_op_b["source_ref"]],
        "idempotency_key": "cross-opportunity",
    })
    assert cross.status_code == 409
    visible_a = client.get(
        f"/api/wiki?scope_type=opportunity&scope_id={opportunity_a['id']}&limit=50"
    ).json()["items"]
    assert [item["id"] for item in visible_a] == [entry_a["id"]]
    general_wiki = client.get("/api/wiki?scope_type=all&limit=50").json()["items"]
    assert all(item["scope_type"] != "opportunity" for item in general_wiki)
    with store.connect(False) as c:
        assert store._get(c, employment_b["id"].replace("employment:", "", 1), "journey_episode")


def test_related_raw_sources_are_listed_without_crossing_object_boundaries(tmp_path):
    client, store = make_client(tmp_path)
    employment = make_employment(client)
    person = client.post(f"/api/work/employments/{employment['id']}/persons", json={
        "name": "虚构人物", "role": "虚构职务", "idempotency_key": "related-person",
    }).json()
    project = client.post("/api/work/projects", json={
        "name": "任职关联项目", "employment_id": employment["id"],
        "idempotency_key": "related-project",
    }).json()
    employment_raw = make_raw(client, "employment", employment["id"], "任职原文", "related-employment-raw")
    project_raw = make_raw(client, "project", project["id"], "项目原文", "related-project-raw")
    person_raw = make_raw(client, "person", person["id"], "人物原文", "related-person-raw")
    personal_raw = make_raw(client, "personal", "", "个人原文", "related-personal-raw")

    def listed(scope_type, scope_id):
        return {
            item["id"] for item in client.get(
                f"/api/raw?scope_type={scope_type}&scope_id={scope_id}"
            ).json()["items"]
        }

    assert listed("project", project["id"]) == {employment_raw["id"], project_raw["id"]}
    assert listed("employment", employment["id"]) == {employment_raw["id"], project_raw["id"]}
    assert listed("person", person["id"]) == {
        employment_raw["id"], project_raw["id"], person_raw["id"],
    }
    cognition = listed("cognition", "")
    assert {personal_raw["id"], employment_raw["id"], project_raw["id"], person_raw["id"]} <= cognition
    # Opportunity material remains private even from the cross-experience source list.
    opportunity = store.save_opportunity({
        "company_name": "隔离机会", "title": "岗位", "jd": "虚构 JD",
        "idempotency_key": "related-opportunity",
    })
    opportunity_raw = make_raw(
        client, "opportunity", opportunity["id"], "机会原文", "related-opportunity-raw",
    )
    assert opportunity_raw["id"] not in cognition


def test_multiple_raw_refs_are_reusable_and_unknown_or_stale_refs_fail_closed(tmp_path):
    client, store = make_client(tmp_path)
    project = make_project(client)
    first = make_raw(client, "project", project["id"], "原文一", "raw-one")
    second = make_raw(client, "project", project["id"], "原文二", "raw-two")
    one = make_knowledge(client, "project", project["id"], [first["source_ref"], second["source_ref"]], "wiki-one")
    two = make_knowledge(client, "project", project["id"], [first["source_ref"]], "wiki-two", "observation")
    assert {ref["id"] for ref in one["source_refs"]} == {first["id"], second["id"]}
    assert two["source_refs"][0]["id"] == first["id"]

    missing = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"],
        "knowledge_type": "fact", "content": "坏来源",
        "tags": [], "source_refs": [{
            "kind": "raw_material", "id": "missing", "revision": 1, "hash": "0" * 64,
        }], "idempotency_key": "missing-source",
    })
    assert missing.status_code == 404
    stale_ref = dict(first["source_ref"], hash="0" * 64)
    stale = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"],
        "knowledge_type": "fact", "content": "旧来源版本",
        "tags": [], "source_refs": [stale_ref], "idempotency_key": "stale-source",
    })
    assert stale.status_code == 409
    url_only = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"],
        "knowledge_type": "fact", "content": "自由网址不算 Career 来源",
        "tags": [], "source_refs": [{"url": "https://example.invalid/source"}],
        "idempotency_key": "url-is-not-a-source-ref",
    })
    assert url_only.status_code == 422
    with store.connect(False) as c:
        assert len(store._current(c, "wiki_knowledge")) == 2


def test_existing_evidence_is_referenced_without_copy_and_ai_review_is_not_raw(tmp_path):
    client, store = make_client(tmp_path)
    project = make_project(client)
    evidence = client.post("/api/work/evidence", json={
        "scope_type": "project", "scope_id": project["id"],
        "title": "虛构验收证据", "source_type": "document",
        "content": "现有证据原文", "idempotency_key": "evidence-1",
    }).json()
    resolved = client.get(f"/api/raw/work_evidence/{evidence['id']}")
    assert resolved.status_code == 200
    assert resolved.json()["content"] == evidence["content"]
    from workbench.work import _evidence_pointer
    assert resolved.json()["hash"] == _evidence_pointer(evidence)["hash"]
    entry = make_knowledge(client, "project", project["id"], [resolved.json()["source_ref"]], "evidence-wiki")
    assert entry["source_refs"][0]["kind"] == "work_evidence"
    with store.connect(False) as c:
        assert store._get(c, evidence["id"], "work_evidence", True) == evidence
        store._record(c, "interview_final_review", {
            "id": "review-fixture", "summary": "AI 派生复盘不是 Raw",
            "interview_session_id": "session-fixture", "revision": 1,
        })
    assert client.get("/api/raw/interview_final_review/review-fixture").status_code == 404
    assert entry["source_refs"][0]["id"] == evidence["id"]


def test_legacy_raw_sources_keep_their_original_ids_and_derived_objects_are_excluded(tmp_path):
    client, store = make_client(tmp_path)
    project = make_project(client, "Raw 类型映射项目")
    episode = client.post("/api/journey/episodes", json={
        "company": "虚构任职", "role": "虚构岗位",
    }).json()
    opportunity = store.save_opportunity({
        "company_name": "虚构面试公司", "title": "虚构职位", "jd": "虚构岗位说明",
        "idempotency_key": "legacy-raw-opportunity",
    })

    knowledge_source = client.post("/api/knowledge/sources", json={
        "scope_type": "personal", "scope_id": "", "title": "旧资料原文",
        "content": "用户输入的旧原文", "source_type": "text",
        "idempotency_key": "legacy-knowledge-source",
    }).json()
    project_source = client.post("/api/work/sources", json={
        "scope_type": "personal", "scope_id": "", "project_id": project["id"],
        "title": "项目资料原文", "content": "项目用户原文", "semantics": "虚构记录",
        "idempotency_key": "legacy-project-source",
    }).json()
    event = client.post("/api/work/events", json={
        "project_id": project["id"], "title": "工作事件", "content": "事件原文",
        "kind": "delivery", "idempotency_key": "legacy-event",
    }).json()
    note = client.post("/api/journey/notes", json={
        "scope_type": "episode", "scope_id": episode["id"], "kind": "reflection",
        "title": "任职原话", "content": "当时的原话",
        "idempotency_key": "legacy-journey-note",
    }).json()
    with store.connect() as c:
        session_id = "synthetic-interview-session"
        store._record(c, "interview", {
            "id": session_id, "opportunity_id": opportunity["id"], "type": "real",
        })
        interview_raw_id = "synthetic-interview-raw"
        store._record(c, "interview_raw", {
            "id": interview_raw_id, "interview_session_id": session_id,
            "content": "虚构转写原文", "revision": 1,
        })
        simulation_session_id = "synthetic-simulation-session"
        store._record(c, "interview", {
            "id": simulation_session_id, "opportunity_id": opportunity["id"],
            "type": "simulation",
        })
        simulation_raw_id = "synthetic-simulation-raw"
        store._record(c, "interview_raw", {
            "id": simulation_raw_id, "interview_session_id": simulation_session_id,
            "content": "虚构模拟转写", "revision": 1,
        })
        communication_id = "synthetic-communication"
        store._record(c, "communication", {
            "id": communication_id, "opportunity_id": opportunity["id"],
            "type": "message", "occurred_on": "2026-01-01",
            "content": "虚构沟通原文", "archived": False,
        })

    sources_to_check = [
        ("knowledge_source", knowledge_source, "用户输入的旧原文"),
        ("work_project_source", project_source, "项目用户原文"),
        ("work_event", event, "事件原文"),
        ("journey_note", note, "当时的原话"),
        ("interview_raw", {"id": interview_raw_id}, "虚构转写原文"),
        ("interview_raw", {"id": simulation_raw_id}, "虚构模拟转写"),
        ("communication", {"id": communication_id}, "虚构沟通原文"),
    ]
    for kind, source, expected_content in sources_to_check:
        response = client.get(f"/api/raw/{kind}/{source['id']}")
        assert response.status_code == 200, response.text
        assert response.json()["content"] == expected_content
        assert response.json()["id"] == source["id"]
        assert response.json()["kind"] == kind
        assert len(response.json()["hash"]) == 64

    simulation_source = client.get(f"/api/raw/interview_raw/{simulation_raw_id}").json()
    assert simulation_source["source_kind"] == "simulation_interview_transcript"
    assert simulation_source["provenance"]["interview_type"] == "simulation"

    transcript = client.get(f"/api/raw/interview_raw/{interview_raw_id}").json()
    transcript_knowledge = make_knowledge(
        client, "opportunity", opportunity["id"],
        [transcript["source_ref"]], "stale-transcript-wiki",
    )
    with store.connect() as c:
        changed_transcript = store._get(c, interview_raw_id, "interview_raw", True)
        changed_transcript.update(
            content="虚构转写修正版", revision=2,
            hash=digest({"content": "虚构转写修正版"}),
        )
        store._record(c, "interview_raw", changed_transcript)
    stale_transcript = client.get(
        f"/api/raw/interview_raw/{interview_raw_id}"
        f"?revision={transcript['revision']}&hash={transcript['hash']}"
    )
    assert stale_transcript.status_code == 409
    replay = client.post("/api/wiki", json={
        "scope_type": "opportunity", "scope_id": opportunity["id"],
        "knowledge_type": "fact", "content": "虚构 Wiki 知识",
        "tags": ["#D1"], "source_refs": [transcript["source_ref"]],
        "idempotency_key": "stale-transcript-wiki",
    })
    assert replay.status_code == 200
    assert replay.json()["id"] == transcript_knowledge["id"]
    assert replay.json()["revision"] == transcript_knowledge["revision"]
    retired = client.post(f"/api/wiki/{transcript_knowledge['id']}", json={
        "knowledge_type": transcript_knowledge["knowledge_type"],
        "content": transcript_knowledge["content"],
        "tags": transcript_knowledge["tags"],
        "source_refs": transcript_knowledge["source_refs"],
        "status": "retired", "expected_revision": transcript_knowledge["revision"],
        "idempotency_key": "retire-stale-transcript-wiki",
    })
    assert retired.status_code == 200 and retired.json()["status"] == "retired"
    assert retired.json()["source_refs"] == transcript_knowledge["source_refs"]

    achievement = client.post("/api/work/achievements", json={
        "project_id": project["id"], "title": "不是 Raw 的成果实体",
        "content": "应该由后续知识表达", "idempotency_key": "legacy-achievement",
    }).json()
    assert client.get(f"/api/raw/work_achievement/{achievement['id']}").status_code == 404


def test_wiki_cas_idempotency_and_user_authored_source_without_raw(tmp_path):
    client, _ = make_client(tmp_path)
    project = make_project(client)
    body = {
        "scope_type": "project", "scope_id": project["id"],
        "knowledge_type": "hypothesis", "content": "用户自己的待验证想法",
        "tags": [], "source_refs": [], "idempotency_key": "manual-wiki",
    }
    created = client.post("/api/wiki", json=body)
    assert created.status_code == 200
    item = created.json()
    assert item["provenance"] == {"kind": "user"} and item["source_refs"] == []
    assert client.post("/api/wiki", json=body).json() == item
    assert client.post("/api/wiki", json={**body, "content": "另一条", "idempotency_key": "manual-wiki"}).status_code == 409
    update_body = {
        "knowledge_type": "hypothesis", "content": "已修订想法", "tags": [],
        "source_refs": [], "expected_revision": item["revision"],
        "idempotency_key": "manual-wiki-edit",
    }
    updated = client.post(f"/api/wiki/{item['id']}", json=update_body)
    assert updated.status_code == 200 and updated.json()["revision"] == item["revision"] + 1
    replay = client.post(f"/api/wiki/{item['id']}", json=update_body)
    assert replay.status_code == 200 and replay.json() == updated.json()
    stale = client.post(f"/api/wiki/{item['id']}", json={
        "knowledge_type": "hypothesis", "content": "不应覆盖", "tags": [],
        "source_refs": [], "expected_revision": item["revision"],
        "idempotency_key": "manual-wiki-stale",
    })
    assert stale.status_code == 409
