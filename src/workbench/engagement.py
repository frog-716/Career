"""Typed Opportunity activity built on immutable journey_note raw records."""

import json

from fastapi import APIRouter

from .core import Conflict, Invalid, Missing, digest, now, required, uid


TYPED = {
    "research": "research_snapshot",
    "communication": "communication",
    "interview": "interview",
    "offer": "offer",
}


def _text(value, field, limit=100000):
    return required(value, field, limit)


def _opportunity(store, c, value):
    value = required(value, "机会", 500)
    if value.startswith("opportunity:"):
        opportunity = store._get(c, value, "opportunity")
        return value, opportunity["legacy_job_id"]
    store._get(c, value, "job")
    return "opportunity:" + value, value


def _opportunities(store, c, values):
    if not isinstance(values, list) or not values:
        raise Invalid("研究至少需要一个机会")
    result = []
    jobs = []
    for value in values:
        opportunity, job = _opportunity(store, c, value)
        if opportunity not in result:
            result.append(opportunity)
            jobs.append(job)
    return result, jobs


def _request(store, c, key, action, payload):
    key = required(key, "请求标识", 200)
    fingerprint = digest({"action": action, "payload": payload})
    row = c.execute(
        "SELECT body FROM records WHERE kind='engagement_request' AND json_extract(body,'$.key')=?",
        (key,),
    ).fetchone()
    if row:
        old = json.loads(row[0])
        if old["fingerprint"] != fingerprint:
            raise Conflict("请求标识已用于不同活动记录")
        return old["result"], key, fingerprint
    return None, key, fingerprint


def _remember(store, c, key, fingerprint, result):
    store._record(c, "engagement_request", {
        "id": uid(), "key": key, "fingerprint": fingerprint,
        "result": result, "created_at": now(),
    })


def _raw(store, c, body, kind, job_id, submission_id=None):
    note = dict(id=uid(), scope_type="job", scope_id=job_id, kind=kind,
                title=body.get("title", ""), content=_text(body.get("content"), "原文"),
                submission_id=submission_id, idempotency_key=body["idempotency_key"],
                created_at=now())
    store._record(c, "journey_note", note)
    return note


def create_activity(store, c, kind, body):
    if kind not in TYPED:
        raise Invalid("活动类型不支持")
    title = body.get("title", "")
    if not isinstance(title, str) or len(title) > 500:
        raise Invalid("标题超出长度限制")
    key = required(body.get("idempotency_key"), "请求标识", 200)
    raw_note = body.get("_raw_note")
    payload = {key: value for key, value in body.items() if key != "_raw_note"}
    payload["kind"] = kind
    previous, key, fingerprint = _request(store, c, key, "create_" + kind, payload)
    if previous is not None:
        return previous

    if kind == "research":
        requested = body.get("opportunity_ids")
        if requested is None and raw_note:
            requested = [raw_note["scope_id"]]
        opportunity_ids, jobs = _opportunities(store, c, requested)
        note = raw_note or _raw(store, c, body, kind, jobs[0])
        typed = dict(id=uid(), captured_at=_text(body.get("captured_at", note["created_at"]), "采集时间", 100),
                     source_locator=body.get("source_locator", ""), content=note["content"],
                     opportunity_ids=opportunity_ids, raw_note_id=note["id"], created_at=note["created_at"])
    else:
        requested = body.get("opportunity_id")
        if requested is None and raw_note:
            requested = raw_note["scope_id"]
        opportunity_id, job_id = _opportunity(store, c, requested)
        submission_id = body.get("submission_id")
        if kind == "interview" and submission_id:
            row = c.execute("SELECT body FROM applications WHERE id=?", (submission_id,)).fetchone()
            if not row:
                raise Missing("投递不存在")
            if json.loads(row[0]).get("job_id") != job_id:
                raise Invalid("面试投递与机会不匹配")
        note = raw_note or _raw(store, c, body, kind, job_id, submission_id)
        if kind == "communication":
            typed = dict(id=uid(), opportunity_id=opportunity_id,
                         occurred_at=_text(body.get("occurred_at", note["created_at"]), "发生时间", 100),
                         channel=body.get("channel", ""), participants=body.get("participants", []),
                         raw_note_id=note["id"], outcome=body.get("outcome", ""), created_at=note["created_at"])
        elif kind == "interview":
            typed = dict(id=uid(), opportunity_id=opportunity_id, submission_id=submission_id,
                         round=body.get("round", ""),
                         occurred_at=_text(body.get("occurred_at", note["created_at"]), "发生时间", 100),
                         participants=body.get("participants", []), raw_note_id=note["id"],
                         outcome=body.get("outcome", ""), created_at=note["created_at"])
        else:
            typed = dict(id=uid(), opportunity_id=opportunity_id,
                         occurred_at=_text(body.get("occurred_at", note["created_at"]), "发生时间", 100),
                         raw_note_id=note["id"], terms=body.get("terms", {}),
                         status=body.get("status", "pending"), created_at=note["created_at"])
    store._record(c, TYPED[kind], typed)
    result = dict(typed, raw_note=note)
    _remember(store, c, key, fingerprint, result)
    return result


def _legacy_projection(store, c, note):
    """Read-only typed shape for historical notes without creating records."""
    opportunity_id = "opportunity:" + note["scope_id"]
    base = {"id": "legacy:" + note["id"], "opportunity_id": opportunity_id,
            "raw_note_id": note["id"], "content": note["content"],
            "created_at": note["created_at"], "legacy": True}
    if note["kind"] == "research":
        return "research_snapshots", dict(base, captured_at=note["created_at"], source_locator="",
                                           opportunity_ids=[opportunity_id])
    if note["kind"] == "communication":
        return "communications", dict(base, occurred_at=note["created_at"], channel="", participants=[], outcome="")
    if note["kind"] == "interview":
        return "interviews", dict(base, occurred_at=note["created_at"], submission_id=note.get("submission_id"), round="", participants=[], outcome="")
    return "offers", dict(base, occurred_at=note["created_at"], terms={}, status="unknown")


def activity_view(store, c):
    result = {"research_snapshots": store._records(c, "research_snapshot"),
              "communications": store._records(c, "communication"),
              "interviews": store._records(c, "interview"),
              "offers": store._records(c, "offer"), "legacy_projections": []}
    typed_raw = {item.get("raw_note_id") for values in result.values() for item in values if isinstance(item, dict)}
    for note in store._records(c, "journey_note"):
        if note.get("scope_type") == "job" and note.get("kind") in TYPED and note["id"] not in typed_raw:
            bucket, projection = _legacy_projection(store, c, note)
            projection["activity_type"] = bucket[:-1]
            result["legacy_projections"].append(projection)
    return result


def engagement_router(store):
    router = APIRouter()

    @router.get("/api/opportunity-activity")
    def read_activity():
        with store.connect(False) as c:
            return activity_view(store, c)

    @router.get("/api/opportunity-activity/{kind}")
    def read_kind(kind: str):
        if kind not in TYPED:
            raise Invalid("活动类型不支持")
        with store.connect(False) as c:
            return store._records(c, TYPED[kind])

    for kind in TYPED:
        @router.post("/api/opportunity-activity/" + kind)
        def create(body: dict, _kind=kind):
            with store.connect() as c:
                return create_activity(store, c, _kind, body)

    return router
