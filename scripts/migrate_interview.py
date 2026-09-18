#!/usr/bin/env python3
"""Explicit isolated v4→v5 Interview migration rehearsal; production cutover is unsupported."""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workbench.interview_migration import apply_migration, dry_run, verify_migration
from workbench.core import Conflict, Invalid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["dry-run", "apply", "verify"])
    parser.add_argument("data_dir")
    parser.add_argument("--plan")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        output = Path(args.output).expanduser().absolute()
        root = Path(args.data_dir).expanduser().resolve()
        if output.resolve() == root or root in output.resolve().parents:
            raise Invalid("报告必须位于受检数据目录之外")
        with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            try:
                if args.action == "dry-run":
                    result = dry_run(root)
                elif args.action == "verify":
                    result = verify_migration(root)
                else:
                    if not args.plan:
                        raise Invalid("apply需要--plan")
                    result = apply_migration(root, json.loads(Path(args.plan).read_text()))
                json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
                stream.write("\n")
            except Exception as exc:
                json.dump({"status": "failed", "error": str(exc)}, stream, ensure_ascii=False)
                raise
        print(json.dumps({"report": str(output.resolve()), "production_cutover": False}))
        return 0 if result.get("verified", True) else 2
    except (Invalid, Conflict, ValueError, OSError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
