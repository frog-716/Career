"""OS-backed secret storage for local Career installations.

Only opaque references are persisted in Career data. Production uses the
explicit macOS Keyring backend; the generic keyring backend selector is never
consulted and there is no plaintext fallback. Native Keychain calls run in a
short-lived helper owned by this module so the Career process can enforce a
bounded wait and terminate a stuck native call.
"""

from __future__ import annotations

import os
import platform
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from keyring import errors as keyring_errors
from keyring.backends import macOS

from .secret_store_helper import (
    classify_keychain_exception,
    recv_frame,
    send_frame,
)


DEFAULT_HELPER_TIMEOUT_SECONDS = 2.0
_SAFE_HELPER_ENVIRONMENT = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
    "KEYCHAIN_PATH",
)
_STATUS_MESSAGES = {
    "missing": "Keychain 中找不到该模型配置的 API Key",
    "denied": "macOS Keychain 拒绝访问",
    "locked": "macOS Keychain 处于锁定状态",
    "interaction_not_allowed": "macOS Keychain 当前不允许交互授权",
    "timeout": "macOS Keychain 操作超时",
    "error": "macOS Keychain 操作失败",
}
_KNOWN_HELPER_STATUSES = {"ok", *tuple(_STATUS_MESSAGES)}


class SecretStoreError(Exception):
    """Safe, user-facing secret-store failure without secret-bearing text."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _classify_error(exc: Exception, default: str = "error") -> str:
    status = classify_keychain_exception(exc)
    return status if status != "error" else default


def _looks_like_missing_delete(exc: BaseException) -> bool:
    """Use exception wording only for classification; never return it."""

    wording = str(exc).casefold()
    return any(
        marker in wording
        for marker in ("not found", "no password", "no such password")
    )


class SecretStore:
    def allocate_ref(self) -> str:
        raise NotImplementedError

    def put(self, ref: Optional[str], value: str) -> str:
        raise NotImplementedError

    def get(self, ref: str) -> str:
        raise NotImplementedError

    def delete(self, ref: str) -> None:
        raise NotImplementedError

    def shutdown(self) -> None:
        """Stop any implementation-owned child work before process shutdown."""


class LocalOnlySecretStore(SecretStore):
    """A non-Keychain implementation used by fail-closed instances."""

    def _blocked(self):
        raise SecretStoreError(
            "local_only_disabled",
            "local_only_disabled: LOCAL_ONLY 不允许访问 SecretStore",
        )

    def allocate_ref(self) -> str:
        return self._blocked()

    def put(self, ref: Optional[str], value: str) -> str:
        return self._blocked()

    def get(self, ref: str) -> str:
        return self._blocked()

    def delete(self, ref: str) -> None:
        self._blocked()


class KeychainSecretStore(SecretStore):
    service = "Career OS AI Model Config"

    def __init__(
        self,
        backend=None,
        platform_name: Optional[str] = None,
        helper_timeout_seconds: float = DEFAULT_HELPER_TIMEOUT_SECONDS,
        helper_command=None,
    ):
        # Tests inject a fake backend. Production deliberately instantiates
        # this concrete backend in the helper rather than asking keyring to
        # auto-select one.
        self._backend = backend
        self._platform_name = platform_name
        try:
            self._helper_timeout_seconds = float(helper_timeout_seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError("helper_timeout_seconds must be positive") from exc
        if self._helper_timeout_seconds <= 0:
            raise ValueError("helper_timeout_seconds must be positive")

        default_command = (
            sys.executable,
            "-m",
            "workbench.secret_store_helper",
        )
        self._helper_command = tuple(helper_command or default_command)
        self._helper_lock = threading.Lock()
        self._active_helpers: set[subprocess.Popen] = set()

    def _check(self) -> None:
        if (self._platform_name or platform.system()) != "Darwin":
            raise SecretStoreError(
                "unavailable",
                "当前平台没有可用的 macOS Keychain；不会把 API Key 写入不安全存储",
            )

    @property
    def backend(self):
        self._check()
        if self._backend is None:
            self._backend = macOS.Keyring()
        return self._backend

    def allocate_ref(self) -> str:
        return "career-ai-" + secrets.token_urlsafe(18)

    @staticmethod
    def _safe_helper_environment() -> dict[str, str]:
        environment = {
            key: value
            for key in _SAFE_HELPER_ENVIRONMENT
            if (value := os.environ.get(key)) is not None
        }
        environment["PYTHONNOUSERSITE"] = "1"
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        return environment

    def _register_helper(self, process: subprocess.Popen) -> None:
        with self._helper_lock:
            self._active_helpers.add(process)

    def _unregister_helper(self, process: subprocess.Popen) -> None:
        with self._helper_lock:
            self._active_helpers.discard(process)

    @staticmethod
    def _terminate_helper(process: subprocess.Popen) -> bool:
        if process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
        return process.poll() is not None

    def _run_helper(self, operation: str, ref: str, value: Optional[str] = None):
        self._check()
        parent, child = socket.socketpair()
        process = None
        deadline = time.monotonic() + self._helper_timeout_seconds
        request = {
            "operation": operation,
            "service": self.service,
            "account": ref,
        }
        if value is not None:
            # This is the only secret-bearing boundary: an anonymous,
            # process-local socketpair. It is never part of argv or env.
            request["value"] = value

        try:
            command = [*self._helper_command, "--fd", str(child.fileno())]
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env=self._safe_helper_environment(),
                pass_fds=(child.fileno(),),
            )
            self._register_helper(process)
            child.close()
            child = None
            parent.settimeout(max(0.001, deadline - time.monotonic()))
            send_frame(parent, request)
            parent.settimeout(max(0.001, deadline - time.monotonic()))
            response = recv_frame(parent)
            if not isinstance(response.get("status"), str):
                raise ValueError("helper response has no status")
            if response["status"] not in _KNOWN_HELPER_STATUSES:
                raise ValueError("helper response has unknown status")

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if not self._terminate_helper(process):
                    raise SecretStoreError("error", _STATUS_MESSAGES["error"])
                raise SecretStoreError("timeout", _STATUS_MESSAGES["timeout"])
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                if not self._terminate_helper(process):
                    raise SecretStoreError("error", _STATUS_MESSAGES["error"])
                raise SecretStoreError("timeout", _STATUS_MESSAGES["timeout"])
            if process.returncode != 0:
                raise SecretStoreError("error", _STATUS_MESSAGES["error"])
            return response
        except SecretStoreError:
            raise
        except (socket.timeout, TimeoutError):
            if process is not None and not self._terminate_helper(process):
                raise SecretStoreError("error", _STATUS_MESSAGES["error"])
            raise SecretStoreError("timeout", _STATUS_MESSAGES["timeout"])
        except Exception as exc:
            if process is not None and not self._terminate_helper(process):
                raise SecretStoreError("error", _STATUS_MESSAGES["error"])
            raise SecretStoreError("error", _STATUS_MESSAGES["error"]) from None
        finally:
            if process is not None:
                if process.poll() is None:
                    self._terminate_helper(process)
                self._unregister_helper(process)
            parent.close()
            if child is not None:
                child.close()

    @staticmethod
    def _raise_for_status(status: str) -> None:
        if status == "ok":
            return
        if status not in _STATUS_MESSAGES:
            raise SecretStoreError("error", _STATUS_MESSAGES["error"])
        raise SecretStoreError(status, _STATUS_MESSAGES[status])

    def put(self, ref: Optional[str], value: str) -> str:
        if not isinstance(value, str) or not value:
            raise SecretStoreError("error", "API Key 不能为空")
        account = ref or self.allocate_ref()
        if self._backend is None:
            response = self._run_helper("put", account, value)
            self._raise_for_status(response["status"])
            return account
        try:
            self.backend.set_password(self.service, account, value)
        except Exception as exc:
            status = _classify_error(exc)
            raise SecretStoreError(status, _STATUS_MESSAGES.get(status, _STATUS_MESSAGES["error"])) from None
        return account

    def get(self, ref: str) -> str:
        if not ref:
            raise SecretStoreError("missing", _STATUS_MESSAGES["missing"])
        if self._backend is None:
            response = self._run_helper("get", ref)
            self._raise_for_status(response["status"])
            value = response.get("value")
            if not isinstance(value, str) or not value:
                raise SecretStoreError("error", _STATUS_MESSAGES["error"])
            return value
        try:
            value = self.backend.get_password(self.service, ref)
        except Exception as exc:
            status = _classify_error(exc)
            raise SecretStoreError(status, _STATUS_MESSAGES.get(status, _STATUS_MESSAGES["error"])) from None
        if not isinstance(value, str) or not value:
            raise SecretStoreError("missing", _STATUS_MESSAGES["missing"])
        return value

    def delete(self, ref: str) -> None:
        if not ref:
            return
        if self._backend is None:
            response = self._run_helper("delete", ref)
            if response["status"] == "missing":
                return
            self._raise_for_status(response["status"])
            return
        try:
            self.backend.delete_password(self.service, ref)
        except keyring_errors.PasswordDeleteError as exc:
            # The desired state is already true when the item is absent; all
            # other deletion failures remain actionable cleanup failures.
            status = _classify_error(exc)
            if status == "missing" or _looks_like_missing_delete(exc):
                return
            raise SecretStoreError(status, _STATUS_MESSAGES.get(status, _STATUS_MESSAGES["error"])) from None
        except Exception as exc:
            status = _classify_error(exc)
            raise SecretStoreError(status, _STATUS_MESSAGES.get(status, _STATUS_MESSAGES["error"])) from None

    def shutdown(self) -> None:
        """Terminate any still-running helper and confirm no child remains."""

        with self._helper_lock:
            processes = tuple(self._active_helpers)
        for process in processes:
            self._terminate_helper(process)


class MemorySecretStore(SecretStore):
    """Explicit test-only store; never selected by production code."""

    def __init__(self):
        self.values: dict[str, str] = {}

    def allocate_ref(self) -> str:
        return "test-secret-" + secrets.token_hex(8)

    def put(self, ref: Optional[str], value: str) -> str:
        if not isinstance(value, str) or not value:
            raise SecretStoreError("error", "API Key 不能为空")
        key = ref or self.allocate_ref()
        self.values[key] = value
        return key

    def get(self, ref: str) -> str:
        if ref not in self.values:
            raise SecretStoreError("missing", "测试 SecretStore 中找不到 API Key")
        return self.values[ref]

    def delete(self, ref: str) -> None:
        self.values.pop(ref, None)
