import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "macos_app.py"
MODULE_SPEC = importlib.util.spec_from_file_location("career_macos_app", MODULE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
macos_app = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(macos_app)


def test_running_career_app_opens_home_in_chrome(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    monkeypatch.setattr(macos_app, "healthy", lambda host, port: True)

    def fake_popen(command: list[str], **kwargs: object) -> object:
        calls.append((command, kwargs))
        return object()

    monkeypatch.setattr(macos_app.subprocess, "Popen", fake_popen)

    assert macos_app.start(tmp_path) == 0
    assert calls == [
        (
            [
                "/usr/bin/open",
                "-b",
                "com.google.Chrome",
                "http://127.0.0.1:8765/#home",
            ],
            {"start_new_session": True},
        )
    ]


def test_cold_start_opens_chrome_only_after_service_is_healthy(
    monkeypatch, tmp_path: Path
) -> None:
    python = tmp_path / ".venv" / "bin" / "python"
    run_script = tmp_path / "scripts" / "run.py"
    python.parent.mkdir(parents=True)
    run_script.parent.mkdir(parents=True)
    python.touch()
    run_script.touch()

    health_results = iter((False, True))
    monkeypatch.setattr(
        macos_app, "healthy", lambda host, port: next(health_results)
    )
    monkeypatch.setenv("CAREER_RUNTIME_DIR", str(tmp_path / "runtime"))
    calls: list[tuple[list[str], dict[str, object]]] = []

    class FakeProcess:
        pid = 43210

        @staticmethod
        def poll() -> None:
            return None

    def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
        calls.append((command, kwargs))
        return FakeProcess()

    monkeypatch.setattr(macos_app.subprocess, "Popen", fake_popen)

    assert macos_app.start(tmp_path) == 0
    assert calls[0][0] == [
        str(python),
        str(run_script),
        "--port",
        "8765",
        "--no-browser",
    ]
    assert calls[1] == (
        [
            "/usr/bin/open",
            "-b",
            "com.google.Chrome",
            "http://127.0.0.1:8765/#home",
        ],
        {"start_new_session": True},
    )
    assert len(calls) == 2
