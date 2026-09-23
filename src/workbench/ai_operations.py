"""Persistent local deduplication and conservative recovery for AI calls."""
import json
from dataclasses import dataclass

from fastapi.responses import JSONResponse

from .core import Conflict, Invalid, Missing, digest, now, uid


RUNNING_STATES = {"reserved", "dispatching"}
_VOLATILE_RESULTS = {}


class AIValidationError(Exception):
    """The provider returned, but the result failed local validation."""

    def __init__(self, message, code="invalid_result"):
        self.code = code
        super().__init__(message)


class PreDispatchFailure(Invalid):
    """A remote precondition failed before the model request was sent."""


@dataclass
class Execution:
    state: str
    operation: dict
    value: object = None
    replay: bool = False


def _row(row):
    if row is None:
        return None
    keys = (
        "op_id", "task_type", "target_kind", "target_id", "idempotency_key",
        "client_intent_hash", "dispatched_payload_hash", "manifest", "state",
        "dispatch_marker", "result_ref", "error_code", "error_message",
        "created_at", "reserved_at", "dispatched_at", "finished_at",
    )
    result = dict(zip(keys, row))
    for key in ("manifest", "result_ref"):
        result[key] = json.loads(result[key]) if result[key] else None
    return result


def _select(c, task_type, target_kind, target_id, key):
    return _row(c.execute(
        """SELECT op_id,task_type,target_kind,target_id,idempotency_key,
                  client_intent_hash,dispatched_payload_hash,manifest,state,
                  dispatch_marker,result_ref,error_code,error_message,created_at,
                  reserved_at,dispatched_at,finished_at
             FROM ai_operations
            WHERE task_type=? AND target_kind=? AND target_id=? AND idempotency_key=?""",
        (task_type, target_kind, target_id, key),
    ).fetchone())


def _by_id(c, op_id):
    return _row(c.execute(
        """SELECT op_id,task_type,target_kind,target_id,idempotency_key,
                  client_intent_hash,dispatched_payload_hash,manifest,state,
                  dispatch_marker,result_ref,error_code,error_message,created_at,
                  reserved_at,dispatched_at,finished_at
             FROM ai_operations WHERE op_id=?""",
        (op_id,),
    ).fetchone())


def _public(row):
    status = "running" if row["state"] in RUNNING_STATES else row["state"]
    return {
        "operation_id": row["op_id"],
        "status": status,
        "state": row["state"],
        "task_type": row["task_type"],
        "target_kind": row["target_kind"],
        "target_id": row["target_id"],
        "error_code": row["error_code"],
        "created_at": row["created_at"],
        "dispatched_at": row["dispatched_at"],
        "finished_at": row["finished_at"],
    }


def _current(store, op_id):
    with store.connect(False) as c:
        return _by_id(c, op_id)


def _add_operation_id(value, op_id):
    if isinstance(value, dict):
        result = dict(value)
        result.setdefault("operation_id", op_id)
        return result
    return value


def _load_value(store, row):
    if row["op_id"] in _VOLATILE_RESULTS:
        return _add_operation_id(_VOLATILE_RESULTS[row["op_id"]], row["op_id"])
    if not row.get("result_ref"):
        raise Missing("result_expired: AI 操作结果已不可用")
    with store.connect(False) as c:
        saved = store._get(c, row["result_ref"]["id"], "ai_operation_result", True)
    return _add_operation_id(saved["value"], row["op_id"])


def _existing(store, row, intent_hash):
    if row["client_intent_hash"] != intent_hash:
        raise Conflict("请求标识已用于不同 AI 操作")
    if row["state"] == "succeeded":
        try:
            return Execution("succeeded", row, _load_value(store, row), True)
        except Missing:
            return Execution("outcome_unknown", dict(row, error_code="result_expired"), None, True)
    if row["state"] in RUNNING_STATES:
        return Execution("running", row, None, True)
    if row["state"] == "outcome_unknown":
        return Execution("outcome_unknown", row, None, True)
    return Execution("failed", row, None, True)


def claim_dispatch_slot(store, op_id):
    """Claim the single outbound slot atomically across local processes."""
    with store.connect() as c:
        row = c.execute(
            "SELECT holder_op_id FROM ai_dispatch_slot WHERE slot_id=1"
        ).fetchone()
        if row and row[0] is not None:
            return False
        c.execute(
            "UPDATE ai_dispatch_slot SET holder_op_id=?,acquired_at=? WHERE slot_id=1 AND holder_op_id IS NULL",
            (op_id, now()),
        )
        return c.execute(
            "SELECT holder_op_id FROM ai_dispatch_slot WHERE slot_id=1"
        ).fetchone()[0] == op_id


def release_dispatch_slot(store, op_id):
    with store.connect() as c:
        c.execute(
            "UPDATE ai_dispatch_slot SET holder_op_id=NULL,acquired_at=NULL WHERE slot_id=1 AND holder_op_id=?",
            (op_id,),
        )


def _new_operation(store, task_type, target_kind, target_id, key, intent_hash):
    with store.connect() as c:
        previous = _select(c, task_type, target_kind, target_id, key)
        if previous:
            return previous, True
        op_id = "ai-operation:" + uid()
        timestamp = now()
        c.execute(
            """INSERT INTO ai_operations(
                    op_id,task_type,target_kind,target_id,idempotency_key,
                    client_intent_hash,state,created_at,reserved_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
            (op_id, task_type, target_kind, target_id, key, intent_hash,
             "reserved", timestamp, timestamp),
        )
        return _select(c, task_type, target_kind, target_id, key), False


def find(store, task_type, target_kind, target_id, key):
    with store.connect(False) as c:
        return _select(c, task_type, target_kind, target_id, key)


def _update(store, op_id, **values):
    if not values:
        return
    columns = []
    params = []
    for key, value in values.items():
        columns.append(key + "=?")
        if key in {"manifest", "result_ref"} and value is not None:
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        params.append(value)
    params.append(op_id)
    with store.connect() as c:
        c.execute("UPDATE ai_operations SET " + ",".join(columns) + " WHERE op_id=?", params)


def bind_dispatch(store, op_id, payload_hash, manifest=None):
    """Bind the final request immediately before the provider call."""
    with store.connect() as c:
        row = _by_id(c, op_id)
        if not row or row["state"] != "dispatching":
            raise Conflict("ai_operation_not_dispatching: AI 操作不允许发送")
        values = [payload_hash]
        assignments = ["dispatched_payload_hash=?"]
        if manifest is not None:
            assignments.append("manifest=?")
            values.append(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        values.append(op_id)
        c.execute("UPDATE ai_operations SET " + ",".join(assignments) + " WHERE op_id=?", values)
        row = _by_id(c, op_id)
    _safe_audit(store, row, "dispatched", payload_hash=payload_hash)


def _manifest_refs(manifest):
    if not isinstance(manifest, dict):
        return []
    return [
        {key: dependency[key] for key in ("id", "revision", "purpose") if key in dependency}
        for dependency in manifest.get("dependencies", [])
    ]


def _safe_audit(store, row, event, *, payload_hash=None, details=None):
    try:
        from . import outbound_policy
        outbound_policy.audit(
            store, task_type=row["task_type"],
            target={"kind": row["target_kind"], "id": row["target_id"]},
            event=event, operation_id=row["op_id"], payload_hash=payload_hash or row.get("dispatched_payload_hash"),
            source_refs_value=_manifest_refs(row.get("manifest")), details=details,
        )
    except Exception:
        # Audit persistence is not allowed to turn a completed provider call
        # into an automatic retry.  The durable operation state remains the
        # source of truth for recovery.
        return


def _mark_failure(store, op_id, state, code, message):
    try:
        _update(store, op_id, state=state, error_code=code, error_message=message,
                finished_at=now())
    except Exception:
        # The dispatch marker remains durable; restart recovery will classify it.
        pass


def _error_code(exc):
    return getattr(exc, "code", None) or exc.__class__.__name__


def _definitely_not_sent(exc):
    return isinstance(exc, (Invalid, PreDispatchFailure)) or _error_code(exc) in {"not_configured", "invalid_input"}


def _response(execution):
    row = execution.operation
    public = _public(row)
    if execution.state == "outcome_unknown":
        public["status"] = "outcome_unknown"
        public["state"] = "outcome_unknown"
    if execution.state == "running":
        return JSONResponse(public, status_code=202)
    if execution.state == "outcome_unknown":
        public["message"] = "外部结果可能已经产生，Career 不会自动重复调用；请查看已有结果或明确重新生成。"
        return JSONResponse(public, status_code=409)
    public["message"] = row.get("error_message") or "AI 操作失败；请使用新的请求标识明确重试。"
    return JSONResponse(public, status_code=429 if row.get("error_code") == "busy" else 503)


def unwrap(execution):
    return execution.value if execution.state == "succeeded" else _response(execution)


def require_success(execution):
    if execution.state != "succeeded":
        raise Conflict("ai_operation_" + execution.state + ": 请查看已有 AI 操作状态")
    return execution.value


def execute(store, *, task_type, target_kind, target_id, idempotency_key,
            client_intent, prepare, dispatch, persist, retain_result=True):
    """Reserve before context/provider work, then conservatively finalize once."""
    intent_hash = digest(client_intent)
    row, existed = _new_operation(
        store, task_type, target_kind, target_id, idempotency_key, intent_hash
    )
    if existed:
        return _existing(store, row, intent_hash)

    dispatch_started = False
    try:
        prepared = prepare()
        if not isinstance(prepared, dict):
            raise Invalid("AI 操作准备结果不合法")
        replay_value = prepared.pop("_replay_value", None)
        replay_expired = prepared.pop("_replay_expired", False)
        if replay_expired:
            _mark_failure(store, row["op_id"], "failed", "result_expired", "已有建议正文已过期，不能用旧 key 重新生成")
            raise Conflict("result_expired: 已有建议正文已过期，请明确重新生成")
        if replay_value is not None:
            _VOLATILE_RESULTS[row["op_id"]] = replay_value
            with store.connect() as c:
                result_id = "ai-result:" + row["op_id"]
                if retain_result:
                    store._record(c, "ai_operation_result", {"id": result_id, "operation_id": row["op_id"], "value": replay_value})
                c.execute(
                    "UPDATE ai_operations SET state='succeeded',result_ref=?,finished_at=? WHERE op_id=? AND state='reserved'",
                    (json.dumps({"kind": "ai_operation_result", "id": result_id}, ensure_ascii=False) if retain_result else None, now(), row["op_id"]),
                )
            with store.connect(False) as c:
                finished = _by_id(c, row["op_id"])
            return Execution("succeeded", finished, _add_operation_id(replay_value, row["op_id"]), False)

        manifest = prepared.get("manifest")
        # Domain dispatchers pass this opaque operation id to the gateway so
        # phase audit rows can be linked without persisting raw request data.
        prepared["_operation_id"] = row["op_id"]
        with store.connect() as c:
            c.execute(
                """UPDATE ai_operations
                      SET manifest=?,state='dispatching',dispatch_marker=?,dispatched_at=?
                    WHERE op_id=? AND state='reserved'""",
                (json.dumps(manifest, ensure_ascii=False, sort_keys=True) if manifest is not None else None,
                uid(), now(), row["op_id"]),
            )
        dispatch_started = True
        def binder(payload_hash, bound_manifest=None):
            bind_dispatch(store, row["op_id"], payload_hash, bound_manifest)
        if not claim_dispatch_slot(store, row["op_id"]):
            _mark_failure(store, row["op_id"], "failed", "busy", "AI 出站额度已占用，请使用新的请求标识重试")
            finished = _current(store, row["op_id"])
            return Execution("failed", finished, None, False)
        try:
            result, diagnostics = dispatch(prepared, binder)
        finally:
            release_dispatch_slot(store, row["op_id"])
    except Exception as exc:
        current_state = "outcome_unknown" if dispatch_started and not _definitely_not_sent(exc) else "failed"
        _mark_failure(store, row["op_id"], current_state, _error_code(exc), str(exc))
        raise

    try:
        value = persist(prepared, result, diagnostics)
    except AIValidationError as exc:
        _mark_failure(store, row["op_id"], "failed", exc.code, str(exc))
        error = Invalid(str(exc))
        error.code = exc.code
        raise error from exc
    except Exception as exc:
        _mark_failure(store, row["op_id"], "outcome_unknown", "persistence_unknown", str(exc))
        raise

    current_after_provider = _current(store, row["op_id"])
    _safe_audit(store, current_after_provider, "schema_validated")
    _safe_audit(store, current_after_provider, "domain_validated")
    if task_type in {"resume_optimization", "research_update", "interview_final_review", "interview_research_patch"}:
        _safe_audit(store, current_after_provider, "proposal_created")

    try:
        with store.connect() as c:
            current = _by_id(c, row["op_id"])
            if current["state"] != "dispatching":
                raise Conflict("ai_operation_state_changed: AI 操作状态已变化")
            result_id = "ai-result:" + row["op_id"]
            _VOLATILE_RESULTS[row["op_id"]] = value
            if retain_result:
                store._record(c, "ai_operation_result", {
                    "id": result_id, "operation_id": row["op_id"], "value": value,
                })
            c.execute(
                "UPDATE ai_operations SET state='succeeded',result_ref=?,finished_at=? WHERE op_id=? AND state='dispatching'",
                (json.dumps({"kind": "ai_operation_result", "id": result_id}, ensure_ascii=False) if retain_result else None, now(), row["op_id"]),
            )
            finished = _by_id(c, row["op_id"])
        return Execution("succeeded", finished, _add_operation_id(value, row["op_id"]), False)
    except Exception as exc:
        _mark_failure(store, row["op_id"], "outcome_unknown", "persistence_unknown", str(exc))
        raise


def recover(c):
    """Never resend work after a process stopped around a provider call."""
    rows = c.execute("SELECT op_id,state FROM ai_operations WHERE state IN ('reserved','dispatching')").fetchall()
    for op_id, state in rows:
        if state == "dispatching":
            c.execute(
                "UPDATE ai_operations SET state='outcome_unknown',error_code='process_interrupted',error_message=?,finished_at=? WHERE op_id=?",
                ("进程在外部调用附近中断，结果未知；不会自动重试", now(), op_id),
            )
        else:
            c.execute(
                "UPDATE ai_operations SET state='failed',error_code='process_interrupted_before_dispatch',error_message=?,finished_at=? WHERE op_id=?",
                ("进程在发送前中断，确认未调用供应商", now(), op_id),
            )
    c.execute(
        """UPDATE ai_dispatch_slot
              SET holder_op_id=NULL,acquired_at=NULL
            WHERE slot_id=1 AND (holder_op_id IS NULL OR holder_op_id NOT IN
                (SELECT op_id FROM ai_operations WHERE state='dispatching'))"""
    )


def list_operations(store):
    with store.connect(False) as c:
        rows = c.execute("SELECT op_id FROM ai_operations ORDER BY rowid DESC").fetchall()
        return [_public(_by_id(c, row[0])) for row in rows]
