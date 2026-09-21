#!/usr/bin/env python3
"""Career macOS 本地运行时。

这个模块只负责本地服务的生命周期，不参与 Career 业务逻辑：
start 复用或启动服务，stop 停止由本模块启动的服务，status 检查健康状态。
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from workbench.local_session import DEFAULT_BUILD_ID, process_identity_matches as _process_identity_matches
from workbench.runtime_mode import RuntimeModeError, startup_mode


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
HOME_PATH = "/"
CHROME_BUNDLE_ID = "com.google.Chrome"


def _runtime_dir(project_root: Path | None = None) -> Path:
    configured = os.environ.get("CAREER_RUNTIME_DIR")
    path = Path(configured).expanduser() if configured else ((project_root or Path(__file__).resolve().parents[1]) / ".career-runtime")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _pid_path(project_root: Path | None = None) -> Path:
    return _runtime_dir(project_root) / "career.pid"


def _log_path(project_root: Path | None = None) -> Path:
    return _runtime_dir(project_root) / "career.log"


def _process_path(project_root: Path | None = None) -> Path:
    return _runtime_dir(project_root) / "process.json"


def _control_path(project_root: Path | None = None) -> Path:
    return _runtime_dir(project_root) / "control.json"


def _url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _open_in_chrome(url: str) -> None:
    subprocess.Popen(
        ["/usr/bin/open", "-b", CHROME_BUNDLE_ID, url],
        start_new_session=True,
    )


def healthy(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(f"{_url(host, port)}/healthz", timeout=1) as response:
            payload = json.load(response)
        return payload.get("status") == "ok" and bool(payload.get("build_id"))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def port_is_occupied(host: str, port: int) -> bool:
    """Detect a listener before spawning a process that could fail to bind."""
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _read_pid(project_root: Path | None = None) -> int | None:
    try:
        pid = int(_pid_path(project_root).read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        _pid_path(project_root).unlink(missing_ok=True)
        return None


def process_identity_matches(metadata_path: Path, *, pid: int, started_at: float, instance_id: str) -> bool:
    return _process_identity_matches(metadata_path, pid=pid, started_at=started_at, instance_id=instance_id)


def verified_healthy(host: str, port: int, metadata: dict, project_root: Path | None = None) -> bool:
    try:
        control = json.loads(_control_path(project_root).read_text(encoding="utf-8"))["token"]
        request = urllib.request.Request(
            f"{_url(host, port)}/api/local/healthz",
            headers={"X-Career-Control": control},
        )
        with urllib.request.urlopen(request, timeout=1) as response:
            payload = json.load(response)
        expected_build = os.environ.get("CAREER_BUILD_ID", DEFAULT_BUILD_ID)
        return (
            payload.get("build_id") == expected_build
            and payload.get("static_resource_build_id") == expected_build
            and payload.get("startup_instance_id") == metadata.get("instance_id")
            and (
                metadata.get("data_instance_id") is None
                or payload.get("data_instance_id") == metadata.get("data_instance_id")
            )
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, urllib.error.URLError):
        return False


def start(project_root: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = True) -> int:
    try:
        startup_mode()
    except RuntimeModeError as exc:
        raise SystemExit(str(exc))
    base_url = _url(host, port)
    python = project_root / ".venv" / "bin" / "python"
    run_script = project_root / "scripts" / "run.py"
    if not python.exists():
        raise SystemExit(f"找不到项目虚拟环境：{python}\n请先在项目根目录创建 .venv。")
    if not run_script.exists():
        raise SystemExit(f"找不到启动脚本：{run_script}")

    metadata_path = _process_path(project_root)
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if process_identity_matches(
                metadata_path,
                pid=metadata["pid"],
                started_at=metadata["started_at"],
                instance_id=metadata["instance_id"],
            ):
                if verified_healthy(host, port, metadata, project_root):
                    print(f"Career 已运行：{base_url}")
                    if open_browser:
                        _open_in_chrome(f"{base_url}{HOME_PATH}")
                    return 0
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and not verified_healthy(host, port, metadata, project_root):
                    time.sleep(0.25)
                if verified_healthy(host, port, metadata, project_root):
                    if open_browser:
                        _open_in_chrome(f"{base_url}{HOME_PATH}")
                    return 0
                raise SystemExit("Career 已有可验证实例但尚未就绪；未终止该进程")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
    if healthy(host, port):
        raise SystemExit("端口已有未验证的 Career 服务；未复用或终止未知进程")
    if port_is_occupied(host, port):
        raise SystemExit("端口已有未验证的服务；未复用或终止未知进程")

    log = _log_path(project_root).open("a", encoding="utf-8")
    process = subprocess.Popen(
        [str(python), str(run_script), "--port", str(port), "--no-browser"],
        cwd=project_root,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if healthy(host, port):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                metadata = {}
            if metadata and process_identity_matches(
                metadata_path,
                pid=metadata.get("pid"),
                started_at=metadata.get("started_at"),
                instance_id=metadata.get("instance_id"),
            ) and verified_healthy(host, port, metadata, project_root):
                print(f"Career 已启动：{base_url}")
                if open_browser:
                    _open_in_chrome(f"{base_url}{HOME_PATH}")
                return 0
        if process.poll() is not None:
            raise SystemExit(f"Career 启动失败，请查看日志：{_log_path(project_root)}")
        time.sleep(0.25)
    raise SystemExit(f"Career 启动超时，请查看日志：{_log_path(project_root)}")


def stop(project_root: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    metadata_path = _process_path(project_root)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        pid = metadata["pid"]
        started_at = metadata["started_at"]
        instance_id = metadata["instance_id"]
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        print("Career 当前没有可验证的运行实例。")
        return 0
    if not process_identity_matches(metadata_path, pid=pid, started_at=started_at, instance_id=instance_id):
        print("Career 运行身份无法核实；未终止未知进程。", file=sys.stderr)
        return 2
    try:
        control = json.loads(_control_path(project_root).read_text(encoding="utf-8"))["token"]
        request = urllib.request.Request(
            f"{_url(host, port)}/api/local/stop",
            data=b"{}",
            headers={"Content-Type": "application/json", "X-Career-Request": "1", "X-Career-Control": control},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            if response.status != 200:
                raise OSError("本实例停止请求未被接受")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError) as exc:
        print(f"Career 未能通过本实例控制通道停止：{exc}", file=sys.stderr)
        return 2
    print(f"Career 已请求优雅停止（PID {pid}）。")
    return 0


def pair(project_root: Path) -> int:
    if not sys.stdout.isatty():
        print("配对码只允许在交互式终端显示。", file=sys.stderr)
        return 2
    try:
        payload = json.loads(_runtime_dir(project_root).joinpath("pairing.json").read_text(encoding="utf-8"))
        code = payload["code"]
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        print("当前没有可用的本地配对码。", file=sys.stderr)
        return 2
    print(code)
    return 0


def status(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    if healthy(host, port):
        print(f"运行中：{_url(host, port)}")
        return 0
    print(f"未运行：{_url(host, port)}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Career macOS 本地服务控制")
    parser.add_argument("action", choices=("start", "stop", "status", "pair"))
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.action == "start":
        return start(args.project_root.resolve(), args.host, args.port, not args.no_browser)
    if args.action == "stop":
        return stop(args.project_root.resolve(), args.host, args.port)
    if args.action == "pair":
        return pair(args.project_root.resolve())
    return status(args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
