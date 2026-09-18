"""Schema v4→v5 is a semantic fence and never invents Interview facts."""
import json
import sqlite3

import pytest

from workbench.core import Conflict, Invalid, Store
from workbench.interview_migration import apply_migration, dry_run, verify_migration, INDEXES
from workbench.providers import TestProvider


def v4_fixture(path):
    store = Store(path, TestProvider())
    with store.connect() as connection:
        opportunity = connection.execute(
            "SELECT body FROM current WHERE kind='opportunity' LIMIT 1"
        ).fetchone()
        # A readable legacy Job owner: type/status/date must remain Unknown.
        store._save(connection, "job", {
            "id": "legacy-job", "company": "虚构历史公司", "title": "历史岗位",
            "jd": "虚构 JD", "url": "", "status": "active",
            "created_at": "2026-09-15T00:00:00+00:00",
        }, 0)
        store._record(connection, "interview", {
            "id": "legacy-interview", "opportunity_id": "opportunity:legacy-job",
            "round": "一面", "occurred_at": "2026-09-18T00:00:00+00:00",
            "created_at": "2026-09-18T00:00:00+00:00",
        })
    with sqlite3.connect(store.db) as connection:
        for name in INDEXES:
            connection.execute("DROP INDEX IF EXISTS " + name)
        connection.execute("PRAGMA user_version=4")
    return path


def test_migration_fences_v4_without_rewriting_legacy(tmp_path):
    root = v4_fixture(tmp_path / "isolated-v4")
    with pytest.raises(Invalid):
        Store(root, TestProvider())
    plan = dry_run(root)
    legacy = plan["classification"]["typed_interviews"][0]
    assert legacy["format"] == "legacy"
    assert set(legacy["unknown"]) >= {"type", "status", "confirmed_on"}
    with sqlite3.connect(root / "workspace.sqlite3") as connection:
        before = connection.execute("SELECT body FROM records WHERE id='legacy-interview'").fetchone()[0]
    result = apply_migration(root, plan)
    assert result["schema_version"] == 5 and result["rewritten_interviews"] == 0
    assert apply_migration(root, plan) == result
    assert verify_migration(root)["verified"] is True
    with sqlite3.connect(root / "workspace.sqlite3") as connection:
        after = connection.execute("SELECT body FROM records WHERE id='legacy-interview'").fetchone()[0]
    assert after == before
    with sqlite3.connect(root / "workspace.sqlite3") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
    with pytest.raises(Invalid, match="schema v6"):
        Store(root, TestProvider())


def test_source_change_and_fault_rollback(tmp_path):
    changed = v4_fixture(tmp_path / "changed")
    plan = dry_run(changed)
    with sqlite3.connect(changed / "workspace.sqlite3") as connection:
        raw = json.loads(connection.execute(
            "SELECT body FROM records WHERE id='legacy-interview'"
        ).fetchone()[0])
        raw["round"] = "源已变化"
        connection.execute("UPDATE records SET body=? WHERE id='legacy-interview'", (json.dumps(raw),))
    with pytest.raises(Conflict):
        apply_migration(changed, plan)

    faulted = v4_fixture(tmp_path / "faulted")
    plan = dry_run(faulted)
    with pytest.raises(RuntimeError):
        apply_migration(
            faulted, plan,
            lambda point: (_ for _ in ()).throw(RuntimeError(point)) if point == "before_commit" else None,
        )
    with sqlite3.connect(faulted / "workspace.sqlite3") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
        assert connection.execute("SELECT count(*) FROM records WHERE kind='interview_migration'").fetchone()[0] == 0
