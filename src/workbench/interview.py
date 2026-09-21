"""Canonical Interview vertical: real rounds, simulations, current materials and real-only research patches."""
import json
from datetime import date, datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .core import Conflict, Invalid, Missing, ProviderError, digest, now, required, uid
from . import opportunity as op
from . import ai_operations as ao
from . import context_manifest as cm
from . import research_store as rs
from . import outbound_policy as outbound
from .model_gateway import ModelGateway


REAL_STATUSES = {"pending", "scheduled", "completed", "cancelled"}
SIMULATION_STATUSES = {"pending", "completed", "cancelled"}
RESEARCH_CATEGORIES = rs.CATEGORIES
PREPARATION_FIELDS = ("focus", "expected_questions", "priority_projects", "risks", "notes")
REVIEW_FIELDS = ("summary", "key_qa", "patterns", "discoveries", "next_actions")


def _strict(body, allowed, label="Interview"):
    extra = set(body) - set(allowed)
    if extra:
        raise Invalid(label + " 不接受字段：" + ",".join(sorted(extra)))


def _expected(value):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Invalid("expected_revision 必须是非负整数")
    return value


def _day(value, field, optional=False):
    if optional and value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) != 10:
        raise Invalid(field + "必须是 YYYY-MM-DD")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise Invalid(field + "必须是 YYYY-MM-DD") from None


def _timestamp(value, scheduled_on):
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 100:
        raise Invalid("scheduled_at 必须是带时区时间")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise Invalid("scheduled_at 必须是带时区时间") from None
    if parsed.tzinfo is None:
        raise Invalid("scheduled_at 必须包含时区")
    if parsed.date().isoformat() != scheduled_on:
        raise Invalid("scheduled_at 与 scheduled_on 日期不一致")
    return value


def _list_of_text(value, field, limit=100):
    if not isinstance(value, list) or len(value) > limit or any(
        not isinstance(item, str) or len(item) > 10000 for item in value
    ):
        raise Invalid(field + "必须是字符串数组")
    return value


def _ids(value, field, limit=30):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit or any(
        not isinstance(item, str) or not item or len(item) > 500 for item in value
    ) or len(set(value)) != len(value):
        raise Invalid(field + "必须是不超过 " + str(limit) + " 个不重复 ID")
    return value


def _command(store, c, action, opportunity_id, target_id, body):
    key = required(body.get("idempotency_key"), "idempotency_key（请刷新客户端）", 200)
    ident = "interview-command:" + digest([action, opportunity_id, target_id, key])
    fingerprint = digest(body)
    row = c.execute(
        "SELECT body FROM records WHERE id=? AND kind='interview_command'", (ident,)
    ).fetchone()
    if row:
        saved = json.loads(row[0])
        if saved["fingerprint"] != fingerprint:
            raise Conflict("请求标识已用于不同 Interview 操作")
        return saved["result"], ident, fingerprint
    return None, ident, fingerprint


def _remember(store, c, ident, fingerprint, result):
    store._record(c, "interview_command", {
        "id": ident, "fingerprint": fingerprint, "result": result, "created_at": now(),
    })
    return result


def _raw_record(store, c, interview_id):
    row = c.execute("SELECT body FROM records WHERE id=? AND kind='interview'", (interview_id,)).fetchone()
    if not row:
        raise Missing("Interview 不存在")
    return json.loads(row[0])


def dto(raw):
    if raw.get("interview_format") == 2:
        return dict(raw, legacy=False)
    return dict(
        raw, interview_format=None, type=None, name=None, status=None,
        confirmed_on=None, scheduled_on=None, scheduled_at=None, completed_on=None,
        cancelled_on=None, target_real_interview_id=None,
        revision=raw.get("revision", 0), legacy=True,
        legacy_name=raw.get("round"), legacy_occurred_at=raw.get("occurred_at"),
    )


def _owned(store, c, opportunity_id, interview_id, require_current=False):
    opportunity = op.resolve(store, c, opportunity_id)
    raw = _raw_record(store, c, interview_id)
    owner = raw.get("opportunity_id")
    if not isinstance(owner, str) or op.canonical_id(owner) != opportunity["id"]:
        raise Missing("Interview 不存在")
    item = dto(raw)
    if require_current and item["legacy"]:
        raise Conflict("legacy_interview_read_only: 历史 Interview 类型和日期待核对")
    return opportunity, raw, item


def _detail(store, c, opportunity_id, interview_id):
    opportunity, _, item = _owned(store, c, opportunity_id, interview_id)
    item = dict(item)
    source_id = item.get("source_communication_id")
    if source_id:
        try:
            from .communication import owned as communication_owned
            item["source_communication"] = communication_owned(
                store, c, opportunity["id"], source_id, include_archived=True
            )[2]
        except Missing:
            item["source_communication"] = {"id": source_id, "missing": True, "archived": None}
    return item


def list_interviews(store, c, opportunity_id):
    opportunity = op.resolve(store, c, opportunity_id)
    rows = []
    for raw in store._records(c, "interview"):
        owner = raw.get("opportunity_id")
        if isinstance(owner, str) and op.canonical_id(owner) == opportunity["id"]:
            item = dto(raw)
            review = _get_material(store, c, "interview_final_review", item["id"]) if not item["legacy"] else None
            item["has_final_review"] = review is not None
            item["final_review_id"] = review["id"] if review else None
            rows.append(item)
    return sorted(rows, key=lambda item: (
        item.get("scheduled_on") or item.get("completed_on") or item.get("confirmed_on") or "",
        item.get("created_at") or "", item["id"],
    ), reverse=True)


def confirm_real(store, opportunity_id, body):
    _strict(body, {"name", "scheduled_on", "scheduled_at", "source_communication_id",
                   "expected_opportunity_revision", "idempotency_key"})
    name = required(body.get("name"), "轮次名称", 500)
    scheduled_on = _day(body.get("scheduled_on"), "预约日期", optional=True)
    scheduled_at = _timestamp(body.get("scheduled_at"), scheduled_on) if scheduled_on else None
    if not scheduled_on and body.get("scheduled_at") not in (None, ""):
        raise Invalid("设置 scheduled_at 时必须提供 scheduled_on")
    expected_opportunity = _expected(body.get("expected_opportunity_revision"))
    with store.connect() as c:
        opportunity = op.writable(store, c, opportunity_id)
        replay, command_id, fingerprint = _command(store, c, "confirm_real", opportunity["id"], None, body)
        if replay is not None:
            return {"interview": _detail(store, c, opportunity["id"], replay["interview_id"]),
                    "opportunity": op.resolve(store, c, opportunity["id"])}
        if opportunity["revision"] != expected_opportunity:
            raise Conflict("机会已更新，请保留输入并重新核对")
        if opportunity["result"] != "active" or opportunity["phase"] not in {"submitted", "interview"}:
            raise Conflict("confirm_real_requires_submitted_or_interview: 仅进行中的已投递/面试机会可确认正式面试")
        source_id = body.get("source_communication_id")
        if source_id is not None:
            from .communication import owned as communication_owned
            communication_owned(store, c, opportunity["id"], required(source_id, "来源沟通", 500))
        timestamp = now()
        confirmed_on = op.business_day(timestamp)
        interview = {
            "id": uid(), "interview_format": 2, "opportunity_id": opportunity["id"],
            "type": "real", "name": name,
            "status": "scheduled" if scheduled_on else "pending",
            "confirmed_on": confirmed_on, "scheduled_on": scheduled_on,
            "scheduled_at": scheduled_at, "completed_on": None, "cancelled_on": None,
            "target_real_interview_id": None, "source_communication_id": source_id,
            "created_at": timestamp, "updated_at": timestamp, "revision": 0,
        }
        store._record(c, "interview", interview)
        if opportunity["phase"] == "submitted":
            row = store._get(c, opportunity["id"], "opportunity")
            row.update(phase="interview", phase_changed_on=confirmed_on,
                       phase_source={"action": "ConfirmRealInterview", "occurred_at": timestamp,
                                     "interview_id": interview["id"]})
            store._save(c, "opportunity", row, opportunity["revision"])
            store._bump(c)
        result = {"interview_id": interview["id"]}
        _remember(store, c, command_id, fingerprint, result)
        return {"interview": dto(interview), "opportunity": op.resolve(store, c, opportunity["id"])}


def upgrade_legacy(store, opportunity_id, interview_id, body):
    """Upgrade one legacy typed Interview only from explicit user-confirmed facts."""
    _strict(body, {"type", "name", "status", "confirmed_on", "scheduled_on", "scheduled_at",
                   "completed_on", "cancelled_on", "target_real_interview_id", "expected_revision",
                   "expected_opportunity_revision", "idempotency_key"}, "UpgradeLegacyInterview")
    kind = body.get("type")
    status = body.get("status")
    if kind not in {"real", "simulation"}:
        raise Invalid("type 只能是 real 或 simulation")
    if status not in (REAL_STATUSES if kind == "real" else SIMULATION_STATUSES):
        raise Invalid("status 与 Interview type 不匹配")
    name = required(body.get("name"), "轮次名称", 500)
    confirmed_on = _day(body.get("confirmed_on"), "确认日期")
    scheduled_on = _day(body.get("scheduled_on"), "预约日期", optional=True)
    scheduled_at = _timestamp(body.get("scheduled_at"), scheduled_on) if scheduled_on else None
    completed_on = _day(body.get("completed_on"), "完成日期", optional=True)
    cancelled_on = _day(body.get("cancelled_on"), "取消日期", optional=True)
    if kind == "simulation" and (scheduled_on is not None or scheduled_at is not None):
        raise Invalid("Simulation 不接受预约日期或时间")
    if status == "scheduled" and not scheduled_on:
        raise Invalid("scheduled 状态需要预约日期")
    if status == "completed" and not completed_on:
        raise Invalid("completed 状态需要完成日期")
    if status == "cancelled" and not cancelled_on:
        raise Invalid("cancelled 状态需要取消日期")
    if status != "completed" and completed_on is not None:
        raise Invalid("仅 completed 状态接受完成日期")
    if status != "cancelled" and cancelled_on is not None:
        raise Invalid("仅 cancelled 状态接受取消日期")
    expected = _expected(body.get("expected_revision"))
    expected_opportunity = _expected(body.get("expected_opportunity_revision"))
    with store.connect() as c:
        opportunity = op.writable(store, c, opportunity_id)
        replay, command_id, fingerprint = _command(
            store, c, "upgrade_legacy_interview", opportunity["id"], interview_id, body
        )
        if replay is not None:
            return {"interview": _detail(store, c, opportunity["id"], interview_id),
                    "opportunity": op.resolve(store, c, opportunity["id"])}
        _, raw, item = _owned(store, c, opportunity["id"], interview_id)
        if not item["legacy"]:
            raise Conflict("Interview 已是当前格式")
        if item["revision"] != expected or opportunity["revision"] != expected_opportunity:
            raise Conflict("Interview 或 Opportunity 已更新，请重新核对")
        if opportunity["result"] != "active" or opportunity["phase"] not in {"submitted", "interview"}:
            raise Conflict("legacy_upgrade_requires_active_submitted_or_interview")
        parent_id = body.get("target_real_interview_id")
        if kind == "simulation":
            parent_id = required(parent_id, "target_real_interview_id", 500)
            _, _, parent = _owned(store, c, opportunity["id"], parent_id, require_current=True)
            if parent["type"] != "real":
                raise Conflict("Simulation 必须绑定同机会真实面试")
        elif parent_id not in (None, ""):
            raise Invalid("Real Interview 不接受 target_real_interview_id")
        timestamp = now()
        raw.update(
            interview_format=2, type=kind, name=name, status=status,
            confirmed_on=confirmed_on, scheduled_on=scheduled_on, scheduled_at=scheduled_at,
            completed_on=completed_on, cancelled_on=cancelled_on,
            target_real_interview_id=parent_id if kind == "simulation" else None,
            revision=expected + 1, updated_at=timestamp,
            legacy_provenance={key: raw.get(key) for key in
                               ("round", "occurred_at", "submission_id", "raw_note_id") if key in raw},
        )
        store._record(c, "interview", raw)
        if kind == "real" and opportunity["phase"] == "submitted":
            row = store._get(c, opportunity["id"], "opportunity")
            row.update(phase="interview", phase_changed_on=confirmed_on,
                       phase_source={"action": "UpgradeLegacyInterview", "occurred_at": timestamp,
                                     "interview_id": interview_id})
            store._save(c, "opportunity", row, opportunity["revision"])
            store._bump(c)
        _remember(store, c, command_id, fingerprint, {"interview_id": interview_id})
        return {"interview": dto(raw), "opportunity": op.resolve(store, c, opportunity["id"])}


def _change_status(store, opportunity_id, interview_id, action, body):
    allowed = {"expected_revision", "idempotency_key"}
    if action == "schedule":
        allowed |= {"scheduled_on", "scheduled_at"}
    elif action == "complete":
        allowed |= {"completed_on"}
    elif action == "cancel":
        allowed |= {"cancelled_on"}
    _strict(body, allowed)
    expected = _expected(body.get("expected_revision"))
    with store.connect() as c:
        opportunity = op.writable(store, c, opportunity_id)
        replay, command_id, fingerprint = _command(store, c, action, opportunity["id"], interview_id, body)
        if replay is not None:
            return _detail(store, c, opportunity["id"], interview_id)
        _, raw, item = _owned(store, c, opportunity["id"], interview_id, require_current=True)
        if item["revision"] != expected:
            raise Conflict("Interview 已在其它窗口更新，请保留输入并重新载入")
        if opportunity["result"] != "active" or opportunity["phase"] != "interview":
            raise Conflict("ended_interview_status_read_only: 已结束机会不能继续推进 Interview 状态")
        if item["status"] in {"completed", "cancelled"}:
            raise Conflict("Interview 已终结，普通状态动作不能回退")
        if action in {"schedule", "pending"} and item["type"] != "real":
            raise Conflict("只有真实面试可以排期或待重约")
        if action == "schedule":
            scheduled_on = _day(body.get("scheduled_on"), "预约日期")
            raw.update(status="scheduled", scheduled_on=scheduled_on,
                       scheduled_at=_timestamp(body.get("scheduled_at"), scheduled_on),
                       completed_on=None, cancelled_on=None)
        elif action == "pending":
            raw.update(status="pending", scheduled_on=None, scheduled_at=None,
                       completed_on=None, cancelled_on=None)
        elif action == "complete":
            raw.update(status="completed", completed_on=_day(body.get("completed_on"), "完成日期"),
                       cancelled_on=None)
        else:
            raw.update(status="cancelled", cancelled_on=_day(body.get("cancelled_on"), "取消日期"),
                       completed_on=None)
        raw.update(revision=expected + 1, updated_at=now())
        store._record(c, "interview", raw)
        _remember(store, c, command_id, fingerprint, {"interview_id": interview_id,
                                                       "revision": raw["revision"]})
        return dto(raw)


def _material_id(kind, interview_id):
    return kind.replace("interview_", "interview-").replace("_", "-") + ":" + interview_id


def _get_material(store, c, kind, interview_id, missing=False):
    ident = _material_id(kind, interview_id)
    row = c.execute("SELECT body FROM records WHERE id=? AND kind=?", (ident, kind)).fetchone()
    if not row:
        if missing:
            raise Missing("资料不存在")
        return None
    return json.loads(row[0])


def _current_save(store, c, kind, interview_id, values, expected):
    old = _get_material(store, c, kind, interview_id)
    revision = old.get("revision", 0) if old else 0
    if revision != expected:
        raise Conflict("内容已在其它窗口更新，请保留输入并重新载入")
    timestamp = now()
    obj = {
        "id": _material_id(kind, interview_id), "interview_session_id": interview_id,
        **values, "revision": expected + 1, "hash": digest(values),
        "created_at": old.get("created_at", timestamp) if old else timestamp,
        "updated_at": timestamp,
    }
    store._record(c, kind, obj)
    return obj


def _preparation_values(body):
    _strict(body, {*PREPARATION_FIELDS, "expected_revision", "idempotency_key"}, "Preparation")
    focus = body.get("focus", "")
    notes = body.get("notes", "")
    if not isinstance(focus, str) or len(focus) > 100000 or not isinstance(notes, str) or len(notes) > 100000:
        raise Invalid("Preparation 文本超出长度限制")
    return {
        "focus": focus,
        "expected_questions": _list_of_text(body.get("expected_questions", []), "预计问题"),
        "priority_projects": _list_of_text(body.get("priority_projects", []), "重点项目"),
        "risks": _list_of_text(body.get("risks", []), "风险问题"),
        "notes": notes,
    }


def save_preparation(store, opportunity_id, interview_id, body):
    values = _preparation_values(body)
    expected = _expected(body.get("expected_revision"))
    with store.connect() as c:
        opportunity = op.writable(store, c, opportunity_id)
        _, _, interview = _owned(store, c, opportunity["id"], interview_id, require_current=True)
        if interview["type"] != "real":
            raise Conflict("Simulation 不拥有 Preparation")
        replay, command_id, fingerprint = _command(store, c, "save_preparation", opportunity["id"], interview_id, body)
        if replay is not None:
            return _get_material(store, c, "interview_preparation", interview_id, True)
        saved = _current_save(store, c, "interview_preparation", interview_id, values, expected)
        _remember(store, c, command_id, fingerprint, {"id": saved["id"], "revision": saved["revision"]})
        return saved


def _review_values(body):
    _strict(body, {*REVIEW_FIELDS, "expected_revision", "idempotency_key"}, "Final Review")
    summary = body.get("summary")
    if not isinstance(summary, str) or len(summary) > 100000:
        raise Invalid("Final Review summary 不合法")
    return {
        "summary": summary,
        "key_qa": _list_of_text(body.get("key_qa"), "key_qa"),
        "patterns": _list_of_text(body.get("patterns"), "patterns"),
        "discoveries": _list_of_text(body.get("discoveries"), "discoveries"),
        "next_actions": _list_of_text(body.get("next_actions"), "next_actions"),
    }


def save_review(store, opportunity_id, interview_id, body):
    values = _review_values(body)
    expected = _expected(body.get("expected_revision"))
    with store.connect() as c:
        opportunity = op.writable(store, c, opportunity_id)
        _owned(store, c, opportunity["id"], interview_id, require_current=True)
        replay, command_id, fingerprint = _command(store, c, "save_final_review", opportunity["id"], interview_id, body)
        if replay is not None:
            return _get_material(store, c, "interview_final_review", interview_id, True)
        saved = _current_save(store, c, "interview_final_review", interview_id, values, expected)
        _remember(store, c, command_id, fingerprint, {"id": saved["id"], "revision": saved["revision"]})
        return saved


def save_raw(store, opportunity_id, interview_id, body):
    _strict(body, {"content", "expected_revision", "idempotency_key"}, "Raw")
    content = body.get("content")
    if not isinstance(content, str) or not content.strip() or len(content) > 100000:
        raise Invalid("Raw 文本不能为空或超出长度限制")
    expected = _expected(body.get("expected_revision"))
    with store.connect() as c:
        opportunity = op.writable(store, c, opportunity_id)
        _owned(store, c, opportunity["id"], interview_id, require_current=True)
        replay, command_id, fingerprint = _command(store, c, "save_raw", opportunity["id"], interview_id, body)
        if replay is not None:
            return _get_material(store, c, "interview_raw", interview_id, True)
        saved = _current_save(store, c, "interview_raw", interview_id, {"content": content}, expected)
        for proposal in store._records(c, "patch_proposal"):
            if proposal.get("source_raw_id") == saved["id"] and proposal.get("status") == "pending":
                proposal.update(status="stale", revision=proposal.get("revision", 0) + 1,
                                stale_reason="Interview Raw 已更新", updated_at=now())
                store._record(c, "patch_proposal", proposal)
        for snapshot in store._records(c, "context_snapshot"):
            if any(ref.get("id") == saved["id"] for ref in snapshot.get("source_refs", [])):
                snapshot.update(stale=True, stale_reason="Interview Raw 已更新")
                store._record(c, "context_snapshot", snapshot)
        _remember(store, c, command_id, fingerprint, {"id": saved["id"], "revision": saved["revision"]})
        return saved


def _submission(c, opportunity):
    alias = opportunity.get("legacy_job_id") or opportunity["id"].split(":", 1)[1]
    rows = []
    for canonical, raw in c.execute("SELECT canonical_opportunity_id,body FROM applications"):
        body = json.loads(raw)
        if canonical == opportunity["id"] or body.get("opportunity_id") == opportunity["id"]:
            rows.append(body)
        elif canonical is None and body.get("opportunity_id") is None and body.get("job_id") == alias:
            rows.append(body)
    if len(rows) != 1:
        raise Conflict("Interview Context 需要同机会唯一 Submission")
    return rows[0]


def _source(identifier, revision, value, purpose):
    return {"id": identifier, "revision": revision, "hash": digest(value),
            "purpose": purpose, "selected_content": value}


def _compile_pack(store, c, opportunity, target_real, task_type, body, raw=None, task_session=None):
    communication_ids = _ids(body.get("communication_ids"), "communication_ids")
    review_ids = _ids(body.get("selected_review_ids"), "selected_review_ids")
    wiki_ids = _ids(body.get("wiki_ids"), "wiki_ids")
    submission = _submission(c, opportunity)
    resume_snapshot = submission.get("resume_snapshot")
    resume_value = resume_snapshot if resume_snapshot is not None else {
        "state": "none", "note": "本次无简历",
    }
    sources = [
        _source(opportunity["id"], opportunity["revision"], {
            "company": opportunity["company"], "title": opportunity["title"],
            "jd": opportunity["jd"], "action_url": opportunity.get("action_url", ""),
        }, "opportunity"),
        _source(submission["id"], 0, resume_value, "submission_resume_snapshot"),
        _source(target_real["id"], target_real["revision"], {
            key: target_real.get(key) for key in (
                "name", "status", "confirmed_on", "scheduled_on", "scheduled_at", "completed_on"
            )
        }, "target_real_interview"),
    ]
    research = _get_research(store, c, opportunity["id"])
    if research["revision"]:
        sources.append(_source(research["id"], research["revision"], research["items"], "opportunity_research"))
    preparation = _get_material(store, c, "interview_preparation", target_real["id"])
    if preparation:
        sources.append(_source(preparation["id"], preparation["revision"], {
            key: preparation[key] for key in PREPARATION_FIELDS
        }, "interview_preparation"))
    from .communication import owned as communication_owned
    for communication_id in communication_ids:
        event = communication_owned(store, c, opportunity["id"], communication_id, include_archived=True)[2]
        sources.append(_source(event["id"], event["revision"], {
            "type": event.get("type"), "occurred_on": event.get("occurred_on"),
            "content": event.get("content"), "archived": event.get("archived", False),
        }, "selected_communication"))
    for review_id in review_ids:
        row = c.execute("SELECT body FROM records WHERE id=? AND kind='interview_final_review'", (review_id,)).fetchone()
        if not row:
            raise Missing("所选 Final Review 不存在")
        review = json.loads(row[0])
        _, _, session = _owned(store, c, opportunity["id"], review["interview_session_id"], require_current=True)
        sources.append(_source(review["id"], review["revision"], {
            key: review[key] for key in REVIEW_FIELDS
        }, "selected_final_review_" + session["type"]))
    if wiki_ids:
        from .knowledge import selected_wiki_sources
        alias = opportunity.get("legacy_job_id") or opportunity["id"].split(":", 1)[1]
        for selected in selected_wiki_sources(store, c, wiki_ids, alias):
            sources.append(_source(selected["id"], selected["revision"],
                                   selected["content"], "career_context"))
    if raw is not None:
        sources.append(_source(raw["id"], raw["revision"], raw["content"], "current_interview_raw"))
    size = sum(len(json.dumps(source["selected_content"], ensure_ascii=False)) for source in sources)
    if len(sources) > 50 or size > 200000:
        raise Invalid("Interview Context 超出预算，请缩小选择范围")
    target_session = task_session or target_real
    return {
        "schemaVersion": 1, "task_type": task_type,
        "target": {"type": target_session["type"] + "_interview", "id": target_session["id"],
                   "target_real_interview_id": target_real["id"],
                   "opportunity_id": opportunity["id"]},
        "resume_snapshot": resume_value,
        "selected_review_ids": review_ids,
        "sources": sources, "unknowns": [] if research["revision"] else ["opportunity_research"],
        "omissions": ["current_resume_document", "unselected_interview_raw", "feedback", "employment_private_notes"],
        "budget_used": {"source_count": len(sources), "content_chars": size,
                        "source_limit": 50, "content_limit": 200000},
        "policy_version": "interview-context-v1", "epoch": store._epoch(c),
    }


def _snapshot(store, c, pack, persist_content):
    snapshot = {
        "id": uid(), "task_type": pack["task_type"], "target": pack["target"],
        "source_refs": [{key: source[key] for key in ("id", "revision", "hash", "purpose")}
                        for source in pack["sources"]],
        "selected_review_ids": pack["selected_review_ids"], "packet_hash": digest(pack),
        "policy_version": pack["policy_version"], "created_at": now(), "stale": False,
    }
    if persist_content:
        snapshot["packet"] = pack
    store._record(c, "context_snapshot", snapshot)
    return snapshot


def start_simulation(store, opportunity_id, real_id, body):
    _strict(body, {"selected_review_ids", "communication_ids", "wiki_ids", "idempotency_key"}, "Simulation")
    with store.connect() as c:
        opportunity = op.writable(store, c, opportunity_id)
        _, _, real = _owned(store, c, opportunity["id"], real_id, require_current=True)
        if real["type"] != "real":
            raise Conflict("Simulation 必须绑定真实面试")
        replay, command_id, fingerprint = _command(store, c, "start_simulation", opportunity["id"], real_id, body)
        if replay is not None:
            simulation = _detail(store, c, opportunity["id"], replay["interview_id"])
            snapshot = store._get(c, replay["snapshot_id"], "context_snapshot", True)
            return {"interview": simulation, "context_snapshot_id": snapshot["id"],
                    "context_pack": snapshot["packet"], "mode": "export"}
        if opportunity["result"] != "active" or opportunity["phase"] != "interview":
            raise Conflict("Simulation 只属于进行中的面试阶段")
        pack = _compile_pack(store, c, opportunity, real, "interview_simulation", body)
        snapshot = _snapshot(store, c, pack, True)
        sequence = 1 + sum(1 for item in store._records(c, "interview")
                           if item.get("interview_format") == 2 and item.get("type") == "simulation"
                           and item.get("target_real_interview_id") == real_id)
        timestamp = now()
        simulation = {
            "id": uid(), "interview_format": 2, "opportunity_id": opportunity["id"],
            "type": "simulation", "name": real["name"] + "模拟 #" + str(sequence),
            "status": "pending", "confirmed_on": op.business_day(timestamp),
            "scheduled_on": None, "scheduled_at": None, "completed_on": None,
            "cancelled_on": None, "target_real_interview_id": real_id,
            "source_communication_id": None, "context_snapshot_id": snapshot["id"],
            "created_at": timestamp, "updated_at": timestamp, "revision": 0,
        }
        store._record(c, "interview", simulation)
        _remember(store, c, command_id, fingerprint, {"interview_id": simulation["id"],
                                                       "snapshot_id": snapshot["id"]})
        return {"interview": dto(simulation), "context_snapshot_id": snapshot["id"],
                "context_pack": pack, "mode": "export"}


def _provider_result(store, pack, before_call=None, operation_id=None, target=None):
    from .model_gateway import ModelGateway
    schemas = {
        "interview_final_review": {"version": 1, "type": "object", "required": list(REVIEW_FIELDS)},
        "interview_research_patch": {"version": 1, "type": "object", "required": ["items"]},
    }
    return ModelGateway(store).generate(
        pack["task_type"], pack, schemas[pack["task_type"]], before_call=before_call,
        operation_id=operation_id, target=target,
    )


def _ai_intent_body(body):
    return {key: body.get(key) for key in
            ("communication_ids", "wiki_ids", "idempotency_key", "model_config_id") if key in body}


def _ai_client_intent(opportunity_id, interview_id, body):
    return {"opportunity_id": opportunity_id, "interview_id": interview_id,
            **_ai_intent_body(body)}


def _final_review_output_schema():
    return {"version": 1, "type": "object", "required": list(REVIEW_FIELDS)}


def _final_review_prepare(store, opportunity_id, interview_id, body):
    with store.connect(False) as c:
        opportunity = op.writable(store, c, opportunity_id)
        _, _, session = _owned(store, c, opportunity["id"], interview_id, require_current=True)
        raw = _get_material(store, c, "interview_raw", interview_id, True)
        target_real = session if session["type"] == "real" else _owned(
            store, c, opportunity["id"], session["target_real_interview_id"], require_current=True
        )[2]
        pack = _compile_pack(store, c, opportunity, target_real, "interview_final_review",
                             dict(body, selected_review_ids=[]), raw, task_session=session)
        pack["manifest"] = cm.manifest(
            "interview_final_review",
            {"kind": "interview", "id": session["id"]},
            session["revision"],
            [cm.dependency(
                "interview_source", source["id"], source["revision"],
                source["selected_content"], source["purpose"], content_hash=source["hash"]
            ) for source in pack["sources"]],
        )
        replay, _, _ = _command(store, c, "generate_final_review", opportunity["id"], interview_id, _ai_intent_body(body))
    if replay is not None:
        saved = replay.get("api_result")
        if saved is None:
            return {"_replay_expired": True}
        return {"_replay_value": saved}
    return {"opportunity": opportunity, "session": session, "raw": raw, "pack": pack, "body": body}


def _final_review_dispatch(store, prepared, binder):
    return _provider_result(
        store, prepared["pack"],
        before_call=lambda payload_hash: binder(payload_hash, prepared["pack"].get("manifest")),
        operation_id=prepared.get("_operation_id"),
        target={"kind": "interview", "id": prepared["session"]["id"]},
    )


def _final_review_persist(store, prepared, result, diagnostics):
    try:
        suggestion = {key: result[key] for key in REVIEW_FIELDS}
        _review_values({**suggestion, "expected_revision": 0, "idempotency_key": "validation"})
    except (Invalid, KeyError, TypeError) as exc:
        raise ao.AIValidationError(str(exc)) from exc
    raw, opportunity, body, pack = prepared["raw"], prepared["opportunity"], prepared["body"], prepared["pack"]
    value = {"suggestion": suggestion, "mode": diagnostics["mode"],
             "context_snapshot_id": None, "source_raw_revision": raw["revision"]}
    with store.connect() as c:
        current_opportunity = op.writable(store, c, opportunity["id"])
        replay, command_id, fingerprint = _command(
            store, c, "generate_final_review", current_opportunity["id"], prepared["session"]["id"], _ai_intent_body(body)
        )
        if replay is not None:
            if replay.get("api_result") is None:
                raise ao.AIValidationError("result_expired: 旧 Interview 建议正文已不可恢复")
            return replay["api_result"]
        snapshot = _snapshot(store, c, pack, False)
        value["context_snapshot_id"] = snapshot["id"]
        _remember(store, c, command_id, fingerprint, {
            "mode": diagnostics["mode"], "context_snapshot_id": snapshot["id"],
            "source_raw_revision": raw["revision"], "source_raw_hash": raw["hash"],
            "suggestion_hash": digest(suggestion),
        })
    return value


def _final_review_prepare_record(store, opportunity_id, interview_id, body):
    prepared = _final_review_prepare(store, opportunity_id, interview_id, body)
    if "_replay_value" in prepared or "_replay_expired" in prepared:
        return prepared
    payload, diagnostics, _, clean_pack, budget_info = ModelGateway(store).prepare_payload(
        "interview_final_review", prepared["pack"], _final_review_output_schema(), body.get("model_config_id")
    )
    prepared.update(pack=clean_pack, payload=payload, diagnostics=diagnostics, budget=budget_info)
    return prepared


def _final_review_create_preparation(store, opportunity_id, interview_id, body):
    prepared = _final_review_prepare_record(store, opportunity_id, interview_id, body)
    if "_replay_value" in prepared:
        return prepared["_replay_value"]
    return outbound.create_preparation(
        store, task_type="interview_final_review", target={"kind": "interview", "id": interview_id},
        client_intent=_ai_client_intent(opportunity_id, interview_id, body),
        packet=prepared["pack"], payload=prepared["payload"], manifest=prepared["pack"].get("manifest"),
        diagnostics=prepared["diagnostics"], budget_info=prepared["budget"],
    )


def _final_review_prepare_for_execution(store, opportunity_id, interview_id, body):
    prepared = _final_review_prepare_record(store, opportunity_id, interview_id, body)
    if "_replay_value" in prepared or "_replay_expired" in prepared:
        return prepared
    outbound.validate_preparation(
        store, body["prepared_id"], task_type="interview_final_review",
        target={"kind": "interview", "id": interview_id},
        client_intent=_ai_client_intent(opportunity_id, interview_id, body),
        payload_hash=body.get("payload_hash"), packet=prepared["pack"], payload=prepared["payload"],
        manifest=prepared["pack"].get("manifest"),
    )
    return prepared


def generate_final_review(store, opportunity_id, interview_id, body):
    _strict(body, {"communication_ids", "wiki_ids", "idempotency_key", "model_config_id",
                   "prepared_id", "payload_hash", "confirm_outbound"}, "GenerateFinalReview")
    key = required(body.get("idempotency_key"), "idempotency_key（请刷新客户端）", 200)
    if not body.get("prepared_id") or body.get("confirm_outbound") is not True:
        return JSONResponse(_final_review_create_preparation(store, opportunity_id, interview_id, body), status_code=409)
    execution = ao.execute(
        store, task_type="interview_final_review", target_kind="interview", target_id=interview_id,
        idempotency_key=key, client_intent=_ai_client_intent(opportunity_id, interview_id, body),
        prepare=lambda: _final_review_prepare_for_execution(store, opportunity_id, interview_id, body),
        dispatch=lambda prepared, binder: _final_review_dispatch(store, prepared, binder),
        persist=lambda prepared, result, diagnostics: _final_review_persist(store, prepared, result, diagnostics),
        retain_result=False,
    )
    return ao.unwrap(execution)


def _research_id(opportunity_id):
    return rs.research_id("opportunity_research", opportunity_id)


def _get_research(store, c, opportunity_id):
    return rs.get(store, c, "opportunity_research", opportunity_id)


def _patch_items(value):
    if not isinstance(value, list) or not value or len(value) > 30:
        raise Invalid("Research Patch 必须包含 1 至 30 项")
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"category", "content"}:
            raise Invalid("Research Patch item 结构不合法")
        category = item.get("category")
        content = item.get("content")
        if category not in RESEARCH_CATEGORIES or not isinstance(content, str) or not content.strip() or len(content) > 10000:
            raise Invalid("Research Patch category/content 不合法")
        result.append({"category": category, "content": content})
    return result


def _patch_prepare(store, opportunity_id, interview_id, body):
    with store.connect(False) as c:
        opportunity = op.writable(store, c, opportunity_id)
        _, _, session = _owned(store, c, opportunity["id"], interview_id, require_current=True)
        if session["type"] != "real":
            raise Conflict("Simulation 没有 GenerateResearchPatch 能力")
        replay, _, _ = _command(store, c, "generate_research_patch", opportunity["id"], interview_id, _ai_intent_body(body))
        if replay is not None:
            if replay.get("api_result") is not None:
                return {"_replay_value": replay["api_result"]}
            if replay.get("proposal_id"):
                proposal = store._get(c, replay["proposal_id"], "patch_proposal", True)
                return {"_replay_value": {"proposal": proposal, "mode": replay.get("mode", "unknown")}}
            return {"_replay_expired": True}
        raw = _get_material(store, c, "interview_raw", interview_id, True)
        pack = _compile_pack(store, c, opportunity, session, "interview_research_patch",
                             dict(body, selected_review_ids=[]), raw, task_session=session)
        target, target_exists = rs.lookup(store, c, "opportunity_research", opportunity["id"])
        dependencies = [
            cm.dependency("opportunity", opportunity["id"], opportunity["revision"],
                          cm.selected_opportunity(opportunity), "current_jd"),
            cm.dependency("interview_raw", raw["id"], raw["revision"], raw["content"],
                          "current_interview_raw", content_hash=raw["hash"]),
            cm.dependency(
                "opportunity_research", target["id"], target["revision"],
                rs.content_hash(target) if target_exists else None, "target_opportunity_research",
                content_hash=rs.content_hash(target) if target_exists else None,
                expected_absent=not target_exists, owner_id=opportunity["id"],
            ),
        ]
        for source in pack["sources"]:
            if source["purpose"] == "selected_communication":
                dependencies.append(cm.dependency(
                    "communication", source["id"], source["revision"], source["selected_content"],
                    source["purpose"], content_hash=source["hash"],
                ))
            elif source["purpose"] == "career_context":
                dependencies.append(cm.dependency(
                    "wiki_entry", source["id"], source["revision"], source["selected_content"],
                    source["purpose"], content_hash=source["hash"],
                ))
        patch_manifest = cm.manifest(
            "interview_research_patch",
            {"kind": "opportunity_research", "id": target["id"], "opportunity_id": opportunity["id"],
             **({"expected_absent": True} if not target_exists else {})},
            target["revision"], dependencies,
        )
    return {"opportunity": opportunity, "session": session, "raw": raw, "target": target,
            "pack": pack, "manifest": patch_manifest, "body": body}


def _patch_dispatch(store, prepared, binder):
    return _provider_result(
        store, prepared["pack"],
        before_call=lambda payload_hash: binder(payload_hash, prepared["manifest"]),
        operation_id=prepared.get("_operation_id"),
        target={"kind": "interview", "id": prepared["session"]["id"]},
    )


def _patch_persist(store, prepared, result, diagnostics):
    try:
        items = _patch_items(result.get("items"))
    except (Invalid, AttributeError, TypeError, KeyError) as exc:
        raise ao.AIValidationError(str(exc)) from exc
    opportunity, raw, target, body = prepared["opportunity"], prepared["raw"], prepared["target"], prepared["body"]
    with store.connect() as c:
        current_opportunity = op.writable(store, c, opportunity["id"])
        replay, command_id, fingerprint = _command(
            store, c, "generate_research_patch", current_opportunity["id"], prepared["session"]["id"], _ai_intent_body(body)
        )
        if replay is not None:
            if replay.get("api_result") is not None:
                return replay["api_result"]
            if replay.get("proposal_id"):
                proposal = store._get(c, replay["proposal_id"], "patch_proposal", True)
                return {"proposal": proposal, "mode": replay.get("mode", diagnostics["mode"])}
            raise ao.AIValidationError("result_expired: 旧 Research Patch 建议正文已不可恢复")
        snapshot = _snapshot(store, c, prepared["pack"], False)
        timestamp = now()
        proposal = {
            "id": uid(), "proposal_format": 1, "opportunity_id": opportunity["id"],
            "origin_interview_id": prepared["session"]["id"], "origin_interview_type": "real",
            "source_raw_id": raw["id"], "source_raw_revision": raw["revision"],
            "source_raw_hash": raw["hash"], "target_type": "opportunity_research",
            "target_id": target["id"], "expected_target_revision": target["revision"],
            "items": items, "status": "pending", "revision": 0,
            "context_snapshot_id": snapshot["id"], "manifest": prepared["manifest"],
            "created_at": timestamp, "updated_at": timestamp,
        }
        api_result = {"proposal": proposal, "mode": diagnostics["mode"]}
        store._record(c, "patch_proposal", proposal)
        _remember(store, c, command_id, fingerprint,
                  {"proposal_id": proposal["id"], "mode": diagnostics["mode"], "api_result": api_result})
        return api_result


def _patch_output_schema():
    return {"version": 1, "type": "object", "required": ["items"]}


def _patch_prepare_record(store, opportunity_id, interview_id, body):
    prepared = _patch_prepare(store, opportunity_id, interview_id, body)
    if "_replay_value" in prepared or "_replay_expired" in prepared:
        return prepared
    payload, diagnostics, _, clean_pack, budget_info = ModelGateway(store).prepare_payload(
        "interview_research_patch", prepared["pack"], _patch_output_schema(), body.get("model_config_id")
    )
    prepared.update(pack=clean_pack, payload=payload, diagnostics=diagnostics, budget=budget_info)
    return prepared


def _patch_create_preparation(store, opportunity_id, interview_id, body):
    prepared = _patch_prepare_record(store, opportunity_id, interview_id, body)
    if "_replay_value" in prepared:
        return prepared["_replay_value"]
    return outbound.create_preparation(
        store, task_type="interview_research_patch", target={"kind": "interview", "id": interview_id},
        client_intent=_ai_client_intent(opportunity_id, interview_id, body),
        packet=prepared["pack"], payload=prepared["payload"], manifest=prepared["manifest"],
        diagnostics=prepared["diagnostics"], budget_info=prepared["budget"],
    )


def _patch_prepare_for_execution(store, opportunity_id, interview_id, body):
    prepared = _patch_prepare_record(store, opportunity_id, interview_id, body)
    if "_replay_value" in prepared or "_replay_expired" in prepared:
        return prepared
    outbound.validate_preparation(
        store, body["prepared_id"], task_type="interview_research_patch",
        target={"kind": "interview", "id": interview_id},
        client_intent=_ai_client_intent(opportunity_id, interview_id, body),
        payload_hash=body.get("payload_hash"), packet=prepared["pack"], payload=prepared["payload"],
        manifest=prepared["manifest"],
    )
    return prepared


def generate_research_patch(store, opportunity_id, interview_id, body):
    _strict(body, {"communication_ids", "wiki_ids", "idempotency_key", "model_config_id",
                   "prepared_id", "payload_hash", "confirm_outbound"}, "GenerateResearchPatch")
    key = required(body.get("idempotency_key"), "idempotency_key（请刷新客户端）", 200)
    if not body.get("prepared_id") or body.get("confirm_outbound") is not True:
        return JSONResponse(_patch_create_preparation(store, opportunity_id, interview_id, body), status_code=409)
    execution = ao.execute(
        store, task_type="interview_research_patch", target_kind="interview", target_id=interview_id,
        idempotency_key=key, client_intent=_ai_client_intent(opportunity_id, interview_id, body),
        prepare=lambda: _patch_prepare_for_execution(store, opportunity_id, interview_id, body),
        dispatch=lambda prepared, binder: _patch_dispatch(store, prepared, binder),
        persist=lambda prepared, result, diagnostics: _patch_persist(store, prepared, result, diagnostics),
    )
    return ao.unwrap(execution)


def _owned_proposal(store, c, opportunity_id, proposal_id):
    opportunity = op.resolve(store, c, opportunity_id)
    proposal = store._get(c, proposal_id, "patch_proposal", True)
    if proposal.get("opportunity_id") != opportunity["id"]:
        raise Missing("PatchProposal 不存在")
    if proposal.get("origin_interview_type") != "real":
        raise Conflict("Simulation PatchProposal 非法")
    _, _, session = _owned(store, c, opportunity["id"], proposal["origin_interview_id"], require_current=True)
    if session["type"] != "real":
        raise Conflict("Simulation PatchProposal 非法")
    return opportunity, proposal


def edit_patch(store, opportunity_id, proposal_id, body):
    _strict(body, {"items", "expected_revision", "idempotency_key"}, "PatchProposal")
    items = _patch_items(body.get("items"))
    expected = _expected(body.get("expected_revision"))
    with store.connect() as c:
        opportunity, proposal = _owned_proposal(store, c, opportunity_id, proposal_id)
        replay, command_id, fingerprint = _command(store, c, "edit_research_patch", opportunity["id"], proposal_id, body)
        if replay is not None:
            return store._get(c, proposal_id, "patch_proposal", True)
        if proposal["status"] != "pending" or proposal["revision"] != expected:
            raise Conflict("PatchProposal 已变化或不可编辑")
        proposal.update(items=items, revision=expected + 1, updated_at=now())
        store._record(c, "patch_proposal", proposal)
        _remember(store, c, command_id, fingerprint, {"proposal_id": proposal_id,
                                                       "revision": proposal["revision"]})
        return proposal


def resolve_patch(store, opportunity_id, proposal_id, body):
    _strict(body, {"decision", "expected_revision", "idempotency_key"}, "PatchProposal")
    if body.get("decision") not in {"accept", "reject"}:
        raise Invalid("decision 只能是 accept 或 reject")
    expected = _expected(body.get("expected_revision"))
    with store.connect() as c:
        opportunity, proposal = _owned_proposal(store, c, opportunity_id, proposal_id)
        replay, command_id, fingerprint = _command(store, c, "resolve_research_patch", opportunity["id"], proposal_id, body)
        if replay is not None:
            return store._get(c, proposal_id, "patch_proposal", True)
        if proposal["status"] != "pending" or proposal["revision"] != expected:
            raise Conflict("PatchProposal 已变化或不可处理")
        if body["decision"] == "reject":
            proposal.update(status="rejected", revision=expected + 1, resolved_at=now(), updated_at=now())
            store._record(c, "patch_proposal", proposal)
            _remember(store, c, command_id, fingerprint, {"proposal_id": proposal_id, "revision": proposal["revision"]})
            return proposal
        cm.validate(store, c, proposal.get("manifest"))
        raw = _get_material(store, c, "interview_raw", proposal["origin_interview_id"], True)
        target = _get_research(store, c, opportunity["id"])
        if (raw["revision"], raw["hash"]) != (proposal["source_raw_revision"], proposal["source_raw_hash"]):
            raise Conflict("Raw 已更新，旧 Patch 不能应用")
        if target["revision"] != proposal["expected_target_revision"]:
            raise Conflict("OpportunityResearch 已更新，旧 Patch 不能应用")
        if body["decision"] == "accept":
            additions = [dict(item, source_refs=[{
                "kind": "interview_raw", "id": raw["id"], "revision": raw["revision"],
                "hash": raw["hash"], "interview_id": proposal["origin_interview_id"],
            }]) for item in proposal["items"]]
            target = rs.append(store, c, "opportunity_research", opportunity["id"], additions, target["revision"])
            store._bump(c)
            proposal["applied_target_revision"] = target["revision"]
        proposal.update(status="applied" if body["decision"] == "accept" else "rejected",
                        revision=expected + 1, resolved_at=now(), updated_at=now())
        store._record(c, "patch_proposal", proposal)
        _remember(store, c, command_id, fingerprint, {"proposal_id": proposal_id,
                                                       "revision": proposal["revision"]})
        return proposal


def router(store):
    api = APIRouter(prefix="/api/opportunities/{opportunity_id}")

    @api.get("/interviews")
    def listing(opportunity_id: str):
        with store.connect(False) as c:
            return list_interviews(store, c, opportunity_id)

    @api.post("/interviews/real")
    def confirm(opportunity_id: str, body: dict):
        return confirm_real(store, opportunity_id, body)

    @api.get("/interviews/{interview_id}")
    def detail(opportunity_id: str, interview_id: str):
        with store.connect(False) as c:
            return _detail(store, c, opportunity_id, interview_id)

    @api.post("/interviews/{interview_id}/upgrade")
    def upgrade(opportunity_id: str, interview_id: str, body: dict):
        return upgrade_legacy(store, opportunity_id, interview_id, body)

    for action in ("schedule", "pending", "complete", "cancel"):
        @api.post("/interviews/{interview_id}/" + action)
        def status(opportunity_id: str, interview_id: str, body: dict, _action=action):
            return _change_status(store, opportunity_id, interview_id, _action, body)

    @api.post("/interviews/{interview_id}/simulations")
    def simulation(opportunity_id: str, interview_id: str, body: dict):
        return start_simulation(store, opportunity_id, interview_id, body)

    @api.get("/interviews/{interview_id}/preparation")
    def get_preparation(opportunity_id: str, interview_id: str):
        with store.connect(False) as c:
            _, _, session = _owned(store, c, opportunity_id, interview_id, require_current=True)
            if session["type"] != "real":
                raise Conflict("Simulation 不拥有 Preparation")
            return _get_material(store, c, "interview_preparation", interview_id) or {
                "id": _material_id("interview_preparation", interview_id),
                "interview_session_id": interview_id, "revision": 0,
                "focus": "", "expected_questions": [], "priority_projects": [], "risks": [], "notes": "",
            }

    @api.put("/interviews/{interview_id}/preparation")
    def preparation(opportunity_id: str, interview_id: str, body: dict):
        return save_preparation(store, opportunity_id, interview_id, body)

    @api.get("/interviews/{interview_id}/raw")
    def get_raw(opportunity_id: str, interview_id: str):
        with store.connect(False) as c:
            _owned(store, c, opportunity_id, interview_id, require_current=True)
            return _get_material(store, c, "interview_raw", interview_id, True)

    @api.put("/interviews/{interview_id}/raw")
    def raw(opportunity_id: str, interview_id: str, body: dict):
        return save_raw(store, opportunity_id, interview_id, body)

    @api.get("/interviews/{interview_id}/final-review")
    def get_review(opportunity_id: str, interview_id: str):
        with store.connect(False) as c:
            _owned(store, c, opportunity_id, interview_id, require_current=True)
            return _get_material(store, c, "interview_final_review", interview_id, True)

    @api.put("/interviews/{interview_id}/final-review")
    def review(opportunity_id: str, interview_id: str, body: dict):
        return save_review(store, opportunity_id, interview_id, body)

    @api.post("/interviews/{interview_id}/generate-final-review")
    def generated_review(opportunity_id: str, interview_id: str, body: dict):
        return generate_final_review(store, opportunity_id, interview_id, body)

    @api.post("/interviews/{interview_id}/generate-research-patch")
    def generated_patch(opportunity_id: str, interview_id: str, body: dict):
        return generate_research_patch(store, opportunity_id, interview_id, body)

    @api.get("/research")
    def research(opportunity_id: str):
        with store.connect(False) as c:
            opportunity = op.resolve(store, c, opportunity_id)
            return _get_research(store, c, opportunity["id"])

    @api.get("/research-patches")
    def patches(opportunity_id: str):
        with store.connect(False) as c:
            opportunity = op.resolve(store, c, opportunity_id)
            result = []
            for proposal in store._records(c, "patch_proposal"):
                if proposal.get("opportunity_id") != opportunity["id"]:
                    continue
                proposal = dict(proposal)
                if proposal.get("status") == "pending":
                    try:
                        cm.validate(store, c, proposal.get("manifest"))
                    except Conflict as exc:
                        proposal.update(stale=True, stale_reason=str(exc))
                result.append(proposal)
            return result

    @api.put("/research-patches/{proposal_id}")
    def patch_edit(opportunity_id: str, proposal_id: str, body: dict):
        return edit_patch(store, opportunity_id, proposal_id, body)

    @api.post("/research-patches/{proposal_id}/resolve")
    def patch_resolve(opportunity_id: str, proposal_id: str, body: dict):
        return resolve_patch(store, opportunity_id, proposal_id, body)

    return api
