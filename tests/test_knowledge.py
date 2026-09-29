from batch_b_helpers import save_job
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


def seed_source(store, key, **changes):
    source = {
        "id": f"legacy-source-{key}", "created_at": "2026-01-01T00:00:00Z",
        "title": "访谈原文", "content": "  原文保留空白  ", "source_type": "text",
        "locator": "", "scope_type": "personal", "scope_id": "",
    }
    source.update(changes)
    with store.connect() as connection:
        store._record(connection, "knowledge_source", source)
    return source


def seed_candidate(store, key, source_ids, **changes):
    candidate = {
        "id": f"legacy-candidate-{key}", "created_at": "2026-01-01T00:00:00Z",
        "source_ids": source_ids, "entry_type": "experience", "title": "经历",
        "content": "负责虚构项目", "scope_type": "personal", "scope_id": "",
        "status": "pending", "entry_id": None,
    }
    candidate.update(changes)
    with store.connect() as connection:
        return store._save(connection, "knowledge_candidate", candidate, 0)


def seed_entry(store, source, entry_type="experience", scope_type="personal",
                 scope_id="", key="candidate-1", content="当前事实"):
    with store.connect() as connection:
        return store._save(connection, "wiki_entry", {
            "id": f"legacy-entry-{key}", "title": "项目", "content": content,
            "entry_type": entry_type, "scope_type": scope_type,
            "scope_id": scope_id, "source_ids": [source["id"]],
            "status": "active", "verification": "user_asserted",
            "created_at": "2026-01-01T00:00:00Z",
        }, 0)


def test_old_source_preserves_original_content_and_locator_on_read(tmp_path):
    client, store = make_client(tmp_path)
    locator = str(tmp_path / "must-not-be-opened")
    source = seed_source(store, "original", source_type="local_repository", locator=locator)
    state = client.get("/api/knowledge").json()
    assert state == {"sources": [source], "candidates": [], "entries": []}
    with store.connect(False) as connection:
        assert store._get(connection, source["id"], "knowledge_source", True) == source


def test_existing_candidate_can_be_rejected_without_creating_entry(tmp_path):
    client, store = make_client(tmp_path)
    source = seed_source(store, "candidate")
    candidate = seed_candidate(store, "pending", [source["id"]])
    assert client.get("/api/knowledge").json()["candidates"] == [candidate]
    with store.connect(False) as c:
        before_epoch = store._epoch(c)
    body = {"decision": "reject", "expected_revision": candidate["revision"],
            "idempotency_key": "reject-old-pending"}
    resolved = client.post(f"/api/knowledge/candidates/{candidate['id']}/resolve", json=body)
    assert resolved.status_code == 200 and resolved.json()["status"] == "rejected"
    assert client.post(f"/api/knowledge/candidates/{candidate['id']}/resolve", json=body).json() == resolved.json()
    state = client.get("/api/knowledge").json()
    assert state["entries"] == [] and state["candidates"] == [resolved.json()]
    with store.connect(False) as c:
        assert store._epoch(c) == before_epoch


def test_rejected_and_episode_material_never_enters_packet(tmp_path):
    client, store = make_client(tmp_path)
    personal = seed_source(store, "rejected")
    seed_candidate(store, "rejected", [personal["id"]],
                   content="拒绝内容 sentinel-rejected", status="rejected")

    episode = client.post("/api/journey/episodes", json={
        "company": "虚构公司", "role": "工程师", "focus": "私聊"
    }).json()
    episode_source = seed_source(store, "episode", scope_type="episode", scope_id=episode["id"],
                                 content="任职私聊 sentinel-private")
    episode_entry = seed_entry(
        store, episode_source, scope_type="episode", scope_id=episode["id"],
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
        sources[name] = seed_source(store, name, scope_type=scope_type, scope_id=scope_id,
                                    content="原始-" + name)
    goal = seed_entry(store, sources["goal"], "goal", key="goal", content="当前目标")
    project = seed_entry(store, sources["project"], "project", key="project", content="项目旧版")
    job_entry = seed_entry(store, sources["job"], "strategy", "job", job["id"],
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


def test_packet_refuses_oversize_mandatory_content_without_truncation(tmp_path):
    _, store = make_client(tmp_path)
    first_source = seed_source(store, "large-source-1")
    second_source = seed_source(store, "large-source-2")
    seed_entry(store, first_source, "goal", key="large-goal", content="甲" * 60000)
    seed_entry(store, second_source, "constraint", key="large-constraint", content="乙" * 60000)
    with store.connect(False) as c:
        try:
            selected_wiki_sources(store, c, None, None)
        except Invalid as exc:
            assert "100000" in str(exc)
        else:
            raise AssertionError("oversize mandatory Wiki content should not be truncated")
