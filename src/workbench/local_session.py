"""Local pairing, browser-session credentials, and local session resumption.

The pairing code is a one-time bootstrap credential kept in a protected local
file.  Bearer sessions live only in memory.  A separate high-entropy browser
resume secret is stored only as a digest in the protected runtime directory so
the same browser can obtain a fresh in-memory Bearer session after a Career
restart without making business APIs anonymous.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import subprocess
import stat
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional


DEFAULT_BUILD_ID = "career-0.7.0-batch-f"
PAIRING_TTL_SECONDS = 5 * 60
SESSION_TTL_SECONDS = 8 * 60 * 60
FAKE_DATA_MARKER_NAME = ".career-fake-data"
FAKE_DATA_MARKER_CONTENT = "career-fake-data-v1\n"
UNPAIRED_FAKE_DATA_ENV = "CAREER_ALLOW_UNPAIRED_FAKE_DATA"


def _write_private(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temporary = path.with_name(path.name + ".tmp-" + secrets.token_hex(8))
    temporary.write_text(payload, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def _is_temporary_path(path: Path) -> bool:
    resolved = path.resolve()
    roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()}
    configured_tmp = os.environ.get("TMPDIR")
    if configured_tmp:
        roots.add(Path(configured_tmp).expanduser().resolve())
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def unpaired_fake_data_enabled(data_dir: Optional[Path]) -> bool:
    """Allow no-pairing only for explicitly marked temporary fake data.

    This is intentionally stricter than ``CAREER_TEST_MODE`` alone.  The
    runtime launcher must opt in, and the data directory must be a regular
    marker file under a system temporary directory.  Production data and
    restored production copies therefore keep the local pairing boundary.
    """
    if os.environ.get("CAREER_TEST_MODE") != "1":
        return False
    if os.environ.get("CAREER_AI_MODE") != "LOCAL_ONLY":
        return False
    if os.environ.get(UNPAIRED_FAKE_DATA_ENV) != "1" or data_dir is None:
        return False
    resolved = Path(data_dir).expanduser().resolve()
    if not _is_temporary_path(resolved):
        return False
    marker = resolved / FAKE_DATA_MARKER_NAME
    try:
        details = marker.lstat()
        return (
            stat.S_ISREG(details.st_mode)
            and marker.read_text(encoding="utf-8") == FAKE_DATA_MARKER_CONTENT
        )
    except (FileNotFoundError, OSError, UnicodeError):
        return False


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


def process_identity_matches(path: Path, *, pid: int, started_at: float, instance_id: str) -> bool:
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


class LocalSessionManager:
    """Manage one process's pairing code and in-memory sessions."""

    def __init__(
        self,
        runtime_dir: Path,
        *,
        data_dir: Optional[Path] = None,
        build_id: str = DEFAULT_BUILD_ID,
        schema_version: int = 6,
        clock: Callable[[], float] = time.time,
        pairing_ttl: int = PAIRING_TTL_SECONDS,
        session_ttl: int = SESSION_TTL_SECONDS,
        pairing_enabled: bool = True,
        local_auth_mode: Optional[str] = None,
    ) -> None:
        self.runtime_dir = Path(runtime_dir).expanduser().resolve()
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.runtime_dir.chmod(0o700)
        self.data_dir = Path(data_dir).expanduser().resolve() if data_dir else None
        self.build_id = build_id
        self.static_resource_build_id = build_id
        self.schema_version = schema_version
        self._clock = clock
        self.pairing_ttl = pairing_ttl
        self.session_ttl = session_ttl
        self.pairing_enabled = bool(pairing_enabled)
        self.local_auth_mode = local_auth_mode or (
            "paired" if self.pairing_enabled else "personal_local"
        )
        self.startup_instance_id = secrets.token_hex(16)
        self._sessions: Dict[str, float] = {}
        self._pairing_failures = 0
        self._pairing_retry_after = 0.0
        self._pairing_consumed = False
        self.pairing_path = self.runtime_dir / "pairing.json"
        self.resume_path = self.runtime_dir / "browser-session.json"
        self.control_path = self.runtime_dir / "control.json"
        self.process_metadata_path = self.runtime_dir / "process.json"
        self._control_token = secrets.token_urlsafe(32)
        self.data_instance_id = self._load_data_instance_id()
        if self.pairing_enabled:
            self._resume_digest = self._load_resume_digest()
            self._pairing_code = secrets.token_hex(16)
            self._pairing_digest = hashlib.sha256(self._pairing_code.encode()).digest()
            self._pairing_expires_at = self._clock() + self.pairing_ttl
            _write_private(
                self.pairing_path,
                json.dumps(
                    {"code": self._pairing_code, "expires_at": self._pairing_expires_at},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        else:
            # Switching to personal-local mode revokes only the old browser
            # bootstrap/resume credentials. Never inspect or carry them back
            # into a later paired (for example, server) launch.
            self._resume_digest = None
            self._pairing_code = None
            self._pairing_digest = None
            self._pairing_expires_at = None
            self.pairing_path.unlink(missing_ok=True)
            self.resume_path.unlink(missing_ok=True)
        _write_private(
            self.control_path,
            json.dumps({"token": self._control_token}, ensure_ascii=False),
        )

    def _load_resume_digest(self) -> Optional[bytes]:
        try:
            payload = json.loads(self.resume_path.read_text(encoding="utf-8"))
            digest = payload.get("digest")
            if not isinstance(digest, str) or len(digest) != 64:
                return None
            return bytes.fromhex(digest)
        except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

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

    def pairing_status(self) -> Dict[str, object]:
        return {
            "enabled": self.pairing_enabled,
            "expires_at": self._pairing_expires_at,
            "consumed": self._pairing_consumed,
        }

    def pair(self, code: str) -> Optional[Dict[str, object]]:
        if not self.pairing_enabled or self._pairing_digest is None:
            return None
        now = self._clock()
        if now < self._pairing_retry_after:
            return None
        if self._pairing_consumed or now >= self._pairing_expires_at:
            return None
        if not isinstance(code, str) or len(code) > 256:
            self._pairing_failures += 1
            return None
        supplied = hashlib.sha256(code.encode()).digest()
        if not hmac.compare_digest(supplied, self._pairing_digest):
            self._pairing_failures += 1
            if self._pairing_failures >= 5:
                self._pairing_retry_after = now + 30
            return None
        resume_token = secrets.token_urlsafe(32)
        try:
            _write_private(
                self.resume_path,
                json.dumps(
                    {"digest": hashlib.sha256(resume_token.encode()).hexdigest()},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        except OSError:
            return None
        self._resume_digest = hashlib.sha256(resume_token.encode()).digest()
        self._pairing_consumed = True
        self.pairing_path.unlink(missing_ok=True)
        token = secrets.token_urlsafe(32)
        expires_at = now + self.session_ttl
        self._sessions[hashlib.sha256(token.encode()).hexdigest()] = expires_at
        return {
            "token": token,
            "resume_token": resume_token,
            "expires_at": expires_at,
            "expires_in": self.session_ttl,
        }

    def resume(self, resume_token: str) -> Optional[Dict[str, object]]:
        if (
            not self.pairing_enabled
            or not isinstance(resume_token, str)
            or not resume_token
            or len(resume_token) > 256
            or self._resume_digest is None
        ):
            return None
        supplied = hashlib.sha256(resume_token.encode()).digest()
        if not hmac.compare_digest(supplied, self._resume_digest):
            return None
        now = self._clock()
        token = secrets.token_urlsafe(32)
        expires_at = now + self.session_ttl
        self._sessions[hashlib.sha256(token.encode()).hexdigest()] = expires_at
        return {
            "token": token,
            "resume_token": resume_token,
            "expires_at": expires_at,
            "expires_in": self.session_ttl,
        }

    def authenticate(self, token: Optional[str]) -> Optional[Dict[str, object]]:
        if not isinstance(token, str) or not token or len(token) > 256:
            return None
        key = hashlib.sha256(token.encode()).hexdigest()
        expires_at = self._sessions.get(key)
        if expires_at is None:
            return None
        if self._clock() >= expires_at:
            self._sessions.pop(key, None)
            return None
        return {"expires_at": expires_at, "startup_instance_id": self.startup_instance_id}

    def revoke(self, token: Optional[str]) -> None:
        if not self.pairing_enabled:
            return
        if isinstance(token, str):
            self._sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)
        self._resume_digest = None
        self.resume_path.unlink(missing_ok=True)

    def authorize_control(self, token: Optional[str]) -> bool:
        return isinstance(token, str) and hmac.compare_digest(token, self._control_token)

    def diagnostics(self) -> Dict[str, object]:
        return {
            "build_id": self.build_id,
            "schema_version": self.schema_version,
            "data_instance_id": self.data_instance_id,
            "startup_instance_id": self.startup_instance_id,
            "static_resource_build_id": self.static_resource_build_id,
            "local_auth_mode": self.local_auth_mode,
        }
