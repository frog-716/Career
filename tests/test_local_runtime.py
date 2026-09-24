import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.local_runtime import process_identity_matches
from workbench.providers import TestProvider


HEADERS = {"Host": "127.0.0.1", "X-Career-Request": "1"}


def test_business_api_is_available_without_pairing_or_bearer_by_default(
    monkeypatch, tmp_path: Path
):
    monkeypatch.delenv("CAREER_TEST_MODE", raising=False)
    runtime = tmp_path / "runtime"
    app = create_app(
        Store(tmp_path / "data", TestProvider()),
        runtime_dir=runtime,
    )
    client = TestClient(app, headers=HEADERS)

    response = client.get("/api/state")

    assert response.status_code == 200
    assert "X-Career-Local-Auth-Mode" not in response.headers
    assert not (runtime / "pairing.json").exists()
    assert not (runtime / "browser-session.json").exists()


def test_pair_resume_and_logout_routes_are_removed(tmp_path: Path):
    app = create_app(
        Store(tmp_path / "data", TestProvider()),
        runtime_dir=tmp_path / "runtime",
    )
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/pair" not in paths
    assert "/api/session/resume" not in paths
    assert "/api/logout" not in paths


def test_startup_removes_only_retired_browser_auth_files(tmp_path: Path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "pairing.json").write_text('{"code":"fictional"}', encoding="utf-8")
    (runtime / "browser-session.json").write_text(
        '{"digest":"fictional"}', encoding="utf-8"
    )
    unrelated = runtime / "preserved.marker"
    unrelated.write_text("keep", encoding="utf-8")

    app = create_app(
        Store(tmp_path / "data", TestProvider()),
        runtime_dir=runtime,
    )
    client = TestClient(app, headers=HEADERS)

    assert client.get("/healthz").status_code == 200
    assert not (runtime / "pairing.json").exists()
    assert not (runtime / "browser-session.json").exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"


def test_local_origin_guards_and_private_runtime_health_remain(tmp_path: Path):
    runtime = tmp_path / "runtime"
    app = create_app(
        Store(tmp_path / "data", TestProvider()),
        runtime_dir=runtime,
    )
    client = TestClient(app, headers=HEADERS)

    assert client.get(
        "/api/state", headers={**HEADERS, "Origin": "https://attacker.example"}
    ).status_code == 403
    assert client.get(
        "/api/state", headers={**HEADERS, "Host": "192.0.2.44"}
    ).status_code == 403
    assert client.get(
        "/api/state", headers={**HEADERS, "Sec-Fetch-Site": "cross-site"}
    ).status_code == 403
    assert client.post(
        "/api/feedback",
        json={},
        headers={**HEADERS, "X-Career-Request": ""},
    ).status_code == 403

    assert client.get("/api/local/healthz", headers=HEADERS).status_code == 403
    control = json.loads((runtime / "control.json").read_text(encoding="utf-8"))["token"]
    health = client.get(
        "/api/local/healthz",
        headers={**HEADERS, "X-Career-Control": control},
    )
    assert health.status_code == 200
    assert {"build_id", "startup_instance_id", "data_instance_id"} <= health.json().keys()


def test_cli_launcher_starts_personal_app_without_auth_switches(monkeypatch, tmp_path: Path):
    module_path = Path(__file__).parents[1] / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("career_run_without_pairing", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    monkeypatch.delenv("CAREER_TEST_MODE", raising=False)
    monkeypatch.setenv("CAREER_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("CAREER_DATA_DIR", str(tmp_path / "data"))

    class FakeLock:
        @staticmethod
        def close():
            return None

    apps = []
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(module, "acquire_runtime_lock", lambda _path: FakeLock())
    monkeypatch.setattr("uvicorn.run", lambda app, **_kwargs: apps.append(app))
    monkeypatch.setattr(module.sys, "argv", ["run.py", "--port", "18765", "--no-browser"])

    assert module.main() == 0
    app = apps[0]
    client = TestClient(app, headers=HEADERS)
    assert client.get("/api/state").status_code == 200
    assert app.state.local_runtime.process_metadata_path.parent == tmp_path / "runtime"
    assert not (tmp_path / "runtime" / "pairing.json").exists()


def test_runtime_process_identity_and_second_launcher_lock_are_preserved(tmp_path: Path):
    metadata = tmp_path / "process.json"
    metadata.write_text(
        json.dumps({"pid": -1, "started_at": 1.0, "instance_id": "instance-a"}),
        encoding="utf-8",
    )
    assert process_identity_matches(
        metadata, pid=1, started_at=1.0, instance_id="instance-a"
    ) is False

    module_path = Path(__file__).parents[1] / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("career_run_runtime_lock", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    first = module.acquire_runtime_lock(tmp_path / "lock-runtime")
    try:
        with pytest.raises(RuntimeError):
            module.acquire_runtime_lock(tmp_path / "lock-runtime")
    finally:
        first.close()
