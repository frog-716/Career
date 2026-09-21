#!/usr/bin/env python3
"""Scan current files and Git history without printing matching content."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{24,}\b"),
)
SKIP_PARTS = {".git", ".venv", "node_modules", "dist", "__pycache__"}


def suspicious(text: str) -> bool:
    return any(pattern.search(text) for pattern in PATTERNS)


def current_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line]


def main() -> int:
    matches: list[str] = []
    for path in current_files():
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(lines, 1):
            if suspicious(line):
                matches.append(f"current:{path.relative_to(ROOT)}:{line_number}")

    for pattern in PATTERNS:
        result = subprocess.run(
            ["git", "log", "--all", "--format=%H", "-G", pattern.pattern, "--"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        for commit in dict.fromkeys(result.stdout.splitlines()):
            matches.append(f"history:{commit[:12]}:{pattern.pattern}")

    if matches:
        print("secret-like matches found (content redacted):")
        print("\n".join(matches))
        print("Stop public reporting and manually revoke/confirm any suspected real credential.")
        return 2
    print("secret scan: no configured secret-like patterns in current files or Git history")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
