#!/usr/bin/env python3
"""Career 每周一数据备份。

只复制生产数据，不启动服务、不读取前端；正常运行不会写入生产数据库。
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workbench.backup import backup, update_backup_status, verify_backup


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
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.exists():
        checked = verify_backup(target)
        if checked["healthy"]:
            _record_success(target.parent, checked)
            return target
        repair_name = f"{target.name}.repair-{uuid.uuid4().hex}"
        try:
            created = backup(source, target.parent, backup_name=repair_name)
        except Exception as exc:
            update_backup_status(target.parent, last_error=str(exc))
            raise
        _record_result(target.parent, verify_backup(created))
        return Path(created)
    try:
        created = backup(source, target.parent, backup_name=target.name)
    except Exception as exc:
        update_backup_status(target.parent, last_error=str(exc))
        raise
    checked = verify_backup(created)
    _record_result(target.parent, checked)
    return Path(created)


def _record_success(backup_dir, checked):
    created_at = checked.get("created_at")
    age = None
    if created_at:
        try:
            age = max(0.0, (datetime.now(timezone.utc) - datetime.fromisoformat(created_at)).total_seconds())
        except ValueError:
            age = None
    update_backup_status(
        backup_dir,
        last_success_at=datetime.now(timezone.utc).isoformat(),
        recovery_point_age=age,
        last_error=None,
    )


def _record_result(backup_dir, checked):
    if checked.get("healthy"):
        _record_success(backup_dir, checked)
    else:
        update_backup_status(
            backup_dir,
            last_error="备份已发布但不完整：" + "; ".join(checked.get("differences", [])),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Career 每周一数据备份")
    parser.add_argument("--dry-run", action="store_true", help="只显示本周一目标目录，不创建备份")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    args = parser.parse_args()
    target = create_weekly_backup(args.data_dir, args.backup_dir, dry_run=args.dry_run)
    if args.dry_run:
        print(f"本次目标：{target}")
    else:
        checked = verify_backup(target)
        print(f"每周备份：{target}（status={checked['status']}，恢复点时间={checked['created_at']}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
