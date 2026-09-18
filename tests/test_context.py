from batch_b_helpers import save_job
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.context import ContextCompiler
from workbench.core import Store
from workbench.journey import journey_router
from workbench.providers import TestProvider
from workbench.app import create_app


def test_context_v2_is_stable_and_keeps_legacy_fields(tmp_path):
    store = Store(tmp_path, TestProvider())
    store.save_profile("当前经历", 0)
    job = save_job(store,{"company": "虚构公司", "title": "工程师", "jd": "岗位要求"})

    preview = store.context(job["id"], "job", "请分析")
    with store.connect(False) as connection:
        compiled = ContextCompiler(store).compile(
            connection, job["id"], "job", "请分析", None)

    assert preview == compiled
    assert preview["schemaVersion"] == 2
    assert preview["task_type"] == preview["taskKind"] == "job"
    assert preview["target"] == {
        "type": "opportunity", "id": "opportunity:" + job["id"],
        "job_posting_id": job["id"],
    }
    assert preview["policy_version"] == "context-v2"
    assert {"unknowns", "conflicts", "omissions", "budget_used", "epoch"} <= set(preview)
    assert all({"id", "revision", "hash", "purpose", "selected_content"} <= set(source)
               for source in preview["sources"])

    run = store.analyze(job["id"], "job", "请分析", preview["epoch"], "stable-run")
    packet = run["packet"]
    assert [(s["id"], s["revision"], s["hash"]) for s in packet["sources"]] == [
        (s["id"], s["revision"], s["hash"]) for s in preview["sources"]
    ]
    assert json.dumps(run["payload"], ensure_ascii=False)


def test_context_v2_excludes_feedback_and_unrelated_journey(tmp_path):
    store = Store(tmp_path, TestProvider())
    store.save_profile("当前经历", 0)
    job = save_job(store,{"company": "虚构公司", "title": "工程师", "jd": "岗位要求"})
    store.feedback({"text": "反馈哨兵", "current_page": "job"})
    app = FastAPI()
    app.include_router(journey_router(store))
    TestClient(app).post("/api/journey/episodes", json={
        "company": "另一公司", "role": "另一角色", "focus": "任职哨兵",
    })

    encoded = json.dumps(store.context(job["id"], "job"), ensure_ascii=False)
    assert "反馈哨兵" not in encoded
    assert "任职哨兵" not in encoded


def test_opportunity_relation_change_invalidates_preview_and_run(tmp_path):
    store = Store(tmp_path, TestProvider())
    store.save_profile("当前经历", 0)
    client = TestClient(create_app(store))
    headers = {"X-Career-Request": "1"}
    job = client.post("/api/jobs", json={
        "company": "虚构公司", "title": "工程师", "jd": "岗位要求", "idempotency_key": "job",
    }, headers=headers).json()
    company = client.post("/api/domain/objects", json={
        "kind": "company", "name": "虚构公司", "idempotency_key": "company",
    }, headers=headers).json()
    relation = client.post("/api/domain/opportunities/" + job["id"], json={
        "company_id": company["id"], "expected_revision": job["revision"], "idempotency_key": "assign",
    }, headers=headers).json()
    preview = store.context(job["id"], "job")
    assert any(source["purpose"] == "company_identity" for source in preview["sources"])
    run = store.analyze(job["id"], "job", expected_epoch=preview["epoch"], idempotency_key="run")
    client.post("/api/domain/opportunities/" + job["id"], json={
        "company_id": company["id"], "expected_revision": relation["revision"], "idempotency_key": "assign-again",
    }, headers=headers)
    assert store.state()["runs"][0]["status"] == "stale"
    from workbench.core import Conflict
    import pytest
    with pytest.raises(Conflict):
        store.analyze(job["id"], "job", expected_epoch=preview["epoch"], idempotency_key="old-preview")
