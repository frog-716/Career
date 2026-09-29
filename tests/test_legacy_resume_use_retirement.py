"""Retired ResumeUse creation must not erase existing references."""

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


HEADERS = {"X-Career-Request": "1"}


def test_legacy_resume_use_post_is_rejected_without_writing(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    client = TestClient(create_app(store))
    role_response = client.post(
        "/api/domain/objects",
        json={"kind": "target_role", "name": "虚构分析方向", "idempotency_key": "role"},
        headers=HEADERS,
    )
    assert role_response.status_code == 200, role_response.text
    role_id = role_response.json()["id"]
    with store.connect() as db:
        store._record(db, "editor_version", {"id": "historical-version", "name": "旧版本", "artifact_id": "historical-pdf"})
        store._record(db, "artifact", {"id": "historical-pdf", "sha256": "synthetic-pdf-hash"})
        store._record(db, "resume_use", {
            "id": "historical-use", "scope_type": "role", "scope_id": role_id,
            "version_id": "historical-version", "artifact_id": "historical-pdf",
        })
        before = db.execute(
            "SELECT kind, id, body FROM records WHERE kind IN ('resume_use', 'domain_command') ORDER BY kind, id"
        ).fetchall()

    body = {
        "version_id": "historical-version", "scope_type": "role",
        "scope_id": role_id, "idempotency_key": "new-use",
    }
    for _ in range(2):
        response = client.post("/api/domain/resume-uses", json=body, headers=HEADERS)
        assert response.status_code == 409, response.text
        assert "legacy_resume_use_retired" in response.text

    with store.connect(False) as db:
        after = db.execute(
            "SELECT kind, id, body FROM records WHERE kind IN ('resume_use', 'domain_command') ORDER BY kind, id"
        ).fetchall()
        assert store._get(db, "historical-version", "editor_version", True)["artifact_id"] == "historical-pdf"
        assert store._get(db, "historical-pdf", "artifact", True)["sha256"] == "synthetic-pdf-hash"
    assert after == before
    assert client.get("/api/domain").json()["resume_uses"] == [{
        "id": "historical-use", "scope_type": "role", "scope_id": role_id,
        "version_id": "historical-version", "artifact_id": "historical-pdf",
    }]
