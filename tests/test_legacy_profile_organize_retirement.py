"""Profile migration must archive old text without creating retired Wiki objects."""

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


HEADERS = {"X-Career-Request": "1"}


def test_profile_organize_archives_old_text_as_raw_without_legacy_candidate(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    client = TestClient(create_app(store), headers=HEADERS)
    old = client.post("/api/profile", json={
        "content": "虚构旧资料：不接受出差", "expected_revision": 0,
    }).json()
    body = {"expected_revision": old["revision"], "basics": {
        "name": "虚构甲", "email": "test@example.invalid", "phone": ""},
        "confirmed": True, "entries": [], "idempotency_key": "archive-old-profile"}
    response = client.post("/api/profile/organize", json=body)
    assert response.status_code == 200, response.text
    assert client.post("/api/profile/organize", json=body).json() == response.json()
    with store.connect(False) as connection:
        raw = store._records(connection, "raw_material")
        assert len(raw) == 1 and raw[0]["content"] == old["content"]
        assert raw[0]["provenance"]["kind"] == "profile_archive"
        assert store._records(connection, "knowledge_source") == []
        assert store._current(connection, "knowledge_candidate") == []


def test_profile_organize_refuses_old_candidate_payload_without_writing(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    client = TestClient(create_app(store), headers=HEADERS)
    old = client.post("/api/profile", json={"content": "虚构旧资料", "expected_revision": 0}).json()
    body = {"expected_revision": old["revision"], "basics": {
        "name": "虚构乙", "email": "test@example.invalid", "phone": ""},
        "confirmed": True, "entries": [{"title": "旧候选", "content": "不应写入",
                                          "entry_type": "constraint"}], "idempotency_key": "legacy-entry"}
    with store.connect(False) as connection:
        before = connection.execute("SELECT epoch FROM meta WHERE id=1").fetchone()[0]
    response = client.post("/api/profile/organize", json=body)
    assert response.status_code == 409
    with store.connect(False) as connection:
        assert connection.execute("SELECT epoch FROM meta WHERE id=1").fetchone()[0] == before
        assert store._records(connection, "knowledge_source") == []
        assert store._current(connection, "knowledge_candidate") == []
