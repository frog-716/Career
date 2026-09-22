import json
import sqlite3
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.backup import backup
from workbench.core import Invalid, Store
from workbench.ai_config import SECRET_OPERATION_KIND
from workbench.model_gateway import OpenAICompatibleAdapter
from workbench.secret_store import KeychainSecretStore, MemorySecretStore, SecretStoreError
from workbench.providers import TestProvider


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


def _client(tmp_path, secrets=None):
    store = Store(tmp_path / "data", TestProvider(), secrets or MemorySecretStore())
    return store, TestClient(create_app(store), headers=HEADERS)


def _payload(**overrides):
    value = {
        "display_name": "Synthetic model",
        "provider": "OpenAI-compatible",
        "base_url": "https://example.test/v1",
        "model": "fake-model",
        "api_key": "fake-key-1",
        "enabled": True,
    }
    value.update(overrides)
    return value


def test_destination_change_without_new_key_is_rejected_and_old_secret_remains(tmp_path):
    secrets = MemorySecretStore()
    store, client = _client(tmp_path, secrets)
    created = client.post("/api/ai/models", json=_payload()).json()

    response = client.put(
        f"/api/ai/models/{created['id']}",
        json={
            **_payload(base_url="https://other.test/v1", api_key=""),
            "expected_revision": created["revision"],
        },
    )

    assert response.status_code == 422
    with store.connect(False) as connection:
        config = store._get(connection, created["id"], "ai_model_config")
    assert secrets.get(config["api_key_ref"]) == "fake-key-1"


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "Another-provider"},
        {"base_url": "https://example.test:8443/v1"},
        {"base_url": "https://example.test/v2"},
    ],
)
def test_any_destination_identity_change_requires_a_new_key(tmp_path, changes):
    _, client = _client(tmp_path)
    created = client.post("/api/ai/models", json=_payload()).json()
    response = client.put(
        f"/api/ai/models/{created['id']}",
        json={**_payload(api_key=""), **changes, "expected_revision": created["revision"]},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:password@example.test/v1",
        "https://example.test/v1?token=fake-key",
        "https://example.test/v1#fragment",
        "http://external.example/v1",
    ],
)
def test_save_rejects_unsafe_destination_urls(tmp_path, base_url):
    _, client = _client(tmp_path)
    response = client.post("/api/ai/models", json=_payload(base_url=base_url))
    assert response.status_code == 422


def test_public_dto_separates_configured_ref_from_secret_status(tmp_path):
    _, client = _client(tmp_path)
    response = client.post("/api/ai/models", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["configured_ref"] is True
    assert body["secret_status"] == "ready"
    assert "fake-key-1" not in json.dumps(body)


def test_keychain_store_accepts_explicit_backend_without_subprocess_secret_argv(monkeypatch):
    class FakeBackend:
        priority = 1

        def __init__(self):
            self.values = {}

        def set_password(self, service, username, password):
            self.values[(service, username)] = password

        def get_password(self, service, username):
            return self.values.get((service, username))

        def delete_password(self, service, username):
            self.values.pop((service, username), None)

    def fail_subprocess(*args, **kwargs):
        raise AssertionError("KeychainSecretStore must not invoke security subprocess")

    monkeypatch.setattr("subprocess.run", fail_subprocess)
    backend = FakeBackend()
    secrets = KeychainSecretStore(backend=backend, platform_name="Darwin")

    ref = secrets.put(None, "fake-key")
    assert secrets.get(ref) == "fake-key"
    secrets.delete(ref)
    assert backend.values == {}


class TracedMemorySecretStore(MemorySecretStore):
    def __init__(self):
        super().__init__()
        self.events = []
        self.store = None

    def put(self, ref, value):
        result = super().put(ref, value)
        self.events.append(("put", result))
        return result

    def delete(self, ref):
        if self.store is not None and ref:
            with sqlite3.connect(str(self.store.db)) as connection:
                row = connection.execute(
                    "SELECT body FROM current WHERE kind='ai_model_config'"
                ).fetchall()
            assert all(ref not in body for (body,) in row), "old ref was deleted before config switch"
        self.events.append(("delete", ref))
        return super().delete(ref)


def test_replacing_a_key_allocates_a_new_ref_and_deletes_old_only_after_switch(tmp_path):
    secrets = TracedMemorySecretStore()
    store, client = _client(tmp_path, secrets)
    secrets.store = store
    created = client.post("/api/ai/models", json=_payload()).json()
    with store.connect(False) as connection:
        old_ref = store._get(connection, created["id"], "ai_model_config")["api_key_ref"]

    response = client.put(
        f"/api/ai/models/{created['id']}",
        json={**_payload(api_key="fake-key-2"), "expected_revision": created["revision"]},
    )

    assert response.status_code == 200, response.text
    with store.connect(False) as connection:
        updated = store._get(connection, created["id"], "ai_model_config")
    assert updated["api_key_ref"] != old_ref
    assert secrets.get(updated["api_key_ref"]) == "fake-key-2"
    assert old_ref not in secrets.values
    assert [event[0] for event in secrets.events] == ["put", "put", "delete"]


def test_equivalent_destination_normalization_does_not_require_a_new_key(tmp_path):
    store, client = _client(tmp_path)
    created = client.post(
        "/api/ai/models",
        json=_payload(base_url="HTTPS://EXAMPLE.TEST:443/v1/"),
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["base_url"] == "https://example.test/v1"

    response = client.put(
        f"/api/ai/models/{body['id']}",
        json={
            **_payload(base_url="https://example.test/v1", api_key=""),
            "expected_revision": body["revision"],
        },
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:password@example.test/v1",
        "https://example.test/v1?token=fake-key",
        "https://example.test/v1#fragment",
        "http://external.example/v1",
    ],
)
def test_ephemeral_connection_test_uses_the_same_destination_policy(tmp_path, base_url):
    _, client = _client(tmp_path)
    response = client.post(
        "/api/ai/test-connection",
        json={"provider": "OpenAI-compatible", "base_url": base_url, "model": "fake", "api_key": "fake-key"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:password@example.test/v1",
        "https://example.test/v1?token=fake-key",
        "https://example.test/v1#fragment",
        "http://external.example/v1",
    ],
)
def test_formal_adapter_uses_the_same_destination_policy(base_url):
    with pytest.raises(Invalid):
        OpenAICompatibleAdapter(
            {"provider": "OpenAI-compatible", "base_url": base_url, "model": "fake"},
            "fake-key",
        )


def test_keychain_failures_are_classified_without_secret_text():
    class Locked(Exception):
        pass

    class DeleteFailure(Exception):
        pass

    class FailingBackend:
        def set_password(self, *args):
            raise Locked("fake-key must not be surfaced")

        def get_password(self, *args):
            raise Locked("fake-key must not be surfaced")

        def delete_password(self, *args):
            raise DeleteFailure("fake-key must not be surfaced")

    secrets = KeychainSecretStore(backend=FailingBackend(), platform_name="Darwin")
    with pytest.raises(SecretStoreError) as put_error:
        secrets.put(None, "fake-key")
    assert put_error.value.code == "locked"
    assert "fake-key" not in str(put_error.value)
    with pytest.raises(SecretStoreError) as get_error:
        secrets.get("known-ref")
    assert get_error.value.code == "locked"
    with pytest.raises(SecretStoreError) as delete_error:
        secrets.delete("known-ref")
    assert delete_error.value.code == "error"

    class MissingBackend:
        def get_password(self, *args):
            return None

    with pytest.raises(SecretStoreError) as missing_error:
        KeychainSecretStore(backend=MissingBackend(), platform_name="Darwin").get("known-ref")
    assert missing_error.value.code == "missing"


class FailingOperationSecretStore(MemorySecretStore):
    def __init__(self, fail_put=False, fail_delete=False):
        super().__init__()
        self.fail_put = fail_put
        self.fail_delete = fail_delete

    def put(self, ref, value):
        if self.fail_put:
            raise SecretStoreError("locked", "秘密存储被锁定")
        return super().put(ref, value)

    def delete(self, ref):
        if self.fail_delete:
            raise SecretStoreError("error", "秘密清理失败")
        return super().delete(ref)


def test_keychain_write_and_cleanup_rejection_leave_journaled_failure(tmp_path):
    secrets = FailingOperationSecretStore(fail_put=True, fail_delete=True)
    store, client = _client(tmp_path, secrets)
    response = client.post("/api/ai/models", json=_payload())
    assert response.status_code == 422
    with store.connect(False) as connection:
        operations = store._records(connection, SECRET_OPERATION_KIND)
        configs = store._current(connection, "ai_model_config")
    assert operations[0]["phase"] == "cleanup_pending"
    assert operations[0]["error_code"] == "error"
    assert configs[0]["secret_status"] == "error"
    assert configs[0]["enabled"] is False


def test_delete_removes_config_before_cleanup_and_records_failure(tmp_path):
    secrets = FailingOperationSecretStore()
    store, client = _client(tmp_path, secrets)
    created = client.post("/api/ai/models", json=_payload()).json()
    secrets.fail_delete = True
    response = client.request("DELETE", f"/api/ai/models/{created['id']}", json={"confirm": True})
    assert response.status_code == 422
    with store.connect(False) as connection:
        assert not store._current(connection, "ai_model_config")
        operation = store._records(connection, SECRET_OPERATION_KIND)[0]
    assert operation["phase"] == "cleanup_pending"


def test_missing_secret_after_restore_is_reported_only_after_explicit_check(tmp_path):
    secrets = MemorySecretStore()
    store, client = _client(tmp_path, secrets)
    created = client.post("/api/ai/models", json=_payload()).json()
    with store.connect() as connection:
        config = store._get(connection, created["id"], "ai_model_config")
        config["api_key_ref"] = "restored-but-missing"
        connection.execute(
            "UPDATE current SET body=? WHERE id=?",
            (json.dumps(config, ensure_ascii=False, sort_keys=True), created["id"]),
        )

    restarted = Store(store.data_dir, TestProvider(), secrets)
    client = TestClient(create_app(restarted), headers=HEADERS)
    listed = client.get("/api/ai/models").json()["configs"][0]
    assert listed["configured_ref"] is True
    assert listed["secret_status"] == "missing"
    checked = client.post(f"/api/ai/models/{created['id']}/test")
    assert checked.status_code == 200
    assert checked.json()["code"] == "secret_missing"
    listed = client.get("/api/ai/models").json()["configs"][0]
    assert listed["secret_status"] == "missing"


def test_settings_list_does_not_probe_or_prompt_for_each_secret(tmp_path):
    secrets = MemorySecretStore()
    store, client = _client(tmp_path, secrets)
    client.post("/api/ai/models", json=_payload())

    class PromptingStore(MemorySecretStore):
        def get(self, ref):
            raise AssertionError("settings list must not probe the Keychain")

    store.secret_store = PromptingStore()
    response = client.get("/api/ai/models")
    assert response.status_code == 200
    assert response.json()["configs"][0]["secret_status"] == "ready"


def test_secret_and_journal_are_absent_from_database_dto_and_backup(tmp_path):
    secrets = MemorySecretStore()
    store, client = _client(tmp_path, secrets)
    created = client.post("/api/ai/models", json=_payload()).json()
    bundle = backup(store.data_dir, tmp_path / "backups", "fake-key-safe")

    assert "fake-key-1" not in store.db.read_bytes().decode("utf-8", "ignore")
    assert "fake-key-1" not in json.dumps(created)
    with store.connect(False) as connection:
        operations = store._records(connection, SECRET_OPERATION_KIND)
    assert operations
    assert all("fake-key-1" not in json.dumps(item) for item in operations)
    assert all("fake-key-1" not in path.read_bytes().decode("utf-8", "ignore") for path in bundle.rglob("*") if path.is_file())


def test_cas_competition_does_not_write_a_second_secret(tmp_path):
    secrets = TracedMemorySecretStore()
    store, client = _client(tmp_path, secrets)
    created = client.post("/api/ai/models", json=_payload()).json()
    first = client.put(
        f"/api/ai/models/{created['id']}",
        json={**_payload(api_key="fake-key-2"), "expected_revision": created["revision"]},
    )
    second = client.put(
        f"/api/ai/models/{created['id']}",
        json={**_payload(api_key="fake-key-3"), "expected_revision": created["revision"]},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 409
    assert [event[0] for event in secrets.events].count("put") == 2
    assert "fake-key-3" not in secrets.values.values()


class CommitFailStore(Store):
    def __init__(self, *args, **kwargs):
        self.fail_next_switch_commit = False
        self.old_ref = None
        super().__init__(*args, **kwargs)

    @contextmanager
    def connect(self, write=True):
        connection = sqlite3.connect(str(self.db), timeout=15)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield connection
            if self.fail_next_switch_commit:
                rows = connection.execute("SELECT body FROM current WHERE kind='ai_model_config'").fetchall()
                if any(
                    json.loads(body).get("api_key_ref") != self.old_ref
                    and json.loads(body).get("secret_status") == "ready"
                    for (body,) in rows
                ):
                    self.fail_next_switch_commit = False
                    raise sqlite3.OperationalError("synthetic commit failure")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class CommitFailSecretStore(TracedMemorySecretStore):
    def put(self, ref, value):
        result = super().put(ref, value)
        if self.store is not None and value == "fake-key-2":
            self.store.fail_next_switch_commit = True
        return result


def test_db_switch_commit_failure_cleans_new_ref_and_keeps_old_ref_usable(tmp_path):
    secrets = CommitFailSecretStore()
    store = CommitFailStore(tmp_path / "data", TestProvider(), secrets)
    client = TestClient(create_app(store), headers=HEADERS)
    secrets.store = store
    created = client.post("/api/ai/models", json=_payload()).json()
    with store.connect(False) as connection:
        old_ref = store._get(connection, created["id"], "ai_model_config")["api_key_ref"]
    store.old_ref = old_ref
    response = client.put(
        f"/api/ai/models/{created['id']}",
        json={**_payload(api_key="fake-key-2"), "expected_revision": created["revision"]},
    )

    assert response.status_code != 200
    assert secrets.get(old_ref) == "fake-key-1"
    assert set(secrets.values.values()) == {"fake-key-1"}
    with store.connect(False) as connection:
        operation = store._records(connection, SECRET_OPERATION_KIND)[0]
    assert "fake-key-2" not in json.dumps(operation)


def test_restart_recovery_only_deletes_journal_known_orphan_ref(tmp_path):
    secrets = MemorySecretStore()
    store, client = _client(tmp_path, secrets)
    created = client.post("/api/ai/models", json=_payload()).json()
    with store.connect(False) as connection:
        old_ref = store._get(connection, created["id"], "ai_model_config")["api_key_ref"]
    orphan_ref = secrets.allocate_ref()
    secrets.put(orphan_ref, "fake-key-orphan")
    unknown_ref = secrets.allocate_ref()
    secrets.put(unknown_ref, "fake-key-unknown")
    operation = {
        "id": "ai-secret-operation:interrupted",
        "operation_id": "interrupted",
        "config_id": created["id"],
        "expected_revision": created["revision"],
        "old_ref": old_ref,
        "new_ref": orphan_ref,
        "phase": "secret_written",
        "created_at": "2026-09-19T00:00:00+00:00",
        "updated_at": "2026-09-19T00:00:00+00:00",
        "error_code": None,
    }
    with store.connect() as connection:
        store._record(connection, SECRET_OPERATION_KIND, operation)

    Store(store.data_dir, TestProvider(), secrets)

    assert old_ref in secrets.values
    assert orphan_ref not in secrets.values
    assert unknown_ref in secrets.values


def test_restart_recovery_removes_only_interrupted_create_row(tmp_path):
    secrets = MemorySecretStore()
    store, client = _client(tmp_path, secrets)
    config_id = "model-config:interrupted-create"
    orphan_ref = secrets.allocate_ref()
    secrets.put(orphan_ref, "fake-key-orphan")
    operation = {
        "id": "ai-secret-operation:interrupted-create",
        "operation_id": "interrupted-create",
        "config_id": config_id,
        "expected_revision": 0,
        "old_ref": None,
        "new_ref": orphan_ref,
        "phase": "secret_written",
        "created_at": "2026-09-19T00:00:00+00:00",
        "updated_at": "2026-09-19T00:00:00+00:00",
        "error_code": None,
    }
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO current VALUES(?,?,?,?)",
            (config_id, "ai_model_config", 0, json.dumps({"id": config_id, "api_key_ref": None})),
        )
        store._record(connection, SECRET_OPERATION_KIND, operation)

    Store(store.data_dir, TestProvider(), secrets)

    assert orphan_ref not in secrets.values
    with store.connect(False) as connection:
        assert not connection.execute("SELECT 1 FROM current WHERE id=?", (config_id,)).fetchone()
