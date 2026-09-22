"""External helper probe used only by keychain timeout tests."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time

from workbench.secret_store_helper import recv_frame, send_frame


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fd", type=int, required=True)
    args = parser.parse_args()
    channel = socket.socket(fileno=args.fd)
    request = recv_frame(channel)
    account = request.get("account")
    if account == "hang":
        time.sleep(60)
        return 0
    if account == "crash":
        os._exit(17)
    if account == "malformed":
        channel.sendall(b"not-a-valid-frame")
        return 0
    if account == "inspect":
        secret = request.get("value") or "helper-secret"
        send_frame(
            channel,
            {
                "status": "ok",
                "value": secret,
                "argv_has_secret": any(secret and secret in value for value in sys.argv),
                "environment_has_secret": any(secret and secret in value for value in os.environ.values()),
            },
        )
        return 0
    if account == "locked":
        send_frame(channel, {"status": "locked"})
        return 0
    if account == "denied":
        send_frame(channel, {"status": "denied"})
        return 0
    if account == "interaction":
        send_frame(channel, {"status": "interaction_not_allowed"})
        return 0
    if account == "missing":
        send_frame(channel, {"status": "missing"})
        return 0
    if request.get("operation") == "get":
        send_frame(channel, {"status": "ok", "value": "helper-secret"})
    else:
        send_frame(channel, {"status": "ok"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
