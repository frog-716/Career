"""Short-lived macOS Keychain helper and its bounded IPC framing.

The parent process owns the timeout and lifecycle.  This module deliberately
returns only safe status codes over the socket; a value returned by ``get`` is
the only secret-bearing field and travels over the anonymous socketpair.
"""

from __future__ import annotations

import json
import socket
import sys
from typing import Any, Mapping

from keyring.backends import macOS
from keyring import errors as keyring_errors


MAX_FRAME_BYTES = 2_000_000

_STATUS_CODES = {
    "item_not_found": -25300,
    "keychain_denied": -128,
    "sec_auth_failed": -25293,
    "plist_missing": -67030,
    "sec_interaction_not_allowed": -25308,
}


def _read_exact(channel: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = channel.recv(size - len(chunks))
        if not chunk:
            raise EOFError("socket closed")
        chunks.extend(chunk)
    return bytes(chunks)


def recv_frame(channel: socket.socket) -> dict[str, Any]:
    """Receive one bounded JSON object without logging its contents."""

    header = _read_exact(channel, 4)
    size = int.from_bytes(header, "big")
    if size <= 0 or size > MAX_FRAME_BYTES:
        raise ValueError("invalid frame size")
    payload = _read_exact(channel, size)
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("invalid frame object")
    return decoded


def send_frame(channel: socket.socket, payload: Mapping[str, Any]) -> None:
    """Send one bounded JSON object without printing its contents."""

    encoded = json.dumps(
        dict(payload), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    if not encoded or len(encoded) > MAX_FRAME_BYTES:
        raise ValueError("invalid frame size")
    channel.sendall(len(encoded).to_bytes(4, "big") + encoded)


def _exception_chain(exc: BaseException):
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _native_status(exc: BaseException) -> int | None:
    for item in _exception_chain(exc):
        for argument in getattr(item, "args", ()):
            if isinstance(argument, int):
                return argument
    return None


def classify_keychain_exception(exc: BaseException) -> str:
    """Classify known macOS/keyring failures without exposing exception text."""

    for item in _exception_chain(exc):
        name = type(item).__name__.casefold().replace("-", "_")
        if isinstance(item, keyring_errors.KeyringLocked) or "locked" in name:
            return "locked"
        if "interaction_not_allowed" in name or (
            "interaction" in name and "allow" in name
        ):
            return "interaction_not_allowed"
        if "notfound" in name or "not_found" in name:
            return "missing"
        if "denied" in name:
            return "denied"

    native_status = _native_status(exc)
    if native_status == _STATUS_CODES["sec_interaction_not_allowed"]:
        return "interaction_not_allowed"
    if native_status == _STATUS_CODES["item_not_found"]:
        return "missing"
    if native_status == _STATUS_CODES["keychain_denied"]:
        return "denied"
    if native_status in {
        _STATUS_CODES["sec_auth_failed"],
        _STATUS_CODES["plist_missing"],
    }:
        return "denied"
    return "error"


def _validate_request(request: Mapping[str, Any]) -> tuple[str, str, str, str | None]:
    operation = request.get("operation")
    service = request.get("service")
    account = request.get("account")
    value = request.get("value")
    if operation not in {"get", "put", "delete"}:
        raise ValueError("invalid operation")
    if not isinstance(service, str) or not service:
        raise ValueError("invalid service")
    if not isinstance(account, str) or not account:
        raise ValueError("invalid account")
    if operation == "put" and (not isinstance(value, str) or not value):
        raise ValueError("invalid value")
    if operation != "put" and value is not None and not isinstance(value, str):
        raise ValueError("invalid value")
    return operation, service, account, value


def handle(request: Mapping[str, Any]) -> dict[str, Any]:
    """Execute one request and return a secret-safe status response."""

    try:
        operation, service, account, value = _validate_request(request)
        backend = macOS.Keyring()
        if operation == "put":
            backend.set_password(service, account, value)
            return {"status": "ok"}
        if operation == "get":
            result = backend.get_password(service, account)
            if not isinstance(result, str) or not result:
                return {"status": "missing"}
            return {"status": "ok", "value": result}
        try:
            backend.delete_password(service, account)
        except Exception as exc:
            status = classify_keychain_exception(exc)
            if status == "missing":
                return {"status": "missing"}
            return {"status": status}
        return {"status": "ok"}
    except Exception as exc:
        return {"status": classify_keychain_exception(exc)}


def main(fd: int) -> int:
    """Serve exactly one request on an inherited socket and then exit."""

    channel = socket.socket(fileno=fd)
    try:
        response = handle(recv_frame(channel))
        send_frame(channel, response)
        return 0
    except Exception:
        # Do not include exception text: the parent maps EOF/malformed output
        # to a generic fail-closed error.
        return 1
    finally:
        channel.close()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--fd":
        raise SystemExit(2)
    try:
        _fd = int(sys.argv[2])
    except ValueError:
        raise SystemExit(2)
    raise SystemExit(main(_fd))
