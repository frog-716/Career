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
    person = c.post("/api/work/persons", json={"name": "虚构同事", "role": "协作者", "idempotency_key": "person-1"}).json()
    participant = c.post(f"/api/work/projects/{project['id']}/participants", json={"person_id": person["id"], "role": "共同负责", "idempotency_key": "participant-1"}).json()
    event = c.post("/api/work/events", json={"project_id": project["id"], "title": "交付事件", "kind": "delivery", "content": "不可变事件原文", "idempotency_key": "event-1"}).json()
    achievement = c.post("/api/work/achievements", json={"project_id": project["id"], "title": "成果", "content": "初始成果", "idempotency_key": "achievement-1"}).json()
    evidence = c.post("/api/work/evidence", json={"scope_type": "project", "scope_id": project["id"], "title": "证据", "source_type": "document", "content": "不可变证据原文", "idempotency_key": "evidence-1"}).json()
    link = c.post("/api/work/evidence-links", json={"achievement_id": achievement["id"], "evidence_id": evidence["id"], "idempotency_key": "link-1"}).json()
    changed = c.post(f"/api/work/achievements/{achievement['id']}", json={"title": "成果修订", "content": "修订成果", "expected_revision": achievement["revision"], "idempotency_key": "achievement-edit-1"}).json()
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
    assert c.post("/api/work/events", json={"episode_id": episode["id"], "project_id": project["id"], "title": "x", "kind": "x", "content": "x", "idempotency_key": "bad-target"}).status_code == 422
    with store.connect(False) as db:
        assert not db.execute("SELECT 1 FROM records WHERE kind='knowledge_source'").fetchone()
