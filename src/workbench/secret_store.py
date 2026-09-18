"""OS-backed secret storage for local Career installations.

The database stores only opaque references.  This module intentionally has no
fallback to a file, SQLite, browser storage, or environment export when a
Keychain is unavailable.
"""
import platform
import secrets
import subprocess
from typing import Optional

def _error(message):
    from .core import Invalid
    return Invalid(message)


class SecretStore:
    def put(self, ref: Optional[str], value: str) -> str:
        raise NotImplementedError

    def get(self, ref: str) -> str:
        raise NotImplementedError

    def delete(self, ref: str) -> None:
        raise NotImplementedError


class KeychainSecretStore(SecretStore):
    service = "Career OS AI Model Config"

    def _check(self):
        if platform.system() != "Darwin":
            raise _error("当前平台没有可用的 macOS Keychain；不会把 API Key 写入不安全存储")

    def put(self, ref: Optional[str], value: str) -> str:
        self._check()
        if not isinstance(value, str) or not value:
            raise _error("API Key 不能为空")
        account = ref or "career-ai-" + secrets.token_urlsafe(18)
        result = subprocess.run(
            ["/usr/bin/security", "add-generic-password", "-a", account,
             "-s", self.service, "-w", value, "-U"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            check=False,
        )
        if result.returncode:
            raise _error("无法写入 macOS Keychain，请检查钥匙串权限")
        return account

    def get(self, ref: str) -> str:
        self._check()
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-a", ref,
             "-s", self.service, "-w"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            check=False,
        )
        if result.returncode or not result.stdout.strip():
            raise _error("Keychain 中找不到该模型配置的 API Key")
        return result.stdout.rstrip("\r\n")

    def delete(self, ref: str) -> None:
        self._check()
        result = subprocess.run(
            ["/usr/bin/security", "delete-generic-password", "-a", ref,
             "-s", self.service],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        # Missing entries are already in the desired state.
        if result.returncode not in (0, 44):
            raise _error("无法从 macOS Keychain 删除该 API Key")


class MemorySecretStore(SecretStore):
    """Explicit test-only store; never selected by production code."""
    def __init__(self):
        self.values: dict[str, str] = {}

    def put(self, ref: Optional[str], value: str) -> str:
        key = ref or "test-secret-" + secrets.token_hex(8)
        self.values[key] = value
        return key

    def get(self, ref: str) -> str:
        if ref not in self.values:
            raise _error("测试 SecretStore 中找不到 API Key")
        return self.values[ref]

    def delete(self, ref: str) -> None:
        self.values.pop(ref, None)
