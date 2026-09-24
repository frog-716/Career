import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "macos_app.py"
MODULE_SPEC = importlib.util.spec_from_file_location("career_macos_app", MODULE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
macos_app = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(macos_app)

BUILDER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "install_macos_app.py"
BUILDER_SPEC = importlib.util.spec_from_file_location("career_install_macos_app", BUILDER_PATH)
assert BUILDER_SPEC is not None and BUILDER_SPEC.loader is not None
builder = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(builder)


def test_verified_running_career_app_opens_default_page_in_chrome(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    python = tmp_path / ".venv" / "bin" / "python"
    run_script = tmp_path / "scripts" / "run.py"
    python.parent.mkdir(parents=True)
    run_script.parent.mkdir(parents=True)
    python.touch()
    run_script.touch()
    monkeypatch.setenv("CAREER_RUNTIME_DIR", str(tmp_path / "runtime"))
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    metadata = runtime / "process.json"
    metadata.write_text('{"pid": 1, "started_at": 1.0, "instance_id": "instance-a", "data_instance_id": "data-a"}', encoding="utf-8")

    monkeypatch.setattr(macos_app, "process_identity_matches", lambda *args, **kwargs: True)
    monkeypatch.setattr(macos_app, "verified_healthy", lambda *args, **kwargs: True)

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
                "http://127.0.0.1:8765/",
            ],
            {"start_new_session": True},
        )
    ]


def test_unknown_healthy_process_is_not_reused(monkeypatch, tmp_path: Path) -> None:
    python = tmp_path / ".venv" / "bin" / "python"
    run_script = tmp_path / "scripts" / "run.py"
    python.parent.mkdir(parents=True)
    run_script.parent.mkdir(parents=True)
    python.touch()
    run_script.touch()
    monkeypatch.setattr(macos_app, "healthy", lambda host, port: True)
    with pytest.raises(SystemExit, match="未验证"):
        macos_app.start(tmp_path)


def test_unknown_occupied_port_is_rejected_before_launch(monkeypatch, tmp_path: Path) -> None:
    python = tmp_path / ".venv" / "bin" / "python"
    run_script = tmp_path / "scripts" / "run.py"
    python.parent.mkdir(parents=True)
    run_script.parent.mkdir(parents=True)
    python.touch()
    run_script.touch()
    monkeypatch.setattr(macos_app, "port_is_occupied", lambda host, port: True)

    with pytest.raises(SystemExit, match="端口已有未验证"):
        macos_app.start(tmp_path, port=18770, open_browser=False)


def test_candidate_launcher_embeds_an_isolated_port(tmp_path: Path) -> None:
    source = builder.launcher_source(18770)

    assert '"start", "--project-root", root, "--port", "18770"' in source
    assert '"start", "--project-root", root, "--port", "8765"' in builder.launcher_source(8765)


def test_candidate_launcher_can_embed_explicit_local_only_mode(tmp_path: Path) -> None:
    source = builder.launcher_source(18770, "LOCAL_ONLY")

    assert 'setenv("CAREER_AI_MODE", "LOCAL_ONLY", 1);' in source
    assert "CAREER_PERSONAL_LOCAL" not in source
    with pytest.raises(ValueError):
        builder.launcher_source(18770, "UNKNOWN")


def test_launcher_finds_project_root_at_runtime_instead_of_embedding_build_path():
    source = builder.launcher_source(18770, "LOCAL_ONLY")

    assert "proc_pidpath" in source
    assert '"%s/scripts/macos_app.py"' in source
    assert '"%s/.venv/bin/python"' in source
    assert "const char *root = \"" not in source


def test_app_builder_signs_and_verifies_after_building_the_bundle(
    monkeypatch, tmp_path: Path
):
    calls = []

    def fake_icon(_project_root, resources_dir):
        resources_dir.mkdir(parents=True, exist_ok=True)

    def fake_run(command, **_kwargs):
        calls.append(command)

    monkeypatch.setattr(builder, "build_icon", fake_icon)
    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    app = builder.build(tmp_path / "output", tmp_path / "project", ai_mode="LOCAL_ONLY")

    assert app.is_dir()
    assert calls[0][0] == "/usr/bin/clang"
    assert calls[-2] == [
        "/usr/bin/codesign", "--force", "--deep", "--sign", "-",
        "--timestamp=none", str(app),
    ]
    assert calls[-1] == [
        "/usr/bin/codesign", "--verify", "--deep", "--strict", str(app),
    ]


def test_pair_command_is_not_part_of_the_launcher(monkeypatch):
    monkeypatch.setattr(macos_app.sys, "argv", ["macos_app.py", "pair"])
    with pytest.raises(SystemExit) as error:
        macos_app.main()
    assert error.value.code == 2


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
        (tmp_path / "runtime" / "process.json").write_text(
            '{"pid": 43210, "started_at": 1.0, "instance_id": "instance-a", "data_instance_id": "data-a"}',
            encoding="utf-8",
        )
        return FakeProcess()

    monkeypatch.setattr(macos_app.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(macos_app, "process_identity_matches", lambda *args, **kwargs: True)
    monkeypatch.setattr(macos_app, "verified_healthy", lambda *args, **kwargs: True)
    monkeypatch.setattr(macos_app, "port_is_occupied", lambda host, port: False)

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
            "http://127.0.0.1:8765/",
        ],
        {"start_new_session": True},
    )
    assert len(calls) == 2
