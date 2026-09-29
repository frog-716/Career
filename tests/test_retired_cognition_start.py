"""The D4 value verdict closes new automatic synthesis, not old proposal reads."""

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


def test_cognition_compiler_rejects_new_prepare_and_execute_without_provider(tmp_path):
    provider = TestProvider()
    calls = []
    provider.complete = lambda payload: calls.append(payload)
    store = Store(tmp_path / "data", provider)
    client = TestClient(create_app(store), headers={"X-Career-Request": "1"})
    before = store.db.read_bytes()
    for endpoint in ("prepare", "execute"):
        response = client.post(f"/api/wiki/cognition/compiler/{endpoint}", json={})
        assert response.status_code == 409, response.text
        assert "retired" in response.json()["detail"]
    assert calls == []
    assert store.db.read_bytes() == before
    assert client.get("/api/wiki/cognition/proposals").status_code == 200
    assert client.get("/api/wiki/cognition/workspace").status_code == 200
