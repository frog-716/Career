"""Hash-bound schema v3→v4 write-contract fence for Communication."""
import json
import sqlite3
from pathlib import Path

from .core import Conflict, Invalid, digest, dump, now
from .migration_baseline import _hash, inventory
from .opportunity import canonical_id
from .opportunity_migration import isolated_root


MIGRATION_ID = "migration:communication-v4"


def _classify(root):
    with sqlite3.connect((root / "workspace.sqlite3").as_uri() + "?mode=ro", uri=True) as c:
        opportunities = {row[0] for row in c.execute("SELECT id FROM current WHERE kind='opportunity' AND json_extract(body,'$.format_version')=2")}
        jobs = {row[0]: json.loads(row[1]) for row in c.execute("SELECT id,body FROM current WHERE kind='job'")}
        notes = {row[0]: json.loads(row[1]) for row in c.execute("SELECT id,body FROM records WHERE kind='journey_note'")}
        communications = [json.loads(row[0]) for row in c.execute("SELECT body FROM records WHERE kind='communication' ORDER BY id")]
        note_links = {}
        rows = []
        gates = []
        demo_legacy = []
        for item in communications:
            note_id = item.get("raw_note_id")
            if note_id:
                note_links.setdefault(note_id, []).append(item["id"])
            owner = item.get("opportunity_id")
            canonical_owner = canonical_id(owner) if isinstance(owner, str) and owner else None
            alias = canonical_owner.split(":", 1)[1] if canonical_owner and ":" in canonical_owner else None
            owner_known = canonical_owner in opportunities
            legacy_owner = alias in jobs
            is_demo = bool(legacy_owner and jobs[alias].get("demo_dataset_id"))
            source_state = "not_applicable" if item.get("communication_format") == 2 else ("present" if note_id in notes else "missing")
            occurred = item.get("occurred_on") if item.get("communication_format") == 2 else item.get("occurred_at")
            rows.append({
                "communication_id": item["id"], "format": item.get("communication_format", "legacy"),
                "opportunity_id": canonical_owner, "owner_known": owner_known,
                "legacy_owner_readable": legacy_owner, "demo_legacy": is_demo,
                "raw_note_id": note_id, "raw_note_state": source_state,
                "occurred_value": occurred, "type": item.get("type"),
                "archived": item.get("archived", False),
            })
            if not owner_known and not legacy_owner:
                gates.append({"code": "communication_owner_unknown", "communication_id": item["id"], "opportunity_id": canonical_owner})
        duplicate_links = [{"raw_note_id": note_id, "communication_ids": ids} for note_id, ids in sorted(note_links.items()) if len(ids) > 1]
        for duplicate in duplicate_links:
            linked = [row for row in rows if row.get("raw_note_id") == duplicate["raw_note_id"]]
            finding = {"code": "multiple_typed_communications_for_note", **duplicate}
            if linked and all(row["demo_legacy"] for row in linked):
                demo_legacy.append(finding)
            else:
                gates.append(finding)
        typed_note_ids = set(note_links)
        note_only = [note_id for note_id, note in notes.items()
                     if note.get("scope_type") == "job" and note.get("kind") == "communication" and note_id not in typed_note_ids]
        submissions = []
        for ident, owner, raw in c.execute("SELECT id,canonical_opportunity_id,body FROM applications ORDER BY id"):
            body = json.loads(raw)
            explicit = owner or body.get("opportunity_id")
            submissions.append({"submission_id": ident, "opportunity_id": explicit,
                                "timeline_eligible": explicit in opportunities})
    return {"typed_communications": rows, "note_only_ids": note_only,
            "duplicate_raw_note_links": duplicate_links, "submission_timeline_candidates": submissions,
            "migration_gates": gates, "demo_legacy_findings": demo_legacy}


def dry_run(data_dir):
    root = Path(data_dir).expanduser().resolve()
    report = inventory(root)
    report.pop("observed_at", None)
    if report["snapshot"]["schema_version"] != 3:
        raise Invalid("需要schema v3源副本")
    if report["integrity"] != ["ok"] or report["integrity_issues"] or report["foreign_key_violations"]:
        raise Invalid("源完整性未通过")
    return {"migration_id": MIGRATION_ID, "source_snapshot_sha256": report["snapshot_sha256"],
            "source_schema_version": 3, "classification": _classify(root), "inventory": report}


def apply_migration(data_dir, plan, fault=lambda point: None):
    root = isolated_root(data_dir)
    if (root / "artifacts").is_symlink():
        raise Invalid("附件目录不能是链接")
    fingerprint = digest(plan)
    with sqlite3.connect(root / "workspace.sqlite3") as c:
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("BEGIN IMMEDIATE")
        saved = c.execute("SELECT body FROM records WHERE id=? AND kind='communication_migration'", (MIGRATION_ID,)).fetchone()
        if saved:
            saved = json.loads(saved[0])
            if saved["fingerprint"] != fingerprint:
                raise Conflict("迁移输入已变化")
            if c.execute("PRAGMA user_version").fetchone()[0] != 4:
                raise Invalid("迁移标记/schema不一致")
            return saved["result"]
        actual = dry_run(root)
        if actual != plan:
            raise Conflict("源数据/计划已变化，请重新dry-run")
        if actual["classification"]["migration_gates"]:
            raise Invalid("存在未解决的Communication归属/重复Gate")
        result = {"schema_version": 4,
                  "typed_communications": len(actual["classification"]["typed_communications"]),
                  "note_only_deferred": len(actual["classification"]["note_only_ids"]),
                  "rewritten_communications": 0}
        record = {"id": MIGRATION_ID, "fingerprint": fingerprint, "plan": plan,
                  "result": result, "created_at": now()}
        c.execute("INSERT INTO records VALUES(?,?,?)", (MIGRATION_ID, "communication_migration", dump(record)))
        fault("after_manifest")
        c.execute("PRAGMA user_version=4")
        if c.execute("PRAGMA foreign_key_check").fetchall():
            raise Invalid("迁移FK检查失败")
        fault("before_commit")
    return result


def verify_migration(data_dir):
    root = Path(data_dir).expanduser().resolve()
    report = inventory(root)
    with sqlite3.connect((root / "workspace.sqlite3").as_uri() + "?mode=ro", uri=True) as c:
        row = c.execute("SELECT body FROM records WHERE id=? AND kind='communication_migration'", (MIGRATION_ID,)).fetchone()
        if not row:
            raise Invalid("没有D迁移标记")
        saved = json.loads(row[0])
        before = saved["plan"]["inventory"]["snapshot"]
        differences = []
        if digest(saved["plan"]) != saved["fingerprint"] or _hash(before) != saved["plan"]["source_snapshot_sha256"]:
            differences.append("manifest_hash")
        for table, hashes in before["row_hashes"].items():
            after = report["snapshot"]["row_hashes"][table]
            for identifier, value in hashes.items():
                if after.get(identifier) != value:
                    differences.append({"table": table, "id": identifier})
        if c.execute("SELECT count(*) FROM records WHERE kind='timeline_event'").fetchone()[0]:
            differences.append("timeline_facts_created")
    if report["snapshot"]["artifact_files"] != before["artifact_files"]:
        differences.append("artifact_bytes")
    if report["snapshot"]["schema_version"] != 4:
        differences.append("schema_version")
    differences += report["integrity_issues"] + report["foreign_key_violations"]
    return {"verified": not differences and report["integrity"] == ["ok"],
            "differences": differences, "schema_version": 4,
            "table_counts": report["snapshot"]["table_counts"],
            "snapshot_sha256": report["snapshot_sha256"],
            "rewritten_communications": saved["result"]["rewritten_communications"]}
