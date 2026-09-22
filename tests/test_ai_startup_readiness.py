"""AI_ENABLED startup readiness and LOCAL_ONLY non-probing contracts."""

import json

import pytest
from fastapi.testclient import TestClient

from workbench.ai_config import CLEANUP_POLICY_MANUAL
from workbench.app import create_app
from workbench.core import Store
from workbench.model_gateway import ModelGateway
from workbench.providers import TestProvider
from workbench.secret_store import MemorySecretStore, SecretStoreError


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


class StartupSecretStore(MemorySecretStore):
    def __init__(self):
        super().__init__()
        self.failure = None
        self.get_refs = []
        self.deleted_refs = []

    def get(self, ref):
        self.get_refs.append(ref)
        if self.failure:
            raise SecretStoreError(self.failure, "synthetic startup failure")
        return super().get(ref)

    def delete(self, ref):
        self.deleted_refs.append(ref)
        return super().delete(ref)


class CountingProvider(TestProvider):
    def __init__(self):
        self.call_count = 0

    def complete(self, payload):
        self.call_count += 1
        return super().complete(payload)


def config_payload(key="synthetic-startup-key"):
    return {
        "display_name": "Synthetic startup model",
        "provider": "OpenAI-compatible",
        "base_url": "https://example.test/v1",
        "model": "synthetic-model",
        "api_key": key,
        "enabled": True,
    }


def create_config(tmp_path, monkeypatch, mode="AI_ENABLED"):
    monkeypatch.setenv("CAREER_AI_MODE", mode)
    secrets = StartupSecretStore()
    store = Store(tmp_path / "data", TestProvider(), secrets)
    client = TestClient(create_app(store), headers=HEADERS)
    created = client.post("/api/ai/models", json=config_payload()).json()
    with store.connect(False) as connection:
        config = store._get(connection, created["id"], "ai_model_config")
    return store, client, secrets, created, config


def list_config(store):
    client = TestClient(create_app(store), headers=HEADERS)
    return client.get("/api/ai/models").json()["configs"][0]


def test_local_only_restart_does_not_probe_keychain(tmp_path, monkeypatch):
    store, _, secrets, created, _ = create_config(tmp_path, monkeypatch, "LOCAL_ONLY")
    secrets.get_refs.clear()

    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    restarted = Store(store.data_dir, TestProvider(), secrets)

    listed = list_config(restarted)
    assert secrets.get_refs == []
    assert listed["configured_ref"] is True
    assert listed["secret_status"] == "not_checked"
    assert created["id"] == listed["id"]


@pytest.mark.parametrize(
    "failure",
    ["timeout", "missing", "denied", "locked", "interaction_not_allowed", "error"],
)
def test_ai_enabled_startup_failure_is_runtime_status_and_fail_closed(
    tmp_path, monkeypatch, failure
):
    store, _, secrets, _, config = create_config(tmp_path, monkeypatch)
    secrets.get_refs.clear()
    secrets.failure = failure

    provider = CountingProvider()
    restarted = Store(store.data_dir, provider, secrets)
    listed = list_config(restarted)

    assert secrets.get_refs == [config["api_key_ref"]]
    assert listed["configured_ref"] is True
    assert listed["secret_status"] == failure

    job = restarted.save_job({
        "company": "启动验收虚构公司",
        "title": "启动验收虚构岗位",
        "jd": "只用于 readiness fail-closed 测试",
        "idempotency_key": "startup-readiness-" + failure,
    })
    restarted.save_profile("启动 readiness 虚构候选人资料", 0)
    client = TestClient(create_app(restarted), headers=HEADERS)
    response = client.post("/api/analysis", json={
        "job_id": job["id"],
        "kind": "job",
        "idempotency_key": "startup-readiness-call-" + failure,
    })
    assert response.status_code == 503
    assert response.json()["code"] == "secret_" + failure
    assert secrets.get_refs == [config["api_key_ref"]]
    assert provider.call_count == 0


def test_ai_enabled_startup_reads_only_active_ref_and_never_held_ref(tmp_path, monkeypatch):
    store, client, secrets, created, original = create_config(tmp_path, monkeypatch)
    held = client.post(
        f"/api/ai/models/{created['id']}/secret-cleanup-hold",
        json={"expected_revision": created["revision"]},
    )
    assert held.status_code == 200, held.text
    updated = client.put(
        f"/api/ai/models/{created['id']}",
        json={
            **config_payload("synthetic-active-key"),
            "expected_revision": held.json()["revision"],
        },
    )
    assert updated.status_code == 200, updated.text
    with store.connect(False) as connection:
        current = store._get(connection, created["id"], "ai_model_config")
    active_ref = current["api_key_ref"]
    assert original["api_key_ref"] != active_ref
    assert current["secret_cleanup_state"] == CLEANUP_POLICY_MANUAL
    assert original["api_key_ref"] in secrets.values

    secrets.get_refs.clear()
    secrets.deleted_refs.clear()
    restarted = Store(store.data_dir, TestProvider(), secrets)

    assert secrets.get_refs == [active_ref]
    assert original["api_key_ref"] not in secrets.get_refs
    assert original["api_key_ref"] not in secrets.deleted_refs
    assert original["api_key_ref"] in secrets.values
    assert list_config(restarted)["secret_status"] == "ready"


def test_restart_does_not_inherit_persisted_ready_without_verification(tmp_path, monkeypatch):
    store, _, secrets, _, config = create_config(tmp_path, monkeypatch)
    with store.connect(False) as connection:
        persisted = store._get(connection, config["id"], "ai_model_config")
    assert persisted["secret_status"] == "ready"

    secrets.failure = "timeout"
    secrets.get_refs.clear()
    restarted = Store(store.data_dir, TestProvider(), secrets)

    assert secrets.get_refs == [config["api_key_ref"]]
    assert list_config(restarted)["secret_status"] == "timeout"
    with restarted.connect(False) as connection:
        assert restarted._get(connection, config["id"], "ai_model_config")["secret_status"] == "ready"


def test_ready_startup_has_no_provider_call_until_explicit_gateway_operation(
    tmp_path, monkeypatch
):
    store, _, secrets, _, config = create_config(tmp_path, monkeypatch)
    secrets.get_refs.clear()
    calls = []

    restarted = Store(store.data_dir, TestProvider(), secrets)
    assert secrets.get_refs == [config["api_key_ref"]]
    assert calls == []

    def fake_complete(adapter, packet, output_schema):
        calls.append((adapter.model, packet["task_type"]))
        return {"synthetic": True}

    monkeypatch.setattr(
        "workbench.model_gateway.OpenAICompatibleAdapter.complete", fake_complete
    )
    result, diagnostics = ModelGateway(restarted).generate(
        "legacy_analysis",
        {
            "task_type": "legacy_analysis",
            "sources": [{
                "id": "synthetic-target-jd",
                "revision": 1,
                "purpose": "target_jd",
                "selected_content": {"jd": "synthetic only"},
            }],
        },
        {"version": 1},
    )

    assert result == {"synthetic": True}
    assert diagnostics["model_config_id"] == config["id"]
    assert calls == [("synthetic-model", "legacy_analysis")]
    assert secrets.get_refs == [
        config["api_key_ref"], config["api_key_ref"], config["api_key_ref"]
    ]


def test_local_only_maintenance_can_report_ready_without_startup_probe(tmp_path, monkeypatch):
    store, client, secrets, created, _ = create_config(tmp_path, monkeypatch, "LOCAL_ONLY")
    assert created["configured_ref"] is True
    assert created["secret_status"] == "ready"
    secrets.get_refs.clear()

    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    restarted = Store(store.data_dir, TestProvider(), secrets)
    listed = list_config(restarted)

    assert secrets.get_refs == []
    assert listed["configured_ref"] is True
    assert listed["secret_status"] == "not_checked"
    assert "synthetic-startup-key" not in json.dumps(listed)
