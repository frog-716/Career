"""Canonical current Offer actions over the legacy typed record identity."""
import json
from datetime import date

from fastapi import APIRouter

from .core import Conflict, Invalid, Missing, digest, now, required, uid
from .opportunity import business_day, canonical_id, resolve, writable


TERM_KEYS = {
    "offered_role_title", "location", "start_date", "employment_type",
    "probation", "benefits", "compensation", "other_terms",
}
COMPENSATION_KEYS = {"guaranteed_cash", "variable_cash", "equity", "one_time", "notes"}


def _strict(body, allowed):
    extra = set(body) - set(allowed)
    if extra:
        raise Invalid("不允许的Offer字段：" + ",".join(sorted(extra)))


def _expected(value, name="expected_revision"):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Invalid(name + "必须是非负整数")
    return value


def _day(value, field):
    if not isinstance(value, str) or len(value) != 10:
        raise Invalid(field + "必须是 YYYY-MM-DD")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise Invalid(field + "必须是 YYYY-MM-DD") from None


def _text(value, field, limit=20000):
    if not isinstance(value, str) or len(value) > limit:
        raise Invalid(field + "格式不正确或超出长度限制")
    return value


def validate_terms(value):
    if not isinstance(value, dict) or set(value) != TERM_KEYS:
        raise Invalid("Offer terms字段不完整或包含未知字段")
    compensation = value.get("compensation")
    if not isinstance(compensation, dict) or set(compensation) != COMPENSATION_KEYS:
        raise Invalid("Offer compensation字段不完整或包含未知字段")
    start_date = value.get("start_date")
    if start_date is not None:
        start_date = _day(start_date, "入职日期")
    return {
        "offered_role_title": _text(value["offered_role_title"], "Offer岗位名称", 500),
        "location": _text(value["location"], "工作地点", 1000),
        "start_date": start_date,
        "employment_type": _text(value["employment_type"], "用工类型", 1000),
        "probation": _text(value["probation"], "试用期", 5000),
        "benefits": _text(value["benefits"], "福利", 20000),
        "compensation": {key: _text(compensation[key], "薪酬条件", 10000)
                         for key in ("guaranteed_cash", "variable_cash", "equity", "one_time", "notes")},
        "other_terms": _text(value["other_terms"], "其它条件", 30000),
    }


def _command(store, c, action, opportunity_id, offer_id, body):
    key = required(body.get("idempotency_key"), "idempotency_key（请刷新客户端）", 200)
    command_id = "offer-command:" + digest([action, opportunity_id, offer_id, key])
    fingerprint = digest(body)
    row = c.execute("SELECT body FROM records WHERE id=? AND kind='offer_command'", (command_id,)).fetchone()
    if row:
        saved = json.loads(row[0])
        if saved["fingerprint"] != fingerprint:
            raise Conflict("请求标识已用于不同Offer操作")
        return saved, command_id, fingerprint
    return None, command_id, fingerprint


def _remember(store, c, command_id, fingerprint, action, offer, opportunity):
    store._record(c, "offer_command", {
        "id": command_id, "action": action, "fingerprint": fingerprint,
        "offer_id": offer["id"], "offer_revision": offer.get("revision", 0),
        "offer_hash": digest(offer), "opportunity_id": opportunity["id"],
        "opportunity_revision": opportunity["revision"], "created_at": now(),
    })


def _raw(store, c, offer_id):
    row = c.execute("SELECT body FROM records WHERE id=? AND kind='offer'", (offer_id,)).fetchone()
    if not row:
        raise Missing("Offer不存在")
    return json.loads(row[0])


def _owner(raw):
    value = raw.get("opportunity_id") or raw.get("job_id")
    return canonical_id(value) if isinstance(value, str) and value else None


def offer_rows(store, c, opportunity_id):
    oid = canonical_id(opportunity_id)
    return [raw for raw in store._records(c, "offer") if _owner(raw) == oid]


def _note_only(store, c, opportunity):
    alias = opportunity.get("legacy_job_id") or opportunity["id"].split(":", 1)[1]
    linked = {raw.get("raw_note_id") for raw in offer_rows(store, c, opportunity["id"])}
    return [note for note in store._records(c, "journey_note")
            if note.get("scope_type") == "job" and note.get("scope_id") == alias
            and note.get("kind") == "offer" and note.get("id") not in linked]


def dto(store, c, raw, opportunity=None):
    opportunity = opportunity or resolve(store, c, _owner(raw) or "")
    if raw.get("offer_format") == 2:
        return dict(raw, legacy=False, decision=opportunity.get("result"),
                    result_changed_at=opportunity.get("result_changed_at"))
    return {
        **raw, "offer_format": None, "terms": None,
        "legacy_terms": raw.get("terms"), "legacy_status": raw.get("status"),
        "legacy_hash": digest(raw),
        "received_on": None, "revision": raw.get("revision", 0),
        "legacy": True, "decision": opportunity.get("result"),
        "result_changed_at": opportunity.get("result_changed_at"),
    }


def _owned(store, c, opportunity_id, offer_id, canonical_only=False):
    opportunity = resolve(store, c, opportunity_id)
    raw = _raw(store, c, offer_id)
    if _owner(raw) != opportunity["id"]:
        raise Missing("Offer不存在")
    if canonical_only and raw.get("offer_format") != 2:
        raise Conflict("legacy_offer_requires_review: 历史Offer尚未核对")
    return opportunity, raw, dto(store, c, raw, opportunity)


def get_offer(store, c, opportunity_id):
    opportunity = resolve(store, c, opportunity_id)
    rows = offer_rows(store, c, opportunity["id"])
    if len(rows) > 1:
        raise Conflict("multiple_offers_require_review: 多条历史Offer尚未消歧")
    if rows:
        return dto(store, c, rows[0], opportunity)
    notes = _note_only(store, c, opportunity)
    if len(notes) > 1:
        raise Conflict("multiple_offer_notes_require_review: 多条Offer原件尚未核对")
    if notes:
        note = notes[0]
        return {"id": "legacy:" + note["id"], "offer_format": None,
                "opportunity_id": opportunity["id"], "received_on": None,
                "terms": None, "legacy_terms": None, "legacy_status": None,
                "raw_note_id": note["id"], "legacy": True, "note_only": True,
                "revision": 0, "created_at": note.get("created_at"),
                "decision": opportunity.get("result"),
                "result_changed_at": opportunity.get("result_changed_at")}
    return None


def require_canonical_offer(store, c, opportunity_id):
    offer = get_offer(store, c, opportunity_id)
    if not offer or offer.get("offer_format") != 2:
        raise Conflict("canonical_offer_required: 请先明确记录当前Offer")
    return offer


def _advance_to_offer(store, c, opportunity, offer_id, timestamp):
    row = store._get(c, opportunity["id"], "opportunity")
    row.update(phase="offer", phase_changed_on=business_day(timestamp),
               phase_source={"action": "RecordOffer", "occurred_at": timestamp},
               confirmed_offer_id=offer_id)
    return store._save(c, "opportunity", row, opportunity["revision"])


def record_offer(store, opportunity_id, body):
    _strict(body, {"received_on", "terms", "expected_opportunity_revision", "idempotency_key"})
    received_on = _day(body.get("received_on"), "Offer收到日期")
    terms = validate_terms(body.get("terms"))
    expected = _expected(body.get("expected_opportunity_revision"), "expected_opportunity_revision")
    with store.connect() as c:
        opportunity = writable(store, c, opportunity_id)
        replay, command_id, fingerprint = _command(store, c, "record", opportunity["id"], None, body)
        if replay:
            offer = dto(store, c, _raw(store, c, replay["offer_id"]))
            return {"offer": offer, "opportunity": resolve(store, c, opportunity["id"])}
        if opportunity["revision"] != expected:
            raise Conflict("机会已更新，请保留输入并重新载入")
        if opportunity["result"] != "active":
            raise Conflict("opportunity_ended: 机会已结束")
        if opportunity["phase"] not in {"submitted", "interview"}:
            raise Conflict("record_offer_requires_submitted_or_interview: 当前阶段不能记录Offer")
        if offer_rows(store, c, opportunity["id"]) or _note_only(store, c, opportunity):
            raise Conflict("offer_requires_review: 当前机会已有Offer或历史原件")
        timestamp = now()
        raw = {"id": uid(), "offer_format": 2, "opportunity_id": opportunity["id"],
               "received_on": received_on, "terms": terms,
               "created_at": timestamp, "updated_at": timestamp, "revision": 0}
        store._record(c, "offer", raw)
        saved_opportunity = _advance_to_offer(store, c, opportunity, raw["id"], timestamp)
        store._bump(c)
        offer = dto(store, c, raw, resolve(store, c, opportunity["id"]))
        current = resolve(store, c, opportunity["id"])
        _remember(store, c, command_id, fingerprint, "record", offer, current)
        return {"offer": offer, "opportunity": current}


def update_offer(store, opportunity_id, offer_id, body):
    _strict(body, {"received_on", "terms", "expected_revision", "idempotency_key"})
    received_on = _day(body.get("received_on"), "Offer收到日期")
    terms = validate_terms(body.get("terms"))
    expected = _expected(body.get("expected_revision"))
    with store.connect() as c:
        opportunity, raw, offer = _owned(store, c, opportunity_id, offer_id, True)
        replay, command_id, fingerprint = _command(store, c, "update", opportunity["id"], offer_id, body)
        if replay:
            return dto(store, c, _raw(store, c, offer_id))
        if opportunity["result"] != "active" or opportunity["phase"] != "offer":
            raise Conflict("opportunity_ended: 已结束机会不能修改Offer")
        if offer["revision"] != expected:
            raise Conflict("Offer已在其它窗口更新，请保留输入并重新载入")
        raw.update(received_on=received_on, terms=terms, updated_at=now(), revision=expected + 1)
        store._record(c, "offer", raw)
        saved = dto(store, c, raw, opportunity)
        _remember(store, c, command_id, fingerprint, "update", saved, opportunity)
        return saved


def accept_offer(store, opportunity_id, offer_id, body, compatibility=False):
    allowed = {"expected_opportunity_revision", "expected_offer_revision", "idempotency_key"}
    _strict(body, allowed)
    expected_opportunity = _expected(body.get("expected_opportunity_revision"), "expected_opportunity_revision")
    expected_offer = _expected(body.get("expected_offer_revision"), "expected_offer_revision")
    with store.connect() as c:
        try:
            opportunity, _, offer = _owned(store, c, opportunity_id, offer_id, True)
        except Missing as error:
            if not compatibility:
                raise
            raise Invalid("accepted必须引用当前Opportunity已确认的Offer") from error
        replay, command_id, fingerprint = _command(store, c, "accept", opportunity["id"], offer_id, body)
        if replay:
            return resolve(store, c, opportunity["id"])
        if opportunity["revision"] != expected_opportunity:
            raise Conflict("机会已更新，请重新载入")
        if offer["revision"] != expected_offer:
            raise Conflict("Offer条件已更新，请重新核对后接受")
        if opportunity["phase"] != "offer" or opportunity.get("confirmed_offer_id") != offer["id"]:
            raise Conflict("accept_offer_requires_current_offer: 当前Offer关系不一致")
        if opportunity["result"] != "active":
            raise Conflict("机会已结束，不能更换最终结果")
        from .opportunity import transition_result_in_transaction
        transition_result_in_transaction(store, c, opportunity, "accepted")
        store._bump(c)
        current = resolve(store, c, opportunity["id"])
        _remember(store, c, command_id, fingerprint, "accept", offer, current)
        return current


def upgrade_legacy_offer(store, opportunity_id, offer_id, body):
    _strict(body, {"received_on", "terms", "expected_opportunity_revision", "expected_legacy_hash",
                   "idempotency_key", "confirmed"})
    if body.get("confirmed") is not True:
        raise Invalid("必须明确确认历史Offer事实")
    received_on = _day(body.get("received_on"), "Offer收到日期")
    terms = validate_terms(body.get("terms"))
    expected_opportunity = _expected(body.get("expected_opportunity_revision"), "expected_opportunity_revision")
    expected_hash = required(body.get("expected_legacy_hash"), "expected_legacy_hash", 128)
    with store.connect() as c:
        opportunity, raw, offer = _owned(store, c, opportunity_id, offer_id)
        replay, command_id, fingerprint = _command(store, c, "upgrade", opportunity["id"], offer_id, body)
        if replay:
            current_offer = dto(store, c, _raw(store, c, offer_id))
            return {"offer": current_offer, "opportunity": resolve(store, c, opportunity["id"])}
        if offer.get("offer_format") == 2:
            raise Conflict("Offer已经完成核对")
        if digest(raw) != expected_hash:
            raise Conflict("历史Offer已变化，请重新核对")
        if opportunity["revision"] != expected_opportunity:
            raise Conflict("机会已更新，请重新核对")
        if opportunity["result"] != "active" or opportunity["phase"] not in {"submitted", "interview"}:
            raise Conflict("当前机会状态不能接管历史Offer")
        others = [item for item in offer_rows(store, c, opportunity["id"]) if item["id"] != offer_id]
        note_only = [item for item in _note_only(store, c, opportunity) if item["id"] != raw.get("raw_note_id")]
        if others or note_only:
            raise Conflict("multiple_offers_require_review: 多条历史Offer尚未消歧")
        timestamp = now()
        canonical = {"id": raw["id"], "offer_format": 2, "opportunity_id": opportunity["id"],
                     "received_on": received_on, "terms": terms,
                     "created_at": raw.get("created_at", timestamp),
                     "updated_at": timestamp, "revision": 0,
                     "legacy_provenance": {"original_body": raw, "original_hash": digest(raw)}}
        if raw.get("raw_note_id"):
            canonical["raw_note_id"] = raw["raw_note_id"]
        store._record(c, "offer", canonical)
        _advance_to_offer(store, c, opportunity, offer_id, timestamp)
        store._bump(c)
        current = resolve(store, c, opportunity["id"])
        saved = dto(store, c, canonical, current)
        _remember(store, c, command_id, fingerprint, "upgrade", saved, current)
        return {"offer": saved, "opportunity": current}


def router(store):
    api = APIRouter(prefix="/api/opportunities/{opportunity_id}/offer")

    @api.get("")
    def current(opportunity_id: str):
        with store.connect(False) as c:
            return get_offer(store, c, opportunity_id)

    @api.post("")
    def record(opportunity_id: str, body: dict):
        return record_offer(store, opportunity_id, body)

    @api.get("/{offer_id}")
    def detail(opportunity_id: str, offer_id: str):
        with store.connect(False) as c:
            return _owned(store, c, opportunity_id, offer_id)[2]

    @api.put("/{offer_id}")
    def update(opportunity_id: str, offer_id: str, body: dict):
        return update_offer(store, opportunity_id, offer_id, body)

    @api.post("/{offer_id}/accept")
    def accept(opportunity_id: str, offer_id: str, body: dict):
        return accept_offer(store, opportunity_id, offer_id, body)

    @api.post("/{offer_id}/upgrade")
    def upgrade(opportunity_id: str, offer_id: str, body: dict):
        return upgrade_legacy_offer(store, opportunity_id, offer_id, body)

    return api
