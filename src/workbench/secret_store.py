"""OS-backed secret storage for local Career installations.

Only opaque references are persisted in Career data. Production uses the
explicit macOS Keyring backend; the generic keyring backend selector is never
consulted and there is no plaintext fallback.
"""

import platform
import secrets
from typing import Optional

from keyring.backends import macOS
from keyring import errors as keyring_errors


class SecretStoreError(Exception):
    """Safe, user-facing secret-store failure without secret-bearing text."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _classify_error(exc: Exception, default: str = "error") -> str:
    name = type(exc).__name__.casefold()
    return "locked" if "lock" in name else default


class SecretStore:
    def allocate_ref(self) -> str:
        raise NotImplementedError

    def put(self, ref: Optional[str], value: str) -> str:
        raise NotImplementedError

    def get(self, ref: str) -> str:
        raise NotImplementedError

    def delete(self, ref: str) -> None:
        raise NotImplementedError


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

    def __init__(self, backend=None, platform_name: Optional[str] = None):
        # Tests inject a fake backend. Production deliberately instantiates
        # this concrete backend rather than asking keyring to auto-select one.
        self._backend = backend
        self._platform_name = platform_name

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

    def put(self, ref: Optional[str], value: str) -> str:
        if not isinstance(value, str) or not value:
            raise SecretStoreError("error", "API Key 不能为空")
        account = ref or self.allocate_ref()
        try:
            self.backend.set_password(self.service, account, value)
        except Exception as exc:
            raise SecretStoreError(
                _classify_error(exc),
                "无法写入 macOS Keychain，请检查钥匙串权限",
            ) from exc
        return account

    def get(self, ref: str) -> str:
        if not ref:
            raise SecretStoreError("missing", "Keychain 中找不到该模型配置的 API Key")
        try:
            value = self.backend.get_password(self.service, ref)
        except Exception as exc:
            raise SecretStoreError(
                _classify_error(exc, "error"),
                "无法读取 macOS Keychain，请检查钥匙串权限",
            ) from exc
        if not isinstance(value, str) or not value:
            raise SecretStoreError("missing", "Keychain 中找不到该模型配置的 API Key")
        return value

    def delete(self, ref: str) -> None:
        if not ref:
            return
        try:
            self.backend.delete_password(self.service, ref)
        except keyring_errors.PasswordDeleteError as exc:
            # The desired state is already true when the item is absent; all
            # other deletion failures remain actionable cleanup failures.
            message = str(exc).casefold()
            if "not found" in message or "no password" in message or "no such password" in message:
                return
            raise SecretStoreError("error", "无法从 macOS Keychain 删除该 API Key") from exc
        except Exception as exc:
            raise SecretStoreError(
                _classify_error(exc),
                "无法从 macOS Keychain 删除该 API Key",
            ) from exc


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
