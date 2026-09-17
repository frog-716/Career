#!/usr/bin/env python3
"""Career 每周一数据备份。

只复制生产数据，不启动服务、不读取前端；正常运行不会写入生产数据库。
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workbench.backup import backup


DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "Career Data"
DEFAULT_BACKUP_DIR = Path.home() / "Library" / "Application Support" / "Career Data-backups"


def monday_label(day: date | None = None) -> str:
    current = day or datetime.now().astimezone().date()
    monday = current - timedelta(days=current.weekday())
    return monday.strftime("%Y%m%d")


def weekly_target(backup_dir: Path = DEFAULT_BACKUP_DIR, day: date | None = None) -> Path:
    return backup_dir.expanduser().resolve() / monday_label(day)


def create_weekly_backup(
    data_dir: Path = DEFAULT_DATA_DIR,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    day: date | None = None,
    dry_run: bool = False,
) -> Path:
    source = data_dir.expanduser().resolve()
    target = weekly_target(backup_dir, day)
    if dry_run:
        return target
    if target.exists():
        return target
    created = backup(source, target.parent, backup_name=target.name)
    return Path(created)


def main() -> int:
    parser = argparse.ArgumentParser(description="Career 每周一数据备份")
    parser.add_argument("--dry-run", action="store_true", help="只显示本周一目标目录，不创建备份")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    args = parser.parse_args()
    target = create_weekly_backup(args.data_dir, args.backup_dir, dry_run=args.dry_run)
    if args.dry_run:
        print(f"本次目标：{target}")
    elif target.exists() and target.name == monday_label():
        print(f"每周备份：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
