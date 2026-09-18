from batch_b_helpers import save_job
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


def test_v2_demo_pack_cannot_reintroduce_legacy_writes_or_remove_data(tmp_path):
    client, store = client_for(tmp_path)
    store.save_profile("虚构哨兵资料", 0)
    save_job(store, {"company":"虚构公司", "title":"岗位", "jd":"JD"})
    before=store.db.read_bytes()
    for path in ('/api/demo/load','/api/demo/remove'):
        response=client.post(path)
        assert response.status_code==409
        assert 'legacy_demo_disabled' in response.text
        assert store.db.read_bytes()==before


def test_demo_rejects_id_collision_and_does_not_remove_unrelated_data(tmp_path):
    client, store = client_for(tmp_path)
    with store.connect() as c:
        c.execute("INSERT INTO records VALUES(?,?,?)", ("demo-b5-job", "foreign", '{"id":"demo-b5-job","demo_dataset_id":"other"}'))
    response = client.post("/api/demo/load")
    assert response.status_code == 409
    assert counts(store) == {"current": 0, "records": 0, "applications": 0}
