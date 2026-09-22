import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.local_session import (
    FAKE_DATA_MARKER_CONTENT,
    FAKE_DATA_MARKER_NAME,
    LocalSessionManager,
    unpaired_fake_data_enabled,
)
from workbench.providers import TestProvider


HEADERS = {"Host": "127.0.0.1", "X-Career-Request": "1"}


def secure_client(tmp_path: Path, runtime_name: str = "runtime"):
    runtime = tmp_path / runtime_name
    store = Store(tmp_path / "data", TestProvider())
    app = create_app(store, require_local_session=True, runtime_dir=runtime)
    return TestClient(app, headers=HEADERS), app


def pairing_code(app):
    path = app.state.local_session.pairing_path
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600
    return json.loads(path.read_text(encoding="utf-8"))["code"]


def pair(client, app):
    response = client.post("/api/pair", json={"code": pairing_code(app)})
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    assert len(token) >= 43
    return token


def auth_headers(token):
    return {**HEADERS, "Authorization": f"Bearer {token}"}


def mark_fake_data(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / FAKE_DATA_MARKER_NAME).write_text(FAKE_DATA_MARKER_CONTENT, encoding="utf-8")


def test_unpaired_fake_data_mode_requires_explicit_flags_marker_and_temp_path(
    monkeypatch, tmp_path
):
    data_dir = tmp_path / "fake-data"
    mark_fake_data(data_dir)
    monkeypatch.setenv("CAREER_TEST_MODE", "1")
    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    monkeypatch.setenv("CAREER_ALLOW_UNPAIRED_FAKE_DATA", "1")

    assert unpaired_fake_data_enabled(data_dir) is True

    monkeypatch.setenv("CAREER_AI_MODE", "AI_ENABLED")
    assert unpaired_fake_data_enabled(data_dir) is False
    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    monkeypatch.delenv("CAREER_ALLOW_UNPAIRED_FAKE_DATA")
    assert unpaired_fake_data_enabled(data_dir) is False
    monkeypatch.setenv("CAREER_ALLOW_UNPAIRED_FAKE_DATA", "1")
    (data_dir / FAKE_DATA_MARKER_NAME).unlink()
    assert unpaired_fake_data_enabled(data_dir) is False


def test_runtime_fake_data_mode_skips_pairing_but_unmarked_data_does_not(
    monkeypatch, tmp_path
):
    data_dir = tmp_path / "fake-data"
    mark_fake_data(data_dir)
    monkeypatch.setenv("CAREER_TEST_MODE", "1")
    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    monkeypatch.setenv("CAREER_ALLOW_UNPAIRED_FAKE_DATA", "1")

    store = Store(data_dir, TestProvider())
    client = TestClient(
        create_app(
            store,
            require_local_session=not unpaired_fake_data_enabled(store.data_dir),
            runtime_dir=tmp_path / "runtime",
        ),
        headers=HEADERS,
    )
    assert client.get("/api/state").status_code == 200

    monkeypatch.delenv("CAREER_ALLOW_UNPAIRED_FAKE_DATA")
    protected = TestClient(
        create_app(
            store,
            require_local_session=not unpaired_fake_data_enabled(store.data_dir),
            runtime_dir=tmp_path / "runtime-protected",
        ),
        headers=HEADERS,
    )
    assert protected.get("/api/state").status_code == 401


def test_unpaired_business_and_artifact_requests_are_denied_but_health_is_minimal(tmp_path):
    client, app = secure_client(tmp_path)

    assert client.get("/healthz").json() == {"status": "ok", "build_id": app.state.local_session.build_id}
    assert client.get("/api/state").status_code == 401
    assert client.get("/api/artifacts/not-a-real-id").status_code == 401
    assert client.get("/docs").status_code == 404
    assert "data_dir" not in client.get("/healthz").text
    assert pairing_code(app) not in client.get("/healthz").text


def test_pairing_is_one_time_and_session_is_required_for_business_api(tmp_path):
    client, app = secure_client(tmp_path)
    code = pairing_code(app)

    first = client.post("/api/pair", json={"code": code})
    assert first.status_code == 200
    token = first.json()["token"]
    resume_token = first.json()["resume_token"]
    assert first.json()["expires_in"] == 8 * 60 * 60
    assert client.get("/api/state", headers=auth_headers(token)).status_code == 200

    replay = client.post("/api/pair", json={"code": code})
    assert replay.status_code == 401
    assert client.get("/api/state", headers=auth_headers(token)).status_code == 200

    logged_out = client.post("/api/logout", headers=auth_headers(token), json={})
    assert logged_out.status_code == 200
    assert client.get("/api/state", headers=auth_headers(token)).status_code == 401
    assert client.post(
        "/api/session/resume",
        json={"resume_token": resume_token},
    ).status_code == 401


def test_browser_session_can_resume_after_runtime_restart_without_reusing_pairing_code(tmp_path):
    client, app = secure_client(tmp_path)
    first = client.post("/api/pair", json={"code": pairing_code(app)})
    assert first.status_code == 200
    resume_token = first.json()["resume_token"]

    restarted_store = Store(tmp_path / "data", TestProvider())
    restarted_app = create_app(
        restarted_store,
        require_local_session=True,
        runtime_dir=tmp_path / "runtime",
    )
    restarted = TestClient(restarted_app, headers=HEADERS)
    resumed = restarted.post(
        "/api/session/resume",
        json={"resume_token": resume_token},
    )

    assert resumed.status_code == 200
    assert resumed.json()["token"] != first.json()["token"]
    assert restarted.get("/api/state", headers=auth_headers(resumed.json()["token"])).status_code == 200

    other_client, _ = secure_client(tmp_path, "runtime-b")
    assert other_client.post(
        "/api/session/resume",
        json={"resume_token": resume_token},
    ).status_code == 401


def test_origin_host_and_missing_bearer_are_rejected_without_data_leak(tmp_path):
    client, app = secure_client(tmp_path)
    token = pair(client, app)

    assert client.get("/api/state", headers={**auth_headers(token), "Origin": "https://attacker.example"}).status_code == 403
    assert client.get("/api/state", headers={**auth_headers(token), "Host": "192.0.2.44"}).status_code == 403
    assert client.get("/api/state", headers={"Host": "127.0.0.1"}).status_code == 401


def test_session_is_invalid_after_restart_and_is_not_accepted_by_another_runtime(tmp_path):
    first, first_app = secure_client(tmp_path, "runtime-a")
    token = pair(first, first_app)

    restarted = LocalSessionManager(tmp_path / "runtime-a", build_id="test-build")
    assert restarted.authenticate(token) is None

    second, _ = secure_client(tmp_path, "runtime-b")
    assert second.get("/api/state", headers=auth_headers(token)).status_code == 401


def test_authorized_health_contains_opaque_identity_but_not_path_or_secret(tmp_path):
    client, app = secure_client(tmp_path)
    code = pairing_code(app)
    token = pair(client, app)
    response = client.get("/api/local/healthz", headers=auth_headers(token))

    assert response.status_code == 200
    payload = response.json()
    assert {
        "build_id",
        "schema_version",
        "data_instance_id",
        "startup_instance_id",
        "static_resource_build_id",
    } <= payload.keys()
    assert str(app.state.store.data_dir) not in response.text
    assert code not in response.text


def test_expired_session_and_pairing_fail_without_refreshing_automatically(tmp_path):
    now = [1000.0]
    manager = LocalSessionManager(tmp_path / "runtime", clock=lambda: now[0], pairing_ttl=300, session_ttl=10)
    code = json.loads(manager.pairing_path.read_text(encoding="utf-8"))["code"]
    token = manager.pair(code)["token"]
    now[0] += 11
    assert manager.authenticate(token) is None

    manager2 = LocalSessionManager(tmp_path / "runtime-2", clock=lambda: now[0], pairing_ttl=300, session_ttl=10)
    code2 = json.loads(manager2.pairing_path.read_text(encoding="utf-8"))["code"]
    now[0] += 301
    assert manager2.pair(code2) is None


def test_verified_process_identity_is_required_before_stop(tmp_path):
    module_path = Path(__file__).parents[1] / "scripts" / "macos_app.py"
    spec = importlib.util.spec_from_file_location("career_macos_app_t09", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    metadata = tmp_path / "runtime.json"
    metadata.write_text(json.dumps({"pid": os.getpid() + 100000, "started_at": 1.0, "instance_id": "instance-a"}), encoding="utf-8")
    assert module.process_identity_matches(metadata, pid=os.getpid(), started_at=1.0, instance_id="instance-a") is False


def test_os_single_instance_lock_rejects_second_launcher(tmp_path):
    module_path = Path(__file__).parents[1] / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("career_run_t09", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    first = module.acquire_runtime_lock(tmp_path / "runtime")
    try:
        with pytest.raises(RuntimeError):
            module.acquire_runtime_lock(tmp_path / "runtime")
    finally:
        first.close()
