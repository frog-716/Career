#!/usr/bin/env python3
"""Explicit read-only migration inventory / restored-backup verification."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from workbench.migration_baseline import inventory, verify_restore, write_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    scan = commands.add_parser('inventory')
    scan.add_argument('data_dir')
    verify = commands.add_parser('verify')
    verify.add_argument('backup_dir')
    verify.add_argument('restored_dir')
    for command in (scan, verify): command.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.action == 'inventory':
            report = inventory(args.data_dir)
            protected = [args.data_dir]
            passed = report['integrity'] == ['ok'] and not report['foreign_key_violations'] and not report['integrity_issues']
        else:
            report = verify_restore(args.backup_dir, args.restored_dir)
            protected = [args.backup_dir, args.restored_dir]
            passed = report['verified']
        write_report(args.output, report, protected)
        print(json.dumps(dict(report=str(Path(args.output).resolve()), integrity_verified=passed,
                              migration_performed=False)))
        return 0 if passed else 2
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print('Migration baseline failed: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
