"""Schema v5→v6 is only a runtime fence and rewrites no business object."""
import json
import sqlite3

import pytest

from workbench.core import Conflict, Invalid, Store
from workbench.offer_migration import MIGRATION_ID, apply_migration, dry_run, verify_migration
from workbench.opportunity import create_opportunity
from workbench.providers import TestProvider


def v5_fixture(path):
    store = Store(path, TestProvider())
    opportunity = create_opportunity(store, {
        "company_name": "虚构迁移公司", "title": "虚构岗位", "jd": "虚构 JD",
        "idempotency_key": "v6-fixture-opportunity",
    })
    with store.connect() as connection:
        store._record(connection, "offer", {
            "id": "offer:synthetic", "offer_format": 2,
            "opportunity_id": opportunity["id"], "received_on": "2026-09-18",
            "terms": {"offered_role_title": "明确岗位", "location": "", "start_date": None,
                      "employment_type": "", "probation": "", "benefits": "",
                      "compensation": {"guaranteed_cash": "", "variable_cash": "", "equity": "",
                                       "one_time": "", "notes": ""}, "other_terms": ""},
            "revision": 1,
        })
    with sqlite3.connect(store.db) as connection:
        connection.execute("PRAGMA user_version=5")
    return path


def business_rows(path):
    with sqlite3.connect(path / "workspace.sqlite3") as connection:
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in ("meta", "current", "applications", "revisions")
        } | {
            "records": connection.execute(
                "SELECT * FROM records WHERE id<>? ORDER BY 1", (MIGRATION_ID,)
            ).fetchall()
        }


def test_v6_fence_rewrites_no_business_rows_and_f_runtime_requires_v6(tmp_path):
    root = v5_fixture(tmp_path / "isolated-v5")
    before = business_rows(root)
    with pytest.raises(Invalid, match="schema v6"):
        Store(root, TestProvider())
    plan = dry_run(root)
    assert plan["business_rewrite"] is False
    result = apply_migration(root, plan)
    assert result == {"schema_version": 6, "rewritten_business_rows": 0,
                      "added_constraints": [], "runtime_fence": "batch-f-v6"}
    assert apply_migration(root, plan) == result
    verified = verify_migration(root)
    assert verified["verified"] is True and verified["differences"] == []
    assert business_rows(root) == before
    assert Store(root, TestProvider()).state()["diagnostics"]["schema_version"] == 6


def test_source_change_and_fault_rollback_leave_v5_intact(tmp_path):
    changed = v5_fixture(tmp_path / "changed")
    plan = dry_run(changed)
    with sqlite3.connect(changed / "workspace.sqlite3") as connection:
        raw = json.loads(connection.execute(
            "SELECT body FROM records WHERE id='offer:synthetic'"
        ).fetchone()[0])
        raw["terms"]["location"] = "源已变化"
        connection.execute("UPDATE records SET body=? WHERE id='offer:synthetic'", (json.dumps(raw),))
    with pytest.raises(Conflict):
        apply_migration(changed, plan)

    faulted = v5_fixture(tmp_path / "faulted")
    before = business_rows(faulted)
    plan = dry_run(faulted)
    with pytest.raises(RuntimeError):
        apply_migration(
            faulted, plan,
            lambda point: (_ for _ in ()).throw(RuntimeError(point)) if point == "before_commit" else None,
        )
    with sqlite3.connect(faulted / "workspace.sqlite3") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
        assert connection.execute(
            "SELECT count(*) FROM records WHERE id=?", (MIGRATION_ID,)
        ).fetchone()[0] == 0
    assert business_rows(faulted) == before
