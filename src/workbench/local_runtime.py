"""Identity and private control channel for one local Career runtime."""
from __future__ import annotations

import hmac
import json
import os
import secrets
import subprocess
import stat
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


DEFAULT_BUILD_ID = "career-0.7.0-batch-f"
RETIRED_BROWSER_AUTH_FILES = ("pairing.json", "browser-session.json")


def _write_private(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temporary = path.with_name(path.name + ".tmp-" + secrets.token_hex(8))
    temporary.write_text(payload, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def process_started_at(pid: int) -> Optional[float]:
    """Return the OS-reported process start time when the platform exposes it."""
    try:
        output = subprocess.check_output(
            ["/bin/ps", "-p", str(pid), "-o", "lstart="],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if not output:
            return None
        return datetime.strptime(output, "%a %b %d %H:%M:%S %Y").timestamp()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def write_process_metadata(
    path: Path,
    *,
    pid: int,
    started_at: float,
    instance_id: str,
    data_instance_id: Optional[str] = None,
) -> None:
    _write_private(
        path,
        json.dumps(
            {
                "pid": pid,
                "started_at": started_at,
                "instance_id": instance_id,
                "data_instance_id": data_instance_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )


def process_identity_matches(
    path: Path, *, pid: int, started_at: float, instance_id: str
) -> bool:
    """Require PID, start time and this runtime's opaque instance ID to agree."""
    try:
        stored = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            type(stored.get("pid")) is not int
            or stored.get("pid") != pid
            or stored.get("instance_id") != instance_id
            or abs(float(stored.get("started_at")) - float(started_at)) > 1.0
        ):
            return False
        os.kill(pid, 0)
        actual = process_started_at(pid)
        return actual is not None and abs(actual - float(started_at)) <= 2.0
    except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


class LocalRuntimeManager:
    """Keep runtime identity and the launcher-only control credential."""

    def __init__(
        self,
        runtime_dir: Path,
        *,
        data_dir: Optional[Path] = None,
        build_id: str = DEFAULT_BUILD_ID,
        schema_version: int = 6,
    ) -> None:
        self.runtime_dir = Path(runtime_dir).expanduser().resolve()
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.runtime_dir.chmod(0o700)
        self.data_dir = Path(data_dir).expanduser().resolve() if data_dir else None
        self.build_id = build_id
        self.static_resource_build_id = build_id
        self.schema_version = schema_version
        self.startup_instance_id = secrets.token_hex(16)
        self.control_path = self.runtime_dir / "control.json"
        self.process_metadata_path = self.runtime_dir / "process.json"
        self._control_token = secrets.token_urlsafe(32)
        self.data_instance_id = self._load_data_instance_id()
        self._remove_retired_browser_auth_files()
        _write_private(
            self.control_path,
            json.dumps({"token": self._control_token}, ensure_ascii=False),
        )

    def _load_data_instance_id(self) -> str:
        path = (self.data_dir or self.runtime_dir) / ".career-instance"
        try:
            value = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            value = ""
        if len(value) != 32 or any(ch not in "0123456789abcdef" for ch in value):
            value = secrets.token_hex(16)
            _write_private(path, value + "\n")
        return value

    def _remove_retired_browser_auth_files(self) -> None:
        # These exact runtime files were used by retired browser authentication.
        # Never read their contents; remove only the obsolete files in this runtime.
        for name in RETIRED_BROWSER_AUTH_FILES:
            (self.runtime_dir / name).unlink(missing_ok=True)

    def authorize_control(self, token: Optional[str]) -> bool:
        return isinstance(token, str) and hmac.compare_digest(token, self._control_token)

    def diagnostics(self) -> Dict[str, object]:
        return {
            "build_id": self.build_id,
            "schema_version": self.schema_version,
            "data_instance_id": self.data_instance_id,
            "startup_instance_id": self.startup_instance_id,
            "static_resource_build_id": self.static_resource_build_id,
        }
