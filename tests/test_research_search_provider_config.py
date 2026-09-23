"""Tavily configuration is a distinct, secret-free maintenance surface."""

import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.secret_store import MemorySecretStore, SecretStoreError
from workbench.providers import TestProvider


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}
FAKE_TAVILY_KEY = "fake-tv-key-7"


class TavilyConfigSecretStore(MemorySecretStore):
    def __init__(self):
        super().__init__()
        self.put_refs = []
        self.get_refs = []
        self.delete_refs = []
        self.read_failure = None

    def put(self, ref, value):
        saved = super().put(ref, value)
        self.put_refs.append(saved)
        return saved

    def get(self, ref):
        self.get_refs.append(ref)
        if self.read_failure:
            raise SecretStoreError(self.read_failure, "synthetic failure")
        return super().get(ref)

    def delete(self, ref):
        self.delete_refs.append(ref)
        super().delete(ref)


def client_for(tmp_path, monkeypatch, secrets):
    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    store = Store(tmp_path / "data", TestProvider(), secrets)
    return store, TestClient(create_app(store), headers=HEADERS)


def test_local_only_can_configure_tavily_without_exposing_secret_or_model_ref(tmp_path, monkeypatch, caplog):
    secrets = TavilyConfigSecretStore()
    store, client = client_for(tmp_path, monkeypatch, secrets)
    model_secret_ref = secrets.put(None, "synthetic-deepseek-secret")
    with store.connect() as connection:
        store._save(connection, "ai_model_config", {
            "id": "synthetic-model", "provider": "DeepSeek", "api_key_ref": model_secret_ref,
            "enabled": True,
        }, 0)
    secrets.put_refs.clear()

    before = client.get("/api/research/search-provider").json()
    response = client.put("/api/research/search-provider", json={
        "api_key": FAKE_TAVILY_KEY,
        "expected_revision": before["revision"],
    })
    assert response.status_code == 200, response.text
    configured = response.json()
    assert configured["provider"] == "tavily"
    assert configured["configured"] is True
    assert configured["secret_status"] == "ready"
    assert "secret_ref" not in configured
    assert "api_key" not in configured
    assert model_secret_ref not in secrets.put_refs
    assert len(secrets.put_refs) == 1
    assert secrets.put_refs[0] != model_secret_ref
    assert secrets.get_refs == [secrets.put_refs[0]]

    listing = client.get("/api/research/search-provider")
    assert listing.json() == configured
    assert FAKE_TAVILY_KEY not in listing.text
    assert FAKE_TAVILY_KEY not in response.text
    with store.connect(False) as connection:
        saved_rows = connection.execute("SELECT body FROM current").fetchall()
    persisted = "\n".join(row[0] for row in saved_rows)
    assert FAKE_TAVILY_KEY not in persisted
    assert FAKE_TAVILY_KEY.encode() not in store.db.read_bytes()
    assert "synthetic-deepseek-secret" not in store.db.read_bytes().decode(errors="ignore")
    assert FAKE_TAVILY_KEY not in caplog.text
    assert FAKE_TAVILY_KEY not in repr(sys.argv)
    assert FAKE_TAVILY_KEY not in os.environ.values()

    first_search_ref = secrets.put_refs[0]
    replacement = "fake-tv-replace-8"
    rotated = client.put("/api/research/search-provider", json={
        "api_key": replacement,
        "expected_revision": configured["revision"],
    })
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["configured"] is True
    assert rotated.json()["secret_status"] == "ready"
    assert first_search_ref in secrets.delete_refs
    assert model_secret_ref not in secrets.delete_refs
    assert secrets.put_refs[-1] != model_secret_ref
    assert secrets.values.get(model_secret_ref) == "synthetic-deepseek-secret"
    assert replacement not in rotated.text


@pytest.mark.parametrize("failure", ["timeout", "denied", "locked", "missing", "error"])
def test_tavily_key_readback_failure_does_not_switch_configuration(tmp_path, monkeypatch, failure):
    secrets = TavilyConfigSecretStore()
    secrets.read_failure = failure
    store, client = client_for(tmp_path, monkeypatch, secrets)

    response = client.put("/api/research/search-provider", json={
        "api_key": FAKE_TAVILY_KEY,
        "expected_revision": 0,
    })

    assert response.status_code == 422
    assert FAKE_TAVILY_KEY not in response.text
    assert client.get("/api/research/search-provider").json() == {
        "provider": "tavily", "configured": False,
        "secret_status": failure, "revision": 0,
    }
    assert secrets.delete_refs == secrets.put_refs
    with store.connect(False) as connection:
        rows = connection.execute("SELECT body FROM current").fetchall()
    assert all(FAKE_TAVILY_KEY not in row[0] for row in rows)


def test_tavily_status_after_restart_is_not_checked_without_keychain_read(tmp_path, monkeypatch):
    secrets = TavilyConfigSecretStore()
    store, client = client_for(tmp_path, monkeypatch, secrets)
    configured = client.put("/api/research/search-provider", json={
        "api_key": FAKE_TAVILY_KEY,
        "expected_revision": 0,
    })
    assert configured.status_code == 200
    secrets.get_refs.clear()

    restarted = Store(store.data_dir, TestProvider(), secrets)
    restarted_client = TestClient(create_app(restarted), headers=HEADERS)
    status = restarted_client.get("/api/research/search-provider").json()

    assert secrets.get_refs == []
    assert status["configured"] is True
    assert status["secret_status"] == "not_checked"
