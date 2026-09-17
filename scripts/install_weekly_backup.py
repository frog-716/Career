#!/usr/bin/env python3
"""安装、卸载和检查 Career 的 macOS 每周备份任务。"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import subprocess


LABEL = "local.career.weekly-backup"


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def plist_payload() -> dict:
    root = project_root()
    runtime = root / ".career-runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LABEL,
        "ProgramArguments": [str(root / ".venv" / "bin" / "python"), str(root / "scripts" / "weekly_backup.py")],
        "WorkingDirectory": str(root),
        "StartCalendarInterval": {"Weekday": 1, "Hour": 0, "Minute": 0},
        "StandardOutPath": str(runtime / "weekly-backup.log"),
        "StandardErrorPath": str(runtime / "weekly-backup.log"),
        "ProcessType": "Background",
        "LowPriorityIO": True,
    }


def _target() -> str:
    return f"gui/{os.getuid()}"


def _bootout() -> None:
    subprocess.run(["/bin/launchctl", "bootout", _target(), LABEL], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def install() -> Path:
    path = plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _bootout()
    path.write_bytes(plistlib.dumps(plist_payload()))
    subprocess.run(["/bin/launchctl", "bootstrap", _target(), str(path)], check=True)
    return path


def uninstall() -> None:
    _bootout()
    plist_path().unlink(missing_ok=True)


def status() -> int:
    result = subprocess.run(["/bin/launchctl", "print", f"{_target()}/{LABEL}"], check=False, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"已加载：{LABEL}")
        return 0
    print(f"未加载：{LABEL}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "uninstall", "status"))
    args = parser.parse_args()
    if args.action == "install":
        print(f"已安装：{install()}")
        return status()
    if args.action == "uninstall":
        uninstall()
        print("已卸载每周备份任务")
        return 0
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
