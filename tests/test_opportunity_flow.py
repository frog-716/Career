import base64

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


HEADERS = {"X-Career-Request": "1"}


def post(client, path, body):
    return client.post("/api" + path, json=body, headers=HEADERS)


def test_opportunity_submission_freezes_relationships_and_status_history(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    client = TestClient(create_app(store))
    created = post(client, "/opportunities", {
        "company": "虚构公司", "title": "后端工程师", "jd": "原始 JD",
    })
    assert created.status_code == 200, created.text
    opportunity = created.json()
    assert opportunity["id"].startswith("opportunity:")
    job_id = opportunity["legacy_job_id"]

    company = post(client, "/domain/objects", {
        "kind": "company", "name": "虚构公司", "idempotency_key": "company",
    }).json()
    role = post(client, "/domain/objects", {
        "kind": "target_role", "name": "服务端", "idempotency_key": "role",
    }).json()
    cycle = post(client, "/domain/objects", {
        "kind": "search_cycle", "name": "秋招", "idempotency_key": "cycle",
    }).json()
    relation = post(client, "/domain/opportunities/" + opportunity["id"], {
        "company_id": company["id"], "target_role_id": role["id"],
        "search_cycle_id": cycle["id"], "expected_revision": 0,
    })
    assert relation.status_code == 200, relation.text

    document = client.get("/api/editor").json()["document"]
    document["profile"]["name"] = "冻结版本"
    saved = client.put("/api/editor", json={"document": document, "expected_revision": 0}, headers=HEADERS)
    assert saved.status_code == 200, saved.text
    version = post(client, "/editor/versions", {
        "document": document, "expected_revision": saved.json()["revision"],
        "name": "正式版本", "pdf_base64": base64.b64encode(b"%PDF-1.7\nsynthetic\n%%EOF").decode(),
        "idempotency_key": "version-1",
    }).json()
    use = post(client, "/domain/resume-uses", {
        "scope_type": "job", "scope_id": job_id, "version_id": version["id"],
        "idempotency_key": "use-1",
    })
    assert use.status_code == 200, use.text
    assert use.json()["scope_type"] == "opportunity"
    assert use.json()["scope_id"] == opportunity["id"]

    submission = post(client, "/applications", {
        "opportunity_id": opportunity["id"], "version_id": version["id"],
        "artifact_id": version["artifact_id"], "applied_at": "2026-09-15T10:00:00+08:00",
        "channel": "招聘平台", "status": "applied", "idempotency_key": "submission-1",
    })
    assert submission.status_code == 200, submission.text
    frozen = submission.json()
    assert frozen["opportunity_snapshot"]["job_posting"]["jd"] == "原始 JD"
    assert frozen["opportunity_snapshot"]["relations"]["target_role_id"]["name"] == "服务端"
    assert len(frozen["status_history"]) == 1

    updated = post(client, "/opportunities/" + opportunity["id"], {
        "company": "虚构公司", "title": "后端工程师", "jd": "更新 JD",
        "expected_revision": opportunity["revision"],
    })
    assert updated.status_code == 200, updated.text
    status = post(client, "/applications/" + frozen["id"] + "/status", {"status": "interviewing"})
    assert status.status_code == 200, status.text
    assert len(status.json()["status_history"]) == 2
    assert status.json()["opportunity_snapshot"] == frozen["opportunity_snapshot"]

    reopened = Store(store.data_dir, TestProvider())
    state = reopened.state()
    assert state["opportunities"][0]["jd"] == "更新 JD"
    assert state["applications"][0]["opportunity_snapshot"] == frozen["opportunity_snapshot"]
    assert state["applications"][0]["status_history"] == status.json()["status_history"]
    assert state["jobs"][0]["id"] == job_id
