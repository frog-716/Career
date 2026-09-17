import base64
import hashlib
import json
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from workbench.core import Conflict, Invalid, Store
from workbench.backup import backup, restore
from workbench.editor import editor_router
from workbench.providers import TestProvider


def client_for(tmp_path):
    store = Store(tmp_path, TestProvider())
    app = FastAPI()
    app.add_exception_handler(Invalid, lambda request, exc: JSONResponse({"detail": str(exc)}, status_code=422))
    app.add_exception_handler(Conflict, lambda request, exc: JSONResponse({"detail": str(exc)}, status_code=409))
    app.include_router(editor_router(store))
    return TestClient(app), store


def doc(label="A"):
    return {"schemaVersion": 1, "profile": {"id": "profile", "name": label, "contacts": []}, "sections": [{"id": "experience", "type": "experience", "title": "经历", "items": [{"id": "item-1", "organization": "Org", "role": "Role", "date": "2020", "bullets": [{"id": "bullet-1", "content": label}]}]}], "formatting": {"font": "sans"}, "meta": {"title": label}}


def pdf():
    return base64.b64encode(b"%PDF-1.7\n1 0 obj\nendobj\n%%EOF\n").decode()


def test_structured_draft_conflict_and_blank_is_read_only(tmp_path):
    client, store = client_for(tmp_path)
    assert client.get("/api/editor").json() == {"document": {"schemaVersion": 1, "profile": {"id": "profile-main", "name": "", "contacts": []}, "sections": [], "formatting": {}, "meta": {}}, "revision": 0, "savedAt": None}
    assert not (store.data_dir / "artifacts").exists()
    saved = client.put("/api/editor", json={"document": doc(), "expected_revision": 0}).json()
    assert saved["revision"] == 1 and saved["document"]["sections"][0]["items"][0]["id"] == "item-1"
    assert client.put("/api/editor", json={"document": doc("B"), "expected_revision": 0}).status_code == 409


def test_version_pdf_freeze_idempotency_restore_and_backup_compatibility(tmp_path):
    client, store = client_for(tmp_path)
    document = doc()
    client.put("/api/editor", json={"document": document, "expected_revision": 0})
    body = {"name": "v1", "document": document, "expected_revision": 1, "pdf_base64": pdf(), "idempotency_key": "version-key"}
    created = client.post("/api/editor/versions", json=body).json()
    replay = client.post("/api/editor/versions", json=body).json()
    assert replay == created
    assert client.post("/api/editor/versions", json={**body, "name": "v2"}).status_code == 409
    assert client.get("/api/editor/versions/" + created["id"]).json()["document"] == document
    artifact = store.state()["artifacts"][0]
    assert hashlib.sha256(store.artifact(artifact["id"])[0].read_bytes()).hexdigest() == artifact["sha256"]
    changed = doc("B")
    client.put("/api/editor", json={"document": changed, "expected_revision": 1})
    restored = client.post("/api/editor/restore", json={"version_id": created["id"], "expected_revision": 2}).json()
    assert restored["revision"] == 3
    with store.connect(False) as c:
        recovery = json.loads(c.execute("SELECT body FROM records WHERE kind='editor_recovery'").fetchone()[0])
    assert recovery["previous_revision"] == 2 and recovery["before"] == changed
    assert store.state()["versions"] == []
    assert store.state()["artifacts"][0]["sha256"] == artifact["sha256"]
    bundle = backup(store.data_dir, tmp_path / "backups")
    restore(bundle, tmp_path / "restored")
    restored_store = Store(tmp_path / "restored", TestProvider())
    assert restored_store.artifact(artifact["id"])[0].read_bytes() == store.artifact(artifact["id"])[0].read_bytes()
    with restored_store.connect(False) as c:
        assert json.loads(c.execute("SELECT body FROM current WHERE id='editor-main'").fetchone()[0])["document"] == document


def test_delete_unreferenced_editor_version_removes_pdf_and_rejects_used_version(tmp_path):
    client, store = client_for(tmp_path)
    document = doc()
    client.put("/api/editor", json={"document": document, "expected_revision": 0})
    body = {"name": "可删除版本", "document": document, "expected_revision": 1, "pdf_base64": pdf(), "idempotency_key": "delete-version-key"}
    created = client.post("/api/editor/versions", json=body).json()
    artifact_path = store.state()["artifacts"][0]["path"]
    assert client.delete("/api/editor/versions/" + created["id"]).json() == {"deleted": created["id"]}
    assert store.state()["versions"] == []
    assert store.state()["artifacts"] == []
    assert not (store.data_dir / artifact_path).exists()

    kept = client.post("/api/editor/versions", json={**body, "name": "已关联版本", "idempotency_key": "kept-version-key"}).json()
    with store.connect() as c:
        store._record(c, "resume_use", {"id": "use-version-delete-test", "version_id": kept["id"]})
    response = client.delete("/api/editor/versions/" + kept["id"])
    assert response.status_code == 409
    assert "关联" in response.json()["detail"]


def test_validation_and_context_isolation(tmp_path):
    client, store = client_for(tmp_path)
    assert client.put("/api/editor", json={"document": {"schemaVersion": 2}, "expected_revision": 0}).status_code == 422
    client.put("/api/editor", json={"document": doc("editor-only-private-sentinel"), "expected_revision": 0})
    assert client.post("/api/editor/versions", json={"name": "v", "document": doc("other"), "expected_revision": 1, "pdf_base64": pdf(), "idempotency_key": "k"}).status_code == 409
    store.save_profile("current profile", 0)
    job = store.save_job({"company": "C", "title": "T", "jd": "J"})
    packet = store.context(job["id"], "job")
    assert len(packet['sources']) == 2
    assert "editor-only-private-sentinel" not in json.dumps(packet)


def test_reject_shapes_that_would_be_lost_by_editor_normalization(tmp_path):
    client, _ = client_for(tmp_path)
    invalid = doc()
    duplicate = deepcopy(invalid['sections'][0])
    duplicate['id'] = 'another-experience'
    duplicate['items'] = []
    invalid['sections'].append(duplicate)
    assert client.put('/api/editor', json={'document': invalid, 'expected_revision': 0}).status_code == 422
    invalid = doc()
    invalid['sections'][0]['items'][0]['bullets'] = 'invalid-array'
    assert client.put('/api/editor', json={'document': invalid, 'expected_revision': 0}).status_code == 422


def test_same_idempotency_key_concurrent_requests_create_one_version(tmp_path):
    client, store = client_for(tmp_path)
    document = doc()
    assert client.put("/api/editor", json={"document": document, "expected_revision": 0}).status_code == 200
    body = {"name": "v1", "document": document, "expected_revision": 1, "pdf_base64": pdf(), "idempotency_key": "concurrent"}
    def request(_):
        with TestClient(client.app) as c:
            return c.post("/api/editor/versions", json=body).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(request, (1, 2)))
    assert statuses == [200, 200]
    with store.connect(False) as c:
        assert c.execute("SELECT count(*) FROM records WHERE kind='editor_version'").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM records WHERE kind='artifact'").fetchone()[0] == 1
