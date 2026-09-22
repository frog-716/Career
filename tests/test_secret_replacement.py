from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from workbench.ai_config import (
    CLEANUP_POLICY_MANUAL,
    SECRET_OPERATION_KIND,
    recover_secret_operations,
)
from workbench.app import create_app
from workbench.core import Conflict, Store
from workbench.providers import LocalOnlyDisabled, TestProvider
from workbench.secret_store import MemorySecretStore, SecretStoreError


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


def payload(key: str = "fake-key-1", **changes):
    value = {
        "display_name": "Synthetic model",
        "provider": "OpenAI-compatible",
        "base_url": "https://example.test/v1",
        "model": "fake-model",
        "api_key": key,
        "enabled": True,
    }
    value.update(changes)
    return value


class FaultInjectingSecretStore(MemorySecretStore):
    def __init__(self):
        super().__init__()
        self.next_get_error: str | None = None
        self.mismatch_ref: str | None = None
        self.get_refs: list[str] = []
        self.deleted_refs: list[str] = []

    def get(self, ref: str) -> str:
        self.get_refs.append(ref)
        if self.next_get_error:
            code = self.next_get_error
            self.next_get_error = None
            raise SecretStoreError(code, "fake read-back failure")
        value = super().get(ref)
        if ref == self.mismatch_ref:
            return "different-fake-key"
        return value

    def delete(self, ref: str) -> None:
        self.deleted_refs.append(ref)
        super().delete(ref)


def make_client(tmp_path, monkeypatch, mode="AI_ENABLED", secret_store=None):
    monkeypatch.setenv("CAREER_AI_MODE", mode)
    store = Store(tmp_path / "data", TestProvider(), secret_store or FaultInjectingSecretStore())
    client = TestClient(
        create_app(store),
        base_url="http://127.0.0.1",
        headers=HEADERS,
    )
    return store, client


def current_config(store, config_id):
    with store.connect(False) as connection:
        return store._get(connection, config_id, "ai_model_config")


def latest_operation(store):
    with store.connect(False) as connection:
        return store._records(connection, SECRET_OPERATION_KIND)[0]


def test_put_read_back_then_cas_switches_config(tmp_path, monkeypatch):
    secrets = FaultInjectingSecretStore()
    store, client = make_client(tmp_path, monkeypatch, secret_store=secrets)
    created = client.post("/api/ai/models", json=payload()).json()

    with store.connect(False) as connection:
        created_config = store._get(connection, created["id"], "ai_model_config")
    old_ref = created_config["api_key_ref"]
    before_gets = len(secrets.get_refs)

    updated = client.put(
        f"/api/ai/models/{created['id']}",
        json={**payload("fake-key-2"), "expected_revision": created["revision"]},
    )

    assert updated.status_code == 200, updated.text
    body = updated.json()
    saved = current_config(store, created["id"])
    assert saved["api_key_ref"] != old_ref
    assert saved["secret_status"] == "ready"
    assert len(secrets.get_refs) == before_gets + 1
    assert secrets.get_refs[-1] == saved["api_key_ref"]
    assert latest_operation(store)["phase"] == "cleaned"
    assert "fake-key-2" not in json.dumps(body)


@pytest.mark.parametrize(
    "failure",
    ["timeout", "denied", "locked", "interaction_not_allowed", "error"],
)
def test_read_back_failure_keeps_old_ref_and_cleans_new_ref(tmp_path, monkeypatch, failure):
    secrets = FaultInjectingSecretStore()
    store, client = make_client(tmp_path, monkeypatch, secret_store=secrets)
    created = client.post("/api/ai/models", json=payload()).json()
    original = current_config(store, created["id"])
    secrets.next_get_error = failure

    response = client.put(
        f"/api/ai/models/{created['id']}",
        json={**payload("fake-key-2"), "expected_revision": created["revision"]},
    )

    assert response.status_code == 422
    assert current_config(store, created["id"])["api_key_ref"] == original["api_key_ref"]
    assert set(secrets.values) == {original["api_key_ref"]}
    assert latest_operation(store)["phase"] == "cleaned"
    assert latest_operation(store)["error_code"] == failure


def test_read_back_mismatch_keeps_old_ref(tmp_path, monkeypatch):
    secrets = FaultInjectingSecretStore()
    store, client = make_client(tmp_path, monkeypatch, secret_store=secrets)
    created = client.post("/api/ai/models", json=payload()).json()
    original = current_config(store, created["id"])
    secrets.mismatch_ref = "next-ref"

    original_allocate = secrets.allocate_ref
    secrets.allocate_ref = lambda: "next-ref"
    try:
        response = client.put(
            f"/api/ai/models/{created['id']}",
            json={**payload("fake-key-2"), "expected_revision": created["revision"]},
        )
    finally:
        secrets.allocate_ref = original_allocate

    assert response.status_code == 422
    assert current_config(store, created["id"])["api_key_ref"] == original["api_key_ref"]
    assert latest_operation(store)["error_code"] == "error"
    assert "next-ref" not in secrets.values


def test_cas_conflict_cleans_verified_new_ref_without_touching_old(tmp_path, monkeypatch):
    secrets = FaultInjectingSecretStore()
    store, client = make_client(tmp_path, monkeypatch, secret_store=secrets)
    created = client.post("/api/ai/models", json=payload()).json()
    original = current_config(store, created["id"])
    original_save = store._save

    def conflict_on_new_config(connection, kind, value, expected):
        if kind == "ai_model_config" and value.get("api_key_ref") != original["api_key_ref"]:
            raise Conflict("synthetic CAS conflict")
        return original_save(connection, kind, value, expected)

    store._save = conflict_on_new_config
    response = client.put(
        f"/api/ai/models/{created['id']}",
        json={**payload("fake-key-2"), "expected_revision": created["revision"]},
    )

    assert response.status_code == 409
    assert current_config(store, created["id"])["api_key_ref"] == original["api_key_ref"]
    assert set(secrets.values) == {original["api_key_ref"]}


def test_cleanup_hold_skips_normal_and_recovery_deletes(tmp_path, monkeypatch):
    secrets = FaultInjectingSecretStore()
    store, client = make_client(tmp_path, monkeypatch, secret_store=secrets)
    created = client.post("/api/ai/models", json=payload()).json()
    original = current_config(store, created["id"])

    held = client.post(
        f"/api/ai/models/{created['id']}/secret-cleanup-hold",
        json={"expected_revision": created["revision"]},
    )
    assert held.status_code == 200, held.text
    held_revision = held.json()["revision"]
    assert held.json()["cleanup_pending"] is True
    assert held.json()["cleanup_state"] == CLEANUP_POLICY_MANUAL

    updated = client.put(
        f"/api/ai/models/{created['id']}",
        json={**payload("fake-key-2"), "expected_revision": held_revision},
    )
    assert updated.status_code == 200, updated.text
    saved = current_config(store, created["id"])
    assert saved["api_key_ref"] != original["api_key_ref"]
    assert updated.json()["cleanup_state"] == CLEANUP_POLICY_MANUAL
    assert original["api_key_ref"] in secrets.values
    assert original["api_key_ref"] not in secrets.deleted_refs
    operation = latest_operation(store)
    assert operation["cleanup_policy"] == CLEANUP_POLICY_MANUAL
    assert operation["cleanup_state"] == CLEANUP_POLICY_MANUAL
    assert operation["phase"] == "cleanup_pending"
    assert original["api_key_ref"] not in secrets.get_refs[1:]

    before = list(secrets.deleted_refs)
    reopened = Store(store.data_dir, TestProvider(), secrets)
    recover_secret_operations(reopened)
    assert secrets.deleted_refs == before
    assert original["api_key_ref"] in secrets.values


def test_secret_verified_crash_recovery_removes_only_new_ref(tmp_path, monkeypatch):
    secrets = FaultInjectingSecretStore()
    store, client = make_client(tmp_path, monkeypatch, secret_store=secrets)
    created = client.post("/api/ai/models", json=payload()).json()
    original = current_config(store, created["id"])
    orphan = "orphan-after-verify"
    secrets.put(orphan, "fake-key-orphan")
    with store.connect() as connection:
        store._record(
            connection,
            SECRET_OPERATION_KIND,
            {
                "id": "ai-secret-operation:crash-after-verify",
                "operation_id": "crash-after-verify",
                "config_id": created["id"],
                "expected_revision": created["revision"],
                "old_ref": original["api_key_ref"],
                "new_ref": orphan,
                "phase": "secret_verified",
                "cleanup_policy": "automatic",
                "created_at": "2026-09-22T00:00:00+00:00",
                "updated_at": "2026-09-22T00:00:00+00:00",
                "error_code": None,
            },
        )

    reopened = Store(store.data_dir, TestProvider(), secrets)
    assert orphan not in secrets.values
    assert original["api_key_ref"] in secrets.values
    assert reopened.runtime_mode.ai_enabled


def test_local_only_allows_secret_maintenance_but_not_outbound(tmp_path, monkeypatch):
    secrets = FaultInjectingSecretStore()
    store, client = make_client(tmp_path, monkeypatch, mode="LOCAL_ONLY", secret_store=secrets)
    created = client.post("/api/ai/models", json=payload()).json()
    assert created["configured_ref"] is True
    assert created["secret_status"] == "ready"
    original = current_config(store, created["id"])
    updated = client.put(
        f"/api/ai/models/{created['id']}",
        json={**payload("fake-key-2"), "expected_revision": created["revision"]},
    )
    assert updated.status_code == 200, updated.text
    assert current_config(store, created["id"])["api_key_ref"] != original["api_key_ref"]
    assert "fake-key-2" not in json.dumps(updated.json())
    assert b"fake-key-2" not in (store.data_dir / "workspace.sqlite3").read_bytes()

    connection_test = client.post(
        "/api/ai/test-connection",
        json={
            "provider": "OpenAI-compatible",
            "base_url": "https://example.test/v1",
            "model": "fake-model",
            "api_key": "fake-key-connection-test",
        },
    )
    assert connection_test.status_code == 503
    with pytest.raises(LocalOnlyDisabled):
        store.provider.complete({})
