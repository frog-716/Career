#!/usr/bin/env python3
"""Reproducible local T12 quality entry point; never targets a production URL."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = (
    ROOT / "README.md",
    ROOT / "frontend" / "README.md",
    ROOT / "src" / "workbench" / "README.md",
    ROOT / "docs" / "00-authority.md",
    ROOT / "docs" / "02-context-contract.md",
    ROOT / "docs" / "03-architecture.md",
    ROOT / "docs" / "04-journeys.md",
    ROOT / "docs" / "05-acceptance.md",
    ROOT / "docs" / "07-roadmap.md",
    ROOT / "docs" / "execution" / "IMPLEMENTATION-PLAN.md",
    ROOT / "docs" / "execution" / "STATUS.md",
)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def check_markdown_links() -> int:
    failures: list[str] = []
    for path in MARKDOWN_FILES:
        text = path.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            target = target.strip().strip("<>").split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:", "codex:")):
                continue
            candidate = (path.parent / target).resolve()
            if not candidate.exists():
                failures.append(f"{path.relative_to(ROOT)} -> {target}")
    if failures:
        print("markdown link failures:")
        print("\n".join(failures))
        return 1
    print("markdown links: checked files and local targets")
    return 0


def run(command: list[str]) -> int:
    rendered = " ".join(command)
    result = subprocess.run(command, cwd=ROOT)
    print(f"{rendered} -> exit {result.returncode}")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-only", action="store_true")
    args = parser.parse_args()
    checks: list[tuple[str, list[str]]] = []
    if not args.docs_only:
        checks.extend(
            [
                ("backend regression", [sys.executable, "-B", "-m", "pytest", "-q"]),
                ("frontend typecheck", ["npm", "--prefix", "frontend", "run", "typecheck"]),
                ("frontend build", ["npm", "--prefix", "frontend", "run", "build"]),
                ("python dependencies", [sys.executable, "-m", "pip", "check"]),
                ("frontend dependencies", ["npm", "--prefix", "frontend", "ls", "--depth=0"]),
                ("secret scan", [sys.executable, "scripts/secret_scan.py"]),
                ("diff whitespace", ["git", "diff", "--check"]),
            ]
        )
    statuses = [check_markdown_links()]
    statuses.extend(run(command) for _, command in checks)
    return max(statuses, default=0)


if __name__ == "__main__":
    raise SystemExit(main())
