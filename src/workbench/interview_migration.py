"""Hash-bound schema v4→v5 semantic write fence for Interview."""
import json
import sqlite3
from pathlib import Path

from .core import Conflict, Invalid, digest, dump, now
from .migration_baseline import _hash, inventory
from .opportunity import canonical_id
from .opportunity_migration import isolated_root


MIGRATION_ID = "migration:interview-v5"
INDEXES = {
    "interview_preparation_owner": "CREATE UNIQUE INDEX interview_preparation_owner ON records(json_extract(body,'$.interview_session_id')) WHERE kind='interview_preparation'",
    "interview_raw_owner": "CREATE UNIQUE INDEX interview_raw_owner ON records(json_extract(body,'$.interview_session_id')) WHERE kind='interview_raw'",
    "interview_review_owner": "CREATE UNIQUE INDEX interview_review_owner ON records(json_extract(body,'$.interview_session_id')) WHERE kind='interview_final_review'",
    "opportunity_research_owner": "CREATE UNIQUE INDEX opportunity_research_owner ON current(json_extract(body,'$.opportunity_id')) WHERE kind='opportunity_research'",
}


def _classify(root):
    with sqlite3.connect((root / "workspace.sqlite3").as_uri() + "?mode=ro", uri=True) as c:
        opportunities = {row[0] for row in c.execute(
            "SELECT id FROM current WHERE kind='opportunity' AND json_extract(body,'$.format_version')=2"
        )}
        jobs = {row[0]: json.loads(row[1]) for row in c.execute(
            "SELECT id,body FROM current WHERE kind='job'"
        )}
        notes = {row[0]: json.loads(row[1]) for row in c.execute(
            "SELECT id,body FROM records WHERE kind='journey_note'"
        )}
        interviews = [json.loads(row[0]) for row in c.execute(
            "SELECT body FROM records WHERE kind='interview' ORDER BY id"
        )]
        interview_by_id = {item["id"]: item for item in interviews}
        note_links = {}
        rows, gates, demo_legacy = [], [], []
        for item in interviews:
            note_id = item.get("raw_note_id")
            if note_id:
                note_links.setdefault(note_id, []).append(item["id"])
            owner = item.get("opportunity_id")
            canonical_owner = canonical_id(owner) if isinstance(owner, str) and owner else None
            alias = canonical_owner.split(":", 1)[1] if canonical_owner and ":" in canonical_owner else None
            owner_known = canonical_owner in opportunities
            legacy_owner = alias in jobs
            is_demo = bool(legacy_owner and jobs[alias].get("demo_dataset_id"))
            current = item.get("interview_format") == 2
            unknown = []
            if not current:
                unknown.extend(["type", "status", "confirmed_on"])
                if not item.get("round"):
                    unknown.append("name")
            row = {
                "interview_id": item["id"], "format": 2 if current else "legacy",
                "opportunity_id": canonical_owner, "owner_known": owner_known,
                "legacy_owner_readable": legacy_owner, "demo_legacy": is_demo,
                "raw_note_id": note_id,
                "raw_note_state": "present" if note_id in notes else ("missing" if note_id else "none"),
                "unknown": unknown,
            }
            rows.append(row)
            if not owner_known and not legacy_owner:
                gates.append({"code": "interview_owner_unknown", "interview_id": item["id"],
                              "opportunity_id": canonical_owner})
            if current:
                if item.get("type") not in {"real", "simulation"}:
                    gates.append({"code": "invalid_interview_type", "interview_id": item["id"]})
                if item.get("type") == "simulation" and not item.get("target_real_interview_id"):
                    gates.append({"code": "simulation_parent_missing", "interview_id": item["id"]})
        duplicate_links = [{"raw_note_id": note_id, "interview_ids": ids}
                           for note_id, ids in sorted(note_links.items()) if len(ids) > 1]
        for duplicate in duplicate_links:
            linked = [row for row in rows if row.get("raw_note_id") == duplicate["raw_note_id"]]
            finding = {"code": "multiple_typed_interviews_for_note", **duplicate}
            (demo_legacy if linked and all(row["demo_legacy"] for row in linked) else gates).append(finding)
        typed_note_ids = set(note_links)
        note_only = [note_id for note_id, note in notes.items()
                     if note.get("scope_type") == "job" and note.get("kind") == "interview"
                     and note_id not in typed_note_ids]
        proposals = [json.loads(row[0]) for row in c.execute(
            "SELECT body FROM records WHERE kind='patch_proposal'"
        )]
        invalid_proposals = [proposal["id"] for proposal in proposals
                             if proposal.get("origin_interview_type") != "real"
                             or interview_by_id.get(proposal.get("origin_interview_id"), {}).get("type") != "real"
                             or interview_by_id.get(proposal.get("origin_interview_id"), {}).get("interview_format") != 2]
        if invalid_proposals:
            gates.append({"code": "simulation_or_unknown_patch_proposal",
                          "proposal_ids": invalid_proposals})
    return {
        "typed_interviews": rows, "note_only_ids": note_only,
        "duplicate_raw_note_links": duplicate_links,
        "invalid_patch_proposal_ids": invalid_proposals,
        "migration_gates": gates, "demo_legacy_findings": demo_legacy,
    }


def dry_run(data_dir):
    root = Path(data_dir).expanduser().resolve()
    report = inventory(root)
    report.pop("observed_at", None)
    if report["snapshot"]["schema_version"] != 4:
        raise Invalid("需要schema v4源副本")
    if report["integrity"] != ["ok"] or report["integrity_issues"] or report["foreign_key_violations"]:
        raise Invalid("源完整性未通过")
    return {"migration_id": MIGRATION_ID, "source_snapshot_sha256": report["snapshot_sha256"],
            "source_schema_version": 4, "classification": _classify(root), "inventory": report}


def apply_migration(data_dir, plan, fault=lambda point: None):
    root = isolated_root(data_dir)
    if (root / "artifacts").is_symlink():
        raise Invalid("附件目录不能是链接")
    fingerprint = digest(plan)
    with sqlite3.connect(root / "workspace.sqlite3") as c:
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("BEGIN IMMEDIATE")
        saved = c.execute(
            "SELECT body FROM records WHERE id=? AND kind='interview_migration'", (MIGRATION_ID,)
        ).fetchone()
        if saved:
            saved = json.loads(saved[0])
            if saved["fingerprint"] != fingerprint:
                raise Conflict("迁移输入已变化")
            if c.execute("PRAGMA user_version").fetchone()[0] != 5:
                raise Invalid("迁移标记/schema不一致")
            return saved["result"]
        actual = dry_run(root)
        if actual != plan:
            raise Conflict("源数据/计划已变化，请重新dry-run")
        if actual["classification"]["migration_gates"]:
            raise Invalid("存在未解决的 Interview 归属/关系 Gate")
        for statement in INDEXES.values():
            c.execute(statement)
        result = {
            "schema_version": 5,
            "typed_interviews": len(actual["classification"]["typed_interviews"]),
            "note_only_deferred": len(actual["classification"]["note_only_ids"]),
            "rewritten_interviews": 0, "indexes": sorted(INDEXES),
        }
        record = {"id": MIGRATION_ID, "fingerprint": fingerprint, "plan": plan,
                  "result": result, "created_at": now()}
        c.execute("INSERT INTO records VALUES(?,?,?)", (MIGRATION_ID, "interview_migration", dump(record)))
        fault("after_manifest")
        c.execute("PRAGMA user_version=5")
        if c.execute("PRAGMA foreign_key_check").fetchall():
            raise Invalid("迁移FK检查失败")
        fault("before_commit")
    return result


def verify_migration(data_dir):
    root = Path(data_dir).expanduser().resolve()
    report = inventory(root)
    with sqlite3.connect((root / "workspace.sqlite3").as_uri() + "?mode=ro", uri=True) as c:
        row = c.execute(
            "SELECT body FROM records WHERE id=? AND kind='interview_migration'", (MIGRATION_ID,)
        ).fetchone()
        if not row:
            raise Invalid("没有E迁移标记")
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
        existing_indexes = {row[0] for row in c.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )}
        for name in INDEXES:
            if name not in existing_indexes:
                differences.append({"missing_index": name})
        if c.execute("SELECT count(*) FROM records WHERE kind='timeline_event'").fetchone()[0]:
            differences.append("timeline_facts_created")
        proposals = [json.loads(row[0]) for row in c.execute(
            "SELECT body FROM records WHERE kind='patch_proposal'"
        )]
        interviews = {row[0]: json.loads(row[1]) for row in c.execute(
            "SELECT id,body FROM records WHERE kind='interview'"
        )}
        if any(proposal.get("origin_interview_type") != "real"
               or interviews.get(proposal.get("origin_interview_id"), {}).get("type") != "real"
               or interviews.get(proposal.get("origin_interview_id"), {}).get("interview_format") != 2
               for proposal in proposals):
            differences.append("simulation_patch_proposal")
    if report["snapshot"]["artifact_files"] != before["artifact_files"]:
        differences.append("artifact_bytes")
    if report["snapshot"]["schema_version"] != 5:
        differences.append("schema_version")
    differences += report["integrity_issues"] + report["foreign_key_violations"]
    return {"verified": not differences and report["integrity"] == ["ok"],
            "differences": differences, "schema_version": 5,
            "table_counts": report["snapshot"]["table_counts"],
            "snapshot_sha256": report["snapshot_sha256"],
            "rewritten_interviews": saved["result"]["rewritten_interviews"]}
