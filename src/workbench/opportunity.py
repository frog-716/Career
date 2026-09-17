"""Canonical Opportunity view and compatibility mapping for legacy jobs."""

import json
from fastapi import APIRouter


def canonical_id(job_id):
    return "opportunity:" + job_id


def _context(store, connection, job_id):
    row = connection.execute(
        "SELECT body FROM current WHERE id=? AND kind='opportunity_context'",
        ("opportunity-context:" + job_id,),
    ).fetchone()
    return json.loads(row[0]) if row else None


def sync_job(store, connection, job):
    """Create/update the canonical opportunity in the same transaction as job."""
    oid = canonical_id(job["id"])
    row = connection.execute(
        "SELECT revision,body FROM current WHERE id=? AND kind='opportunity'", (oid,)
    ).fetchone()
    old = json.loads(row[1]) if row else {}
    expected = row[0] if row else 0
    obj = dict(old, id=oid, legacy_job_id=job["id"], company=job["company"],
               title=job["title"], jd=job["jd"], url=job.get("url", ""),
               status=job["status"], source=job.get("source", "manual"),
               created_at=job.get("created_at", old.get("created_at")))
    return store._save(connection, "opportunity", obj, expected)


def _view(store, connection, opportunity):
    return dict(opportunity, context=_context(store, connection, opportunity["legacy_job_id"]))


def current_opportunities(store, connection):
    """Read canonical rows and map pre-canonical legacy jobs without migration."""
    items = store._current(connection, "opportunity")
    seen = {item["legacy_job_id"] for item in items}
    for job in store._current(connection, "job"):
        if job["id"] in seen:
            continue
        items.append(dict(id=canonical_id(job["id"]), legacy_job_id=job["id"],
                          company=job["company"], title=job["title"], jd=job["jd"],
                          url=job.get("url", ""), status=job["status"],
                          source=job.get("source", "manual"), revision=job["revision"],
                          created_at=job.get("created_at"), context=_context(store, connection, job["id"])))
    return items


def router(store):
    api = APIRouter(prefix="/api/opportunities")

    @api.get("")
    def list_opportunities():
        with store.connect(False) as connection:
            return [item if "context" in item else _view(store, connection, item)
                    for item in current_opportunities(store, connection)]

    @api.post("")
    def create_opportunity(body: dict):
        return store.save_opportunity(body)

    @api.post("/{opportunity_id}")
    def update_opportunity(opportunity_id: str, body: dict):
        return store.save_opportunity(body, opportunity_id)

    return api
