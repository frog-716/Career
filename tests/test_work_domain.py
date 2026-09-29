import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.core import Conflict, Invalid, Missing, Store
from workbench.journey import journey_router
from workbench.providers import TestProvider
from workbench.work import work_router


def client_for(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    app = FastAPI()
    for cls, code in ((Invalid, 422), (Conflict, 409), (Missing, 404)):
        async def handle(request, exc, status=code):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": str(exc)}, status_code=status)
        app.add_exception_handler(cls, handle)
    app.include_router(journey_router(store))
    app.include_router(work_router(store))
    return TestClient(app), store


def test_episode_to_project_event_achievement_evidence_survives_restart(tmp_path):
    c, store = client_for(tmp_path)
    episode = c.post("/api/journey/episodes", json={"company": "虚构公司", "role": "研发", "focus": "原始任职"}).json()
    employment = c.get("/api/work-domain").json()["employments"][0]
    assert employment["legacy_episode_id"] == episode["id"]
    stage = c.post(f"/api/work/employments/{employment['id']}/stages", json={"name": "平台建设", "start_date": "2021-05-01", "end_date": "2022-06-01", "focus": "从试点到上线", "status": "completed", "idempotency_key": "stage-1"}).json()
    assert stage["employment_id"] == employment["id"]
    updated_stage = c.post(f"/api/work/stages/{stage['id']}", json={"name": "平台建设复盘", "start_date": "2021-05-01", "end_date": "2022-06-01", "focus": "保留阶段原文", "status": "completed", "expected_revision": stage["revision"], "idempotency_key": "stage-edit-1"}).json()
    assert updated_stage["revision"] == stage["revision"] + 1
    assert c.post(f"/api/work/stages/{stage['id']}", json={"name": "旧版本", "start_date": "2021-05-01", "end_date": "2022-06-01", "expected_revision": stage["revision"], "idempotency_key": "stage-edit-stale"}).status_code == 409
    assert c.post(f"/api/work/employments/{employment['id']}/stages", json={"name": "非法阶段", "start_date": "2022-06-02", "end_date": "2022-06-01", "idempotency_key": "stage-bad"}).status_code == 422
    project = c.post("/api/work/projects", json={"name": "迁移项目", "scope_type": "employment", "scope_id": employment["id"], "description": "项目原文", "idempotency_key": "project-1"}).json()
    source = c.post("/api/work/sources", json={"project_id": project["id"], "scope_type": "employment", "scope_id": employment["id"], "title": "任职来源", "content": "来源原文", "semantics": "用户原始记录", "idempotency_key": "source-1"}).json()
    person = c.post(f"/api/work/employments/{employment['id']}/persons", json={"name": "虚构同事", "role": "协作者", "idempotency_key": "person-1"}).json()
    participant = c.post(f"/api/work/projects/{project['id']}/participants", json={"person_id": person["id"], "role": "共同负责", "idempotency_key": "participant-1"}).json()
    # Preserve an old data graph without using its retired creation endpoints.
    with store.connect() as db:
        event = {"id": "historical-event", "target_type": "project", "target_id": project["id"],
                 "title": "交付事件", "kind": "delivery", "content": "不可变事件原文",
                 "created_at": "2026-01-01T00:00:00Z"}
        store._record(db, "work_event", event)
        achievement = store._save(db, "work_achievement", {
            "id": "historical-achievement", "project_id": project["id"], "title": "成果",
            "content": "初始成果", "created_at": event["created_at"]}, 0)
        evidence = {"id": "historical-evidence", "scope_type": "project", "scope_id": project["id"],
                    "title": "证据", "source_type": "document", "content": "不可变证据原文",
                    "created_at": event["created_at"]}
        store._record(db, "work_evidence", evidence)
        link = {"id": "historical-link", "achievement_id": achievement["id"],
                "evidence_id": evidence["id"], "achievement_revision": achievement["revision"],
                "evidence_created_at": evidence["created_at"], "created_at": event["created_at"]}
        store._record(db, "work_evidence_link", link)
        changed = store._save(db, "work_achievement", dict(achievement, title="成果修订",
                                                                content="修订成果"), achievement["revision"])
    assert changed["revision"] == achievement["revision"] + 1
    domain = c.get("/api/work-domain").json()
    assert updated_stage in domain["stages"]
    assert source in domain["sources"] and participant in domain["participants"] and event in domain["events"] and link in domain["evidence_links"]
    reopened = Store(tmp_path / "data", TestProvider())
    app = FastAPI(); app.include_router(work_router(reopened))
    restored = TestClient(app).get("/api/work-domain").json()
    assert restored["projects"][0]["id"] == project["id"]
    assert restored["stages"][0]["id"] == updated_stage["id"]
    assert restored["events"][0]["content"] == "不可变事件原文"
    assert restored["evidence"][0]["content"] == "不可变证据原文"
    assert restored["achievements"][0]["content"] == "修订成果"


def test_work_domain_scope_cas_idempotency_and_no_wiki_side_effect(tmp_path):
    c, store = client_for(tmp_path)
    episode = c.post("/api/journey/episodes", json={"company": "甲", "role": "乙"}).json()
    body = {"name": "项目", "scope_type": "episode", "scope_id": episode["id"], "idempotency_key": "same"}
    first = c.post("/api/work/projects", json=body)
    assert first.status_code == 200
    assert c.post("/api/work/projects", json=body).json() == first.json()
    assert c.post("/api/work/projects", json={**body, "name": "另一个"}).status_code == 409
    project = first.json()
    assert c.post(f"/api/work/projects/{project['id']}", json={"name": "新名", "description": "", "expected_revision": 0, "idempotency_key": "edit"}).status_code == 409
    assert c.post("/api/work/sources", json={"scope_type": "episode", "scope_id": "missing", "title": "x", "content": "x", "semantics": "x", "idempotency_key": "bad-source"}).status_code == 404
    assert c.post("/api/work/events", json={"episode_id": episode["id"], "project_id": project["id"], "title": "x", "kind": "x", "content": "x", "idempotency_key": "bad-target"}).status_code == 409
    with store.connect(False) as db:
        assert not db.execute("SELECT 1 FROM records WHERE kind='knowledge_source'").fetchone()


def test_project_is_independent_revisioned_object_with_free_tags_and_four_statuses(tmp_path):
    c, store = client_for(tmp_path)
    created = c.post("/api/work/projects", json={
        "name": "个人 Career 工作台",
        "description": "长期自己使用",
        "tags": ["#AI", "#黑客松"],
        "status": "active",
        "status_note": "",
        "idempotency_key": "independent-project",
    })
    assert created.status_code == 200
    project = created.json()
    assert project["employment_id"] is None
    assert project["tags"] == ["#AI", "#黑客松"]
    assert c.post("/api/work/projects", json={
        "name": "个人 Career 工作台",
        "description": "长期自己使用",
        "tags": ["#AI", "#黑客松"],
        "status": "active",
        "status_note": "",
        "idempotency_key": "independent-project",
    }).json()["id"] == project["id"]
    assert c.get("/api/work-domain").json()["participants"] == []

    updated = c.post(f"/api/work/projects/{project['id']}", json={
        "name": "Career 长期工作台",
        "description": "改名仍然是同一个项目",
        "tags": ["#AI", "#个人项目"],
        "status": "canceled",
        "status_note": "方向结束，记录在原 Project 上",
        "employment_id": None,
        "expected_revision": project["revision"],
        "idempotency_key": "independent-project-edit",
    })
    assert updated.status_code == 200
    saved = updated.json()
    assert saved["id"] == project["id"]
    assert saved["revision"] == project["revision"] + 1
    assert saved["name"] == "Career 长期工作台"
    assert saved["tags"] == ["#AI", "#个人项目"]
    assert saved["status"] == "canceled"
    assert saved["status_note"] == "方向结束，记录在原 Project 上"
    repeated_update = c.post(f"/api/work/projects/{project['id']}", json={
        "name": "Career 长期工作台",
        "description": "改名仍然是同一个项目",
        "tags": ["#AI", "#个人项目"],
        "status": "canceled",
        "status_note": "方向结束，记录在原 Project 上",
        "employment_id": None,
        "expected_revision": project["revision"],
        "idempotency_key": "independent-project-edit",
    }).json()
    assert repeated_update["id"] == saved["id"]
    assert repeated_update["revision"] == saved["revision"]
    cleared_tags = c.post(f"/api/work/projects/{project['id']}", json={
        "name": saved["name"], "description": saved["description"], "tags": [],
        "status": saved["status"], "status_note": saved["status_note"],
        "employment_id": None, "expected_revision": saved["revision"],
        "idempotency_key": "independent-project-clear-tags",
    }).json()
    assert cleared_tags["tags"] == []
    domain = c.get("/api/work-domain").json()
    assert [item["id"] for item in domain["projects"]] == [project["id"]]
    with store.connect(False) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 6
        assert db.execute("SELECT COUNT(*) FROM current WHERE kind='work_project'").fetchone()[0] == 1


def test_project_status_is_restricted_and_revision_conflicts_remain_safe(tmp_path):
    c, _ = client_for(tmp_path)
    for status in ("active", "paused", "completed", "canceled"):
        assert c.post("/api/work/projects", json={
            "name": "允许状态 " + status, "status": status,
            "idempotency_key": "good-status-" + status,
        }).status_code == 200
    for status in ("stopped", "merged", "replaced", "pivot", "archived", "unknown"):
        response = c.post("/api/work/projects", json={
            "name": "状态校验",
            "status": status,
            "idempotency_key": "bad-status-" + status,
        })
        assert response.status_code == 422

    project = c.post("/api/work/projects", json={
        "name": "CAS 项目", "idempotency_key": "cas-project",
    }).json()
    stale = c.post(f"/api/work/projects/{project['id']}", json={
        "name": "过期修改", "description": "", "tags": [], "status": "paused",
        "status_note": "", "employment_id": None,
        "expected_revision": project["revision"] + 1,
        "idempotency_key": "cas-project-stale",
    })
    assert stale.status_code == 409
    assert c.get("/api/work-domain").json()["projects"][0]["name"] == "CAS 项目"


def test_employment_and_project_share_one_optional_association_without_copy(tmp_path):
    c, store = client_for(tmp_path)
    episode = c.post("/api/journey/episodes", json={"company": "虚构公司", "role": "研发"}).json()
    employment = c.get("/api/work-domain").json()["employments"][0]
    assert employment["legacy_episode_id"] == episode["id"]
    project = c.post("/api/work/projects", json={
        "name": "关联项目", "tags": ["#AI"], "status": "active",
        "employment_id": employment["id"], "idempotency_key": "linked-project",
    }).json()
    linked = c.get("/api/work-domain").json()["projects"]
    assert len(linked) == 1
    assert linked[0]["id"] == project["id"]
    assert linked[0]["employment_id"] == employment["id"]

    standalone = c.post("/api/work/projects", json={
        "name": "待关联个人项目", "idempotency_key": "personal-to-link",
    }).json()
    link_request = {
        "employment_id": employment["id"],
        "expected_revision": standalone["revision"],
        "idempotency_key": "attach-existing-project",
    }
    attached = c.post(f"/api/work/projects/{standalone['id']}/employment", json=link_request)
    assert attached.status_code == 200
    assert attached.json()["id"] == standalone["id"]
    assert attached.json()["employment_id"] == employment["id"]
    assert c.post(f"/api/work/projects/{standalone['id']}/employment", json=link_request).json() == attached.json()
    assert c.post(f"/api/work/projects/{standalone['id']}/employment", json={
        "employment_id": None, "expected_revision": standalone["revision"],
        "idempotency_key": "stale-project-unlink",
    }).status_code == 409

    all_projects = c.get("/api/work-domain").json()["projects"]
    assert {item["id"] for item in all_projects} == {project["id"], standalone["id"]}
    assert len([item for item in all_projects if item["employment_id"] == employment["id"]]) == 2
    with store.connect(False) as db:
        assert db.execute("SELECT COUNT(*) FROM current WHERE kind='work_project'").fetchone()[0] == 2


def test_legacy_project_scope_is_read_as_canonical_employment_without_schema_migration(tmp_path):
    c, store = client_for(tmp_path)
    episode = c.post("/api/journey/episodes", json={"company": "测试公司", "role": "测试岗位"}).json()
    employment = c.get("/api/work-domain").json()["employments"][0]
    legacy = c.post("/api/work/projects", json={
        "name": "旧式测试项目", "scope_type": "episode", "scope_id": episode["id"],
        "idempotency_key": "legacy-project",
    }).json()
    project = c.get("/api/work-domain").json()["projects"][0]
    assert project["id"] == legacy["id"]
    assert project["employment_id"] == employment["id"]
    assert project["tags"] == []
    assert project["status"] == "active"
    assert "scope_type" not in project and "scope_id" not in project
    with store.connect(False) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 6
        assert db.execute("SELECT COUNT(*) FROM current WHERE kind='work_project'").fetchone()[0] == 1
