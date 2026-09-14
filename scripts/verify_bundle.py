#!/usr/bin/env python3
"""Check a sealed context kit; no network or external project access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {"__pycache__", ".DS_Store"}


def payload_files(root):
    return sorted(p for p in root.rglob("*") if p.is_file()
                  and not any(part in IGNORED for part in p.relative_to(root).parts)
                  and p.name != "MANIFEST.json" and p.suffix != ".pyc")


def check(root, strict=False, manifest=None):
    errors = []
    if manifest is None:
        manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    entries = manifest["files"]
    seen = set()
    for entry in entries:
        name = entry["path"]
        target = root / name
        if name in seen or Path(name).is_absolute() or ".." in Path(name).parts:
            errors.append("Invalid manifest path: " + name)
            continue
        seen.add(name)
        if target.is_symlink() or not target.is_file():
            errors.append("Missing file or symlink: " + name)
            continue
        data = target.read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            errors.append("Hash/size mismatch: " + name)
    actual = {p.relative_to(root).as_posix() for p in payload_files(root)}
    if strict and actual != seen:
        errors.append("Manifest file set differs: " + str(sorted(actual ^ seen)))

    # No real machine paths, private app addresses, or token-shaped secrets.
    patterns = [r"/(?:Users|home)/[^/\s]+/", r"https://[^\s/]+\.feishuapp\.com/",
                r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"]
    for path in payload_files(root):
        relative = path.relative_to(root)
        if path.is_symlink():
            errors.append("Symlink: " + str(relative))
            continue
        if path.suffix in {".sqlite", ".sqlite3", ".pdf", ".mp3", ".wav", ".zip"}:
            errors.append("Unexpected private/binary artifact: " + str(relative))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            errors.append("Non-text file cannot be scanned: " + str(relative))
            continue
        if any(re.search(pattern, text) for pattern in patterns):
            errors.append("Potential contamination in: " + str(relative))
        if path.suffix == ".md":
            for match in re.finditer(r"\]\(([^)]+)\)", text):
                link = match.group(1)
                if re.match(r"https?://|#", link):
                    continue
                linked = (path.parent / link.split("#", 1)[0]).resolve()
                if root.resolve() not in linked.parents and linked != root.resolve():
                    errors.append("Nonportable link: " + str(relative))
                elif not linked.exists():
                    errors.append("Broken link in " + str(relative) + ": " + link)
        if path.name == "SKILL.md":
            if not re.match(r"---\nname: [a-z0-9-]+\ndescription: [^\n]+\n---\n", text):
                errors.append("Invalid skill entry: " + str(relative))
    fixture = json.loads((root / "fixtures/scenarios.json").read_text(encoding="utf-8"))
    if fixture.get("synthetic") is not True:
        errors.append("Fixture is not explicitly synthetic")
    return errors, len(entries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Also reject unlisted files")
    args = parser.parse_args()
    try:
        problems, count = check(ROOT, args.strict)
    except (OSError, ValueError, KeyError) as exc:
        print("FAIL:", exc)
        sys.exit(1)
    if problems:
        print("\n".join("FAIL: " + problem for problem in problems))
        sys.exit(1)
    print(f"PASS: {count} payload files; hashes, local links, skill entries and contamination checks")
