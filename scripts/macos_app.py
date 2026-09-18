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
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


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


def _url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _open_in_chrome(url: str) -> None:
    subprocess.Popen(
        ["/usr/bin/open", "-b", CHROME_BUNDLE_ID, url],
        start_new_session=True,
    )


def healthy(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(f"{_url(host, port)}/api/state", timeout=1) as response:
            payload = json.load(response)
        return bool(payload.get("diagnostics", {}).get("app_version"))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def _read_pid(project_root: Path | None = None) -> int | None:
    try:
        pid = int(_pid_path(project_root).read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        _pid_path(project_root).unlink(missing_ok=True)
        return None


def start(project_root: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = True) -> int:
    base_url = _url(host, port)
    if healthy(host, port):
        print(f"Career 已运行：{base_url}")
        if open_browser:
            _open_in_chrome(f"{base_url}{HOME_PATH}")
        return 0

    python = project_root / ".venv" / "bin" / "python"
    run_script = project_root / "scripts" / "run.py"
    if not python.exists():
        raise SystemExit(f"找不到项目虚拟环境：{python}\n请先在项目根目录创建 .venv。")
    if not run_script.exists():
        raise SystemExit(f"找不到启动脚本：{run_script}")

    old_pid = _read_pid(project_root)
    if old_pid is not None:
        try:
            os.kill(old_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        _pid_path(project_root).unlink(missing_ok=True)

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
    _pid_path(project_root).write_text(str(process.pid), encoding="utf-8")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if healthy(host, port):
            print(f"Career 已启动：{base_url}")
            if open_browser:
                _open_in_chrome(f"{base_url}{HOME_PATH}")
            return 0
        if process.poll() is not None:
            raise SystemExit(f"Career 启动失败，请查看日志：{_log_path(project_root)}")
        time.sleep(0.25)
    raise SystemExit(f"Career 启动超时，请查看日志：{_log_path(project_root)}")


def stop(project_root: Path) -> int:
    pid = _read_pid(project_root)
    if pid is None:
        print("Career 当前没有由 macOS App 管理的运行进程。")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    _pid_path(project_root).unlink(missing_ok=True)
    print(f"Career 已停止（PID {pid}）。")
    return 0


def status(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    if healthy(host, port):
        print(f"运行中：{_url(host, port)}")
        return 0
    print(f"未运行：{_url(host, port)}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Career macOS 本地服务控制")
    parser.add_argument("action", choices=("start", "stop", "status"))
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.action == "start":
        return start(args.project_root.resolve(), args.host, args.port, not args.no_browser)
    if args.action == "stop":
        return stop(args.project_root.resolve())
    return status(args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
