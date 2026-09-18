from batch_b_helpers import save_job
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from workbench.core import Conflict, Invalid, Missing, Store
from workbench.journey import journey_router
from workbench.knowledge import knowledge_router, selected_wiki_sources
from workbench.providers import TestProvider


def make_client(tmp_path):
    store = Store(tmp_path, TestProvider())
    app = FastAPI()
    for cls, code in ((Invalid, 422), (Conflict, 409), (Missing, 404)):
        async def handle(request, exc, status=code):
            return JSONResponse({"detail": str(exc)}, status_code=status)
        app.add_exception_handler(cls, handle)
    app.include_router(journey_router(store))
    app.include_router(knowledge_router(store))
    return TestClient(app), store


def source_body(key="source-1", **changes):
    body = {
        "title": "访谈原文", "content": "  原文保留空白  ", "source_type": "text",
        "locator": "", "scope_type": "personal", "scope_id": "",
        "idempotency_key": key,
    }
    body.update(changes)
    return body


def candidate_body(source_ids, key="candidate-1", **changes):
    body = {
        "source_ids": source_ids, "entry_type": "experience", "title": "经历",
        "content": "负责虚构项目", "scope_type": "personal", "scope_id": "",
        "idempotency_key": key,
    }
    body.update(changes)
    return body


def create_entry(client, source, entry_type="experience", scope_type="personal",
                 scope_id="", key="candidate-1", content="当前事实"):
    candidate = client.post("/api/knowledge/candidates", json=candidate_body(
        [source["id"]], key, entry_type=entry_type, scope_type=scope_type,
        scope_id=scope_id, content=content)).json()
    resolved = client.post(f"/api/knowledge/candidates/{candidate['id']}/resolve", json={
        "decision": "confirm", "expected_revision": candidate["revision"],
        "idempotency_key": "resolve-" + key,
    })
    assert resolved.status_code == 200
    return resolved.json(), client.get("/api/knowledge").json()["entries"][0]


def test_source_is_immutable_preserves_original_and_idempotency(tmp_path):
    client, _ = make_client(tmp_path)
    locator = str(tmp_path / "must-not-be-opened")
    body = source_body(source_type="local_repository", locator=locator)
    first = client.post("/api/knowledge/sources", json=body)
    assert first.status_code == 200
    assert first.json()["content"] == body["content"] and first.json()["locator"] == locator
    assert client.post("/api/knowledge/sources", json=body).json() == first.json()
    assert client.post("/api/knowledge/sources", json=dict(body, content="不同原文")).status_code == 409
    state = client.get("/api/knowledge").json()
    assert state == {"sources": [first.json()], "candidates": [], "entries": []}


def test_candidate_scope_cas_edit_and_confirmation_are_transactional(tmp_path):
    client, store = make_client(tmp_path)
    personal = client.post("/api/knowledge/sources", json=source_body()).json()
    job = save_job(store,{"company": "虚构公司", "title": "工程师", "jd": "JD"})
    job_source = client.post("/api/knowledge/sources", json=source_body(
        "source-job", scope_type="job", scope_id=job["id"])).json()

    cross_scope = client.post("/api/knowledge/candidates", json=candidate_body(
        [personal["id"], job_source["id"]], "cross", scope_type="personal", scope_id=""))
    assert cross_scope.status_code == 422
    created = client.post("/api/knowledge/candidates", json=candidate_body([personal["id"]]))
    assert created.status_code == 200 and created.json()["revision"] == 1
    candidate = created.json()
    edit = candidate_body([personal["id"]], "edit-1", title="新标题",
                          expected_revision=candidate["revision"])
    edited = client.post(f"/api/knowledge/candidates/{candidate['id']}", json=edit)
    assert edited.status_code == 200 and edited.json()["revision"] == 2
    assert client.post(f"/api/knowledge/candidates/{candidate['id']}", json=edit).json() == edited.json()
    stale = dict(edit, idempotency_key="edit-stale", title="覆盖")
    assert client.post(f"/api/knowledge/candidates/{candidate['id']}", json=stale).status_code == 409

    with store.connect(False) as c:
        before_epoch = store._epoch(c)
    resolve_body = {"decision": "confirm", "expected_revision": 2,
                    "idempotency_key": "resolve-1"}
    resolved = client.post(f"/api/knowledge/candidates/{candidate['id']}/resolve", json=resolve_body)
    assert resolved.status_code == 200 and resolved.json()["entry_id"]
    assert client.post(f"/api/knowledge/candidates/{candidate['id']}/resolve", json=resolve_body).json() == resolved.json()
    assert client.post(f"/api/knowledge/candidates/{candidate['id']}/resolve", json={
        **resolve_body, "decision": "reject"}).status_code == 409
    state = client.get("/api/knowledge").json()
    assert len(state["entries"]) == 1 and state["candidates"][0]["status"] == "confirmed"
    with store.connect(False) as c:
        assert store._epoch(c) == before_epoch + 1


def test_rejected_and_episode_material_never_enters_packet(tmp_path):
    client, store = make_client(tmp_path)
    personal = client.post("/api/knowledge/sources", json=source_body()).json()
    rejected = client.post("/api/knowledge/candidates", json=candidate_body(
        [personal["id"]], "rejected", content="拒绝内容 sentinel-rejected")).json()
    assert client.post(f"/api/knowledge/candidates/{rejected['id']}/resolve", json={
        "decision": "reject", "expected_revision": 1, "idempotency_key": "reject-1"
    }).status_code == 200

    episode = client.post("/api/journey/episodes", json={
        "company": "虚构公司", "role": "工程师", "focus": "私聊"
    }).json()
    episode_source = client.post("/api/knowledge/sources", json=source_body(
        "episode-source", scope_type="episode", scope_id=episode["id"],
        content="任职私聊 sentinel-private")).json()
    _, episode_entry = create_entry(
        client, episode_source, scope_type="episode", scope_id=episode["id"],
        key="episode", content="任职私聊 sentinel-private")
    with store.connect(False) as c:
        assert selected_wiki_sources(store, c, None, None) == []
        try:
            selected_wiki_sources(store, c, [episode_entry["id"]], None)
        except Invalid as exc:
            assert "任职范围" in str(exc)
        else:
            raise AssertionError("episode Wiki should be rejected")


def test_packet_uses_current_revision_mandatory_and_explicit_entries_only(tmp_path):
    client, store = make_client(tmp_path)
    job = save_job(store,{"company": "虚构公司", "title": "工程师", "jd": "JD"})
    sources = {}
    for name, scope_type, scope_id in (
        ("goal", "personal", ""), ("project", "personal", ""),
        ("project-extra", "personal", ""),
        ("job", "job", job["id"]),
    ):
        sources[name] = client.post("/api/knowledge/sources", json=source_body(
            "source-" + name, scope_type=scope_type, scope_id=scope_id,
            content="原始-" + name)).json()
    _, goal = create_entry(client, sources["goal"], "goal", key="goal", content="当前目标")
    _, project = create_entry(client, sources["project"], "project", key="project", content="项目旧版")
    _, job_entry = create_entry(client, sources["job"], "strategy", "job", job["id"],
                                key="job", content="岗位策略")

    updated = client.post(f"/api/knowledge/entries/{project['id']}", json={
        "title": "项目", "content": "项目新版", "entry_type": "project",
        "status": "active", "expected_revision": project["revision"],
        "source_ids": [sources["project"]["id"], sources["project-extra"]["id"]],
    })
    assert updated.status_code == 200 and updated.json()["revision"] == 2
    assert updated.json()["source_ids"] == [sources["project"]["id"], sources["project-extra"]["id"]]
    cross_scope = client.post(f"/api/knowledge/entries/{project['id']}", json={
        "title": "项目", "content": "不应写入", "entry_type": "project",
        "status": "active", "expected_revision": 2,
        "source_ids": [sources["job"]["id"]],
    })
    assert cross_scope.status_code == 422
    history = client.get(f"/api/knowledge/entries/{project['id']}/history").json()["revisions"]
    assert [item["content"] for item in history] == ["项目旧版", "项目新版"]

    with store.connect(False) as c:
        default = selected_wiki_sources(store, c, None, job["id"])
        packet = selected_wiki_sources(store, c, [project["id"], job_entry["id"]], job["id"])
    assert [item["id"] for item in default] == [goal["id"]]
    assert {item["id"] for item in packet} == {goal["id"], project["id"], job_entry["id"]}
    project_packet = next(item for item in packet if item["id"] == project["id"])
    assert project_packet["revision"] == 2 and project_packet["content"]["content"] == "项目新版"
    assert project_packet["source_ids"] == [sources["project"]["id"], sources["project-extra"]["id"]]
    assert project_packet["purpose"] == "current_fact"
    job_packet = next(item for item in packet if item["id"] == job_entry["id"])
    assert job_packet["purpose"] == "task_context"
    assert job_packet["content"]["scope_type"] == "job"
    assert job_packet["content"]["scope_id"] == job["id"]
    assert "项目旧版" not in str(packet)

    withdrawn = client.post(f"/api/knowledge/entries/{project['id']}", json={
        "title": "项目", "content": "项目新版", "entry_type": "project",
        "status": "withdrawn", "expected_revision": 2,
    })
    assert withdrawn.status_code == 200
    with store.connect(False) as c:
        try:
            selected_wiki_sources(store, c, [project["id"]], job["id"])
        except Invalid as exc:
            assert "撤回" in str(exc)
        else:
            raise AssertionError("withdrawn Wiki should be rejected")


def test_concurrent_source_idempotency_creates_one_immutable_record(tmp_path):
    client, _ = make_client(tmp_path)
    body = source_body("concurrent-source")

    def submit(_):
        return client.post("/api/knowledge/sources", json=body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert len({response.json()["id"] for response in responses}) == 1
    assert len(client.get("/api/knowledge").json()["sources"]) == 1


def test_packet_refuses_oversize_mandatory_content_without_truncation(tmp_path):
    client, store = make_client(tmp_path)
    first_source = client.post("/api/knowledge/sources", json=source_body("large-source-1")).json()
    second_source = client.post("/api/knowledge/sources", json=source_body("large-source-2")).json()
    create_entry(client, first_source, "goal", key="large-goal", content="甲" * 60000)
    create_entry(client, second_source, "constraint", key="large-constraint", content="乙" * 60000)
    with store.connect(False) as c:
        try:
            selected_wiki_sources(store, c, None, None)
        except Invalid as exc:
            assert "100000" in str(exc)
        else:
            raise AssertionError("oversize mandatory Wiki content should not be truncated")
