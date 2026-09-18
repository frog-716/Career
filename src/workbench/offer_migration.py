"""Hash-bound schema v5→v6 runtime fence for canonical Offer writes."""
import json
import sqlite3
from pathlib import Path

from .core import Conflict, Invalid, digest, dump, now
from .migration_baseline import _hash, inventory
from .opportunity_migration import isolated_root


MIGRATION_ID = "migration:offer-v6-fence"
MIGRATION_KIND = "offer_migration"


def dry_run(data_dir):
    root = Path(data_dir).expanduser().resolve()
    report = inventory(root)
    report.pop("observed_at", None)
    if report["snapshot"]["schema_version"] != 5:
        raise Invalid("需要schema v5源副本")
    if report["integrity"] != ["ok"] or report["integrity_issues"] or report["foreign_key_violations"]:
        raise Invalid("源完整性未通过")
    return {
        "migration_id": MIGRATION_ID,
        "source_snapshot_sha256": report["snapshot_sha256"],
        "source_schema_version": 5,
        "target_schema_version": 6,
        "business_rewrite": False,
        "inventory": report,
    }


def apply_migration(data_dir, plan, fault=lambda point: None):
    root = isolated_root(data_dir)
    if (root / "artifacts").is_symlink():
        raise Invalid("附件目录不能是链接")
    fingerprint = digest(plan)
    with sqlite3.connect(root / "workspace.sqlite3") as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        saved = connection.execute(
            "SELECT body FROM records WHERE id=? AND kind=?", (MIGRATION_ID, MIGRATION_KIND)
        ).fetchone()
        if saved:
            saved = json.loads(saved[0])
            if saved["fingerprint"] != fingerprint:
                raise Conflict("迁移输入已变化")
            if connection.execute("PRAGMA user_version").fetchone()[0] != 6:
                raise Invalid("迁移标记/schema不一致")
            return saved["result"]
        actual = dry_run(root)
        if actual != plan:
            raise Conflict("源数据/计划已变化，请重新dry-run")
        result = {
            "schema_version": 6,
            "rewritten_business_rows": 0,
            "added_constraints": [],
            "runtime_fence": "batch-f-v6",
        }
        record = {
            "id": MIGRATION_ID,
            "fingerprint": fingerprint,
            "plan": plan,
            "result": result,
            "created_at": now(),
        }
        connection.execute(
            "INSERT INTO records VALUES(?,?,?)", (MIGRATION_ID, MIGRATION_KIND, dump(record))
        )
        fault("after_manifest")
        connection.execute("PRAGMA user_version=6")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise Invalid("迁移FK检查失败")
        fault("before_commit")
    return result


def verify_migration(data_dir):
    root = Path(data_dir).expanduser().resolve()
    report = inventory(root)
    with sqlite3.connect((root / "workspace.sqlite3").as_uri() + "?mode=ro", uri=True) as connection:
        row = connection.execute(
            "SELECT body FROM records WHERE id=? AND kind=?", (MIGRATION_ID, MIGRATION_KIND)
        ).fetchone()
        if not row:
            raise Invalid("没有F v6迁移标记")
        saved = json.loads(row[0])
        before = saved["plan"]["inventory"]["snapshot"]
        differences = []
        if digest(saved["plan"]) != saved["fingerprint"]:
            differences.append("manifest_fingerprint")
        if _hash(before) != saved["plan"]["source_snapshot_sha256"]:
            differences.append("source_snapshot_hash")
        if saved["result"] != {
            "schema_version": 6,
            "rewritten_business_rows": 0,
            "added_constraints": [],
            "runtime_fence": "batch-f-v6",
        }:
            differences.append("migration_result")
        for table, hashes in before["row_hashes"].items():
            after = report["snapshot"]["row_hashes"][table]
            for identifier, value in hashes.items():
                if after.get(identifier) != value:
                    differences.append({"table": table, "id": identifier})
        expected_counts = dict(before["table_counts"])
        expected_counts["records"] += 1
        if report["snapshot"]["table_counts"] != expected_counts:
            differences.append({"table_counts": report["snapshot"]["table_counts"]})
        if report["snapshot"]["schema_hash"] != before["schema_hash"]:
            differences.append("schema_objects_changed")
        if report["snapshot"]["artifact_files"] != before["artifact_files"]:
            differences.append("artifact_bytes")
        if report["snapshot"]["schema_version"] != 6:
            differences.append("schema_version")
    differences += report["integrity_issues"] + report["foreign_key_violations"]
    return {
        "verified": not differences and report["integrity"] == ["ok"],
        "differences": differences,
        "schema_version": 6,
        "table_counts": report["snapshot"]["table_counts"],
        "snapshot_sha256": report["snapshot_sha256"],
        "rewritten_business_rows": saved["result"]["rewritten_business_rows"],
        "added_constraints": saved["result"]["added_constraints"],
    }
