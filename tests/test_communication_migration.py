"""Schema v3→v4 is a semantic write fence and does not rewrite legacy facts."""
import json
import sqlite3

import pytest

from workbench.communication_migration import apply_migration, dry_run, verify_migration
from workbench.core import Conflict, Invalid, Store, dump
from workbench.providers import TestProvider


def v3_fixture(path):
    store = Store(path, TestProvider())
    with store.connect() as connection:
        opportunity = {
            "id": "opportunity:synthetic", "format_version": 2, "legacy_job_id": None,
            "company_id": "company:synthetic", "title": "虚构岗位", "jd": "虚构JD", "url": "",
            "phase": "submitted", "result": "active", "created_on": "2026-09-17",
            "created_at": "2026-09-17T00:00:00+00:00", "phase_changed_on": "2026-09-17",
            "phase_source": {"action": "fixture"}, "result_changed_at": None, "revision": 0,
        }
        company = {"id": "company:synthetic", "kind": "company", "name": "虚构公司",
                   "match_key": "虚构公司", "description": "", "created_at": "2026-09-17T00:00:00+00:00", "revision": 0}
        connection.execute("INSERT INTO current VALUES(?,?,?,?)", (company["id"], "domain_company", 0, dump(company)))
        connection.execute("INSERT INTO current VALUES(?,?,?,?)", (opportunity["id"], "opportunity", 0, dump(opportunity)))
        store._record(connection, "communication", {
            "id": "legacy-communication", "opportunity_id": opportunity["id"],
            "occurred_at": "2026-09-18T00:00:00+00:00", "channel": "邮件",
            "participants": [], "outcome": "", "created_at": "2026-09-18T00:00:00+00:00",
        })
    with sqlite3.connect(store.db) as connection:
        connection.execute("PRAGMA user_version=3")
    return path


def test_migration_fences_runtime_without_rewriting(tmp_path):
    root = v3_fixture(tmp_path / "isolated-v3")
    with pytest.raises(Invalid):
        Store(root, TestProvider())
    plan = dry_run(root)
    assert plan["classification"]["typed_communications"][0]["format"] == "legacy"
    with sqlite3.connect(root / "workspace.sqlite3") as connection:
        before = connection.execute("SELECT body FROM records WHERE id='legacy-communication'").fetchone()[0]
    result = apply_migration(root, plan)
    assert result == {"schema_version": 4, "typed_communications": 1, "note_only_deferred": 0, "rewritten_communications": 0}
    assert apply_migration(root, plan) == result
    verified = verify_migration(root)
    assert verified["verified"] is True and verified["rewritten_communications"] == 0
    with sqlite3.connect(root / "workspace.sqlite3") as connection:
        after = connection.execute("SELECT body FROM records WHERE id='legacy-communication'").fetchone()[0]
    assert after == before
    with pytest.raises(Invalid):
        Store(root, TestProvider())


def test_source_change_and_fault_rollback(tmp_path):
    changed = v3_fixture(tmp_path / "changed")
    plan = dry_run(changed)
    with sqlite3.connect(changed / "workspace.sqlite3") as connection:
        raw = json.loads(connection.execute("SELECT body FROM records WHERE id='legacy-communication'").fetchone()[0])
        raw["outcome"] = "源已变化"
        connection.execute("UPDATE records SET body=? WHERE id='legacy-communication'", (dump(raw),))
    with pytest.raises(Conflict):
        apply_migration(changed, plan)

    faulted = v3_fixture(tmp_path / "faulted")
    plan = dry_run(faulted)
    with pytest.raises(RuntimeError):
        apply_migration(faulted, plan, lambda point: (_ for _ in ()).throw(RuntimeError(point)) if point == "before_commit" else None)
    with sqlite3.connect(faulted / "workspace.sqlite3") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert connection.execute("SELECT count(*) FROM records WHERE kind='communication_migration'").fetchone()[0] == 0
