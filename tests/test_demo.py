import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.core import Conflict, Invalid, Missing, Store
from workbench.demo import DATASET_ID, demo_router
from workbench.engagement import engagement_router
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
    app.include_router(demo_router(store))
    app.include_router(work_router(store))
    app.include_router(engagement_router(store))
    return TestClient(app), store


def counts(store):
    with store.connect(False) as c:
        return {
            "current": c.execute("SELECT count(*) FROM current WHERE json_extract(body,'$.demo_dataset_id')=?", (DATASET_ID,)).fetchone()[0],
            "records": c.execute("SELECT count(*) FROM records WHERE json_extract(body,'$.demo_dataset_id')=?", (DATASET_ID,)).fetchone()[0],
            "applications": c.execute("SELECT count(*) FROM applications WHERE json_extract(body,'$.demo_dataset_id')=?", (DATASET_ID,)).fetchone()[0],
        }


def test_demo_load_is_complete_idempotent_restartable_and_removable(tmp_path):
    client, store = client_for(tmp_path)
    sentinel_profile = store.save_profile("真实哨兵资料", 0)
    sentinel_job = store.save_job({"company": "真实公司", "title": "真实岗位", "jd": "真实 JD"})
    first = client.post("/api/demo/load")
    assert first.status_code == 200, first.text
    loaded = first.json()
    assert loaded["dataset_id"] == DATASET_ID
    assert counts(store)["current"] >= 15 and counts(store)["records"] >= 15
    demo_packet = store.context("demo-b5-job", "job", wiki_ids=["demo-b5-wiki-entry-1"])
    assert "真实哨兵资料" not in json.dumps(demo_packet, ensure_ascii=False)
    work_domain = client.get("/api/work-domain").json()
    assert any(item["id"] == "employment:demo-b5-episode" for item in work_domain["employments"])
    assert [item["id"] for item in work_domain["stages"]] == ["demo-b5-stage"]
    activity = client.get("/api/opportunity-activity").json()
    assert [len(activity[key]) for key in ("research_snapshots", "communications", "interviews", "offers")] == [1, 1, 1, 1]
    assert activity["legacy_projections"] == []
    with store.connect(False) as c:
        kinds = {row[0] for row in c.execute("SELECT kind FROM current WHERE json_extract(body,'$.demo_dataset_id')=?", (DATASET_ID,))}
        record_kinds = {row[0] for row in c.execute("SELECT kind FROM records WHERE json_extract(body,'$.demo_dataset_id')=?", (DATASET_ID,))}
        assert {"job", "opportunity", "opportunity_context", "journey_plan", "journey_episode", "employment", "work_employment_stage", "wiki_entry", "knowledge_candidate", "domain_company", "domain_org_unit", "domain_target_role", "domain_search_cycle", "work_project", "work_person", "work_achievement"} <= kinds
        assert {"journey_note", "research_snapshot", "communication", "interview", "offer", "knowledge_source", "work_project_source", "work_project_participant", "work_event", "work_evidence", "work_evidence_link", "editor_version", "artifact", "resume_use", "run", "feedback"} <= record_kinds
        submission = c.execute("SELECT body FROM applications WHERE json_extract(body,'$.demo_dataset_id')=?", (DATASET_ID,)).fetchone()
        assert submission
        assert all(json.loads(row[0]).get("demo_dataset_id") == DATASET_ID for row in c.execute("SELECT body FROM revisions WHERE json_extract(body,'$.demo_dataset_id')=?", (DATASET_ID,)))
    pdf = store.data_dir / "artifacts/demo-b5-resume-pdf.pdf"
    assert pdf.read_bytes().startswith(b"%PDF")
    before = counts(store)
    second = client.post("/api/demo/load")
    assert second.status_code == 200 and second.json()["status"] == "already_loaded"
    assert counts(store) == before
    reopened = Store(tmp_path / "data", TestProvider())
    assert counts(reopened) == before
    removed = client.post("/api/demo/remove")
    assert removed.status_code == 200
    assert counts(store) == {"current": 0, "records": 0, "applications": 0}
    assert not pdf.exists()
    assert store.state()["profile"] == sentinel_profile
    assert store.state()["jobs"] == [sentinel_job]


def test_demo_rejects_id_collision_and_does_not_remove_unrelated_data(tmp_path):
    client, store = client_for(tmp_path)
    with store.connect() as c:
        c.execute("INSERT INTO records VALUES(?,?,?)", ("demo-b5-job", "foreign", '{"id":"demo-b5-job","demo_dataset_id":"other"}'))
    response = client.post("/api/demo/load")
    assert response.status_code == 409
    assert counts(store) == {"current": 0, "records": 0, "applications": 0}
