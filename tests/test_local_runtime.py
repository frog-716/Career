import json
from pathlib import Path

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
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
    client = TestClient(app, headers=HEADERS)

    for path, body in (
        ("/api/pair", {"code": "fictional"}),
        ("/api/session/resume", {"resume_token": "fictional"}),
        ("/api/logout", {}),
    ):
        response = client.post(path, json=body)
        assert response.status_code == 404, (path, response.text)


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
