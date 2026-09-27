#!/usr/bin/env python3
"""Print only whitelisted local runtime and SQLite metadata."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path


def _health(base_url: str) -> dict[str, str]:
    request = urllib.request.Request(base_url.rstrip("/") + "/healthz", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.load(response)
        status = payload.get("status")
        build_id = payload.get("build_id")
        return {
            "status": status if status == "ok" else "unavailable",
            "build_id": build_id if isinstance(build_id, str) and len(build_id) <= 100 else "",
        }
    except (OSError, ValueError, urllib.error.URLError):
        return {"status": "unavailable", "build_id": ""}


def _id_manifest_digest(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    queries = (
        ("current", "SELECT id, kind, revision FROM current ORDER BY id"),
        ("records", "SELECT id, kind FROM records ORDER BY id"),
        ("revisions", "SELECT id, revision FROM revisions ORDER BY id, revision"),
    )
    for table, query in queries:
        for row in connection.execute(query):
            digest.update(table.encode("ascii"))
            digest.update(b"\0")
            digest.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()


def _database(data_dir: Path) -> dict[str, object]:
    db_path = (data_dir / "workspace.sqlite3").resolve()
    connection = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        row_counts = {
            "current": connection.execute("SELECT COUNT(*) FROM current").fetchone()[0],
            "records": connection.execute("SELECT COUNT(*) FROM records").fetchone()[0],
            "revisions": connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0],
        }
        try:
            data_instance_id = (data_dir / ".career-instance").read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            data_instance_id = ""
        if not re.fullmatch(r"[0-9a-f]{32}", data_instance_id):
            data_instance_id = ""
        return {
            "quick_check": quick_check,
            "schema_version": schema_version,
            "data_instance_id": data_instance_id,
            "row_counts": row_counts,
            "revision_count": row_counts["revisions"],
            "id_manifest_sha256": _id_manifest_digest(connection),
        }
    finally:
        connection.close()


def collect_runtime_health(base_url: str, data_dir: Path) -> dict[str, object]:
    """Read `/healthz` plus table counts and ID metadata; never select row bodies."""
    return {"health": _health(base_url), "database": _database(Path(data_dir))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument(
        "--data-dir",
        default=str(Path.home() / "Library/Application Support/Career Data"),
    )
    args = parser.parse_args(argv)
    print(json.dumps(collect_runtime_health(args.url, Path(args.data_dir)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
