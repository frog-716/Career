"""Canonical Communication actions over the existing typed record identity."""
import json
from datetime import date, datetime

from fastapi import APIRouter

from .core import Conflict, Invalid, Missing, digest, dump, now, required, uid
from .opportunity import canonical_id, resolve, writable


TYPES = {"text", "phone", "other"}
PURPOSES = {"general", "negotiation"}


def _strict(body, allowed):
    extra = set(body) - set(allowed)
    if extra:
        raise Invalid("不允许的沟通字段：" + ",".join(sorted(extra)))


def _expected(value):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Invalid("expected_revision 必须是非负整数")
    return value


def _values(body):
    communication_type = body.get("type")
    if communication_type not in TYPES:
        raise Invalid("沟通类型只能是 text、phone 或 other")
    occurred_on = body.get("occurred_on")
    if not isinstance(occurred_on, str) or len(occurred_on) != 10:
        raise Invalid("沟通日期必须是 YYYY-MM-DD")
    try:
        date.fromisoformat(occurred_on)
    except ValueError:
        raise Invalid("沟通日期必须是 YYYY-MM-DD") from None
    content = body.get("content")
    if not isinstance(content, str) or not content.strip() or len(content) > 100000:
        raise Invalid("沟通内容不能为空或超出长度限制")
    return communication_type, occurred_on, content


def _legacy_day(value):
    if not isinstance(value, str):
        return None
    try:
        if len(value) == 10:
            return date.fromisoformat(value).isoformat()
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _command(store, c, action, opportunity_id, communication_id, body):
    key = required(body.get("idempotency_key"), "idempotency_key（请刷新客户端）", 200)
    ident = "communication-command:" + digest([action, opportunity_id, communication_id, key])
    fingerprint = digest(body)
    row = c.execute("SELECT body FROM records WHERE id=? AND kind='communication_command'", (ident,)).fetchone()
    if row:
        saved = json.loads(row[0])
        if saved["fingerprint"] != fingerprint:
            raise Conflict("请求标识已用于不同沟通操作")
        return saved["result"], ident, fingerprint
    return None, ident, fingerprint


def _remember(store, c, ident, fingerprint, event):
    result = {"id": event["id"], "revision": event["revision"], "archived": event["archived"]}
    store._record(c, "communication_command", {
        "id": ident, "fingerprint": fingerprint, "result": result, "created_at": now(),
    })
    return event


def _raw(store, c, communication_id):
    row = c.execute("SELECT body FROM records WHERE id=? AND kind='communication'", (communication_id,)).fetchone()
    if not row:
        raise Missing("沟通不存在")
    return json.loads(row[0])


def _legacy_content(store, c, raw):
    note_id = raw.get("raw_note_id")
    if not note_id:
        return raw.get("content", ""), False
    row = c.execute("SELECT body FROM records WHERE id=? AND kind='journey_note'", (note_id,)).fetchone()
    if not row:
        return raw.get("content", ""), True
    from .journey import _note_view
    return _note_view(store, c, json.loads(row[0]))["content"], False


def dto(store, c, raw):
    if raw.get("communication_format") == 2:
        return dict(raw, purpose=raw.get("purpose", "general"), legacy=False, legacy_source_missing=False)
    content, missing = _legacy_content(store, c, raw)
    return dict(raw, communication_format=None, type=None, purpose=None,
                occurred_on=_legacy_day(raw.get("occurred_at")), content=content,
                revision=raw.get("revision", 0), archived=raw.get("archived", False),
                archived_at=raw.get("archived_at"), legacy=True,
                legacy_source_missing=missing)


def _owned(store, c, opportunity_id, communication_id, include_archived=False, require_writable=False):
    opportunity = (writable if require_writable else resolve)(store, c, opportunity_id)
    raw = _raw(store, c, communication_id)
    owner = raw.get("opportunity_id")
    if not isinstance(owner, str) or canonical_id(owner) != opportunity["id"]:
        raise Missing("沟通不存在")
    event = dto(store, c, raw)
    if event["archived"] and not include_archived:
        raise Missing("沟通不存在")
    return opportunity, raw, event


def list_communications(store, c, opportunity_id, include_archived=False):
    opportunity = resolve(store, c, opportunity_id)
    events = []
    for raw in store._records(c, "communication"):
        owner = raw.get("opportunity_id")
        if not isinstance(owner, str) or canonical_id(owner) != opportunity["id"]:
            continue
        event = dto(store, c, raw)
        if include_archived or not event["archived"]:
            events.append(event)
    return sorted(events, key=lambda item: (item.get("occurred_on") or "", item.get("created_at") or "", item["id"]), reverse=True)


def create_communication(store, opportunity_id, body):
    _strict(body, {"type", "purpose", "occurred_on", "content", "idempotency_key"})
    communication_type, occurred_on, content = _values(body)
    purpose = body.get("purpose", "general")
    if purpose not in PURPOSES:
        raise Invalid("沟通目的只能是 general 或 negotiation")
    with store.connect() as c:
        opportunity = writable(store, c, opportunity_id)
        replay, command_id, fingerprint = _command(store, c, "create", opportunity["id"], None, body)
        if replay is not None:
            return dto(store, c, _raw(store, c, replay["id"]))
        if opportunity["result"] != "active":
            raise Conflict("opportunity_ended: 机会已结束")
        if purpose == "general" and opportunity["phase"] != "submitted":
            raise Conflict("communication_requires_submitted: 只有已投递机会可以新增普通招聘沟通")
        if purpose == "negotiation":
            if opportunity["phase"] != "offer":
                raise Conflict("negotiation_requires_offer: 只有Offer阶段可以新增谈薪沟通")
            from .offer import require_canonical_offer
            require_canonical_offer(store, c, opportunity["id"])
        timestamp = now()
        event = {
            "id": uid(), "communication_format": 2, "opportunity_id": opportunity["id"],
            "type": communication_type, "purpose": purpose,
            "occurred_on": occurred_on, "content": content,
            "created_at": timestamp, "updated_at": timestamp, "revision": 0,
            "archived": False, "archived_at": None,
        }
        store._record(c, "communication", event)
        return _remember(store, c, command_id, fingerprint, dto(store, c, event))


def update_communication(store, opportunity_id, communication_id, body):
    _strict(body, {"type", "occurred_on", "content", "expected_revision", "idempotency_key"})
    communication_type, occurred_on, content = _values(body)
    expected = _expected(body.get("expected_revision"))
    with store.connect() as c:
        opportunity = writable(store, c, opportunity_id)
        replay, command_id, fingerprint = _command(store, c, "update", opportunity["id"], communication_id, body)
        if replay is not None:
            return dto(store, c, _raw(store, c, replay["id"]))
        _, raw, event = _owned(store, c, opportunity["id"], communication_id, require_writable=True)
        if event["revision"] != expected:
            raise Conflict("沟通已在其它窗口更新，请保留输入并重新载入")
        raw.update(communication_format=2, opportunity_id=opportunity["id"], type=communication_type,
                   occurred_on=occurred_on, content=content, updated_at=now(), revision=expected + 1,
                   archived=False, archived_at=None)
        raw.setdefault("created_at", now())
        store._record(c, "communication", raw)
        return _remember(store, c, command_id, fingerprint, dto(store, c, raw))


def archive_communication(store, opportunity_id, communication_id, body):
    _strict(body, {"expected_revision", "idempotency_key"})
    expected = _expected(body.get("expected_revision"))
    with store.connect() as c:
        opportunity = writable(store, c, opportunity_id)
        replay, command_id, fingerprint = _command(store, c, "archive", opportunity["id"], communication_id, body)
        if replay is not None:
            return dto(store, c, _raw(store, c, replay["id"]))
        _, raw, event = _owned(store, c, opportunity["id"], communication_id)
        if event["revision"] != expected:
            raise Conflict("沟通已在其它窗口更新，请重新载入")
        timestamp = now()
        raw.update(revision=expected + 1, archived=True, archived_at=timestamp, updated_at=timestamp)
        store._record(c, "communication", raw)
        return _remember(store, c, command_id, fingerprint, dto(store, c, raw))


def router(store):
    api = APIRouter(prefix="/api/opportunities/{opportunity_id}/communications")

    @api.get("")
    def listing(opportunity_id: str):
        with store.connect(False) as c:
            return list_communications(store, c, opportunity_id)

    @api.post("")
    def create(opportunity_id: str, body: dict):
        return create_communication(store, opportunity_id, body)

    @api.get("/{communication_id}")
    def detail(opportunity_id: str, communication_id: str):
        with store.connect(False) as c:
            return _owned(store, c, opportunity_id, communication_id)[2]

    @api.put("/{communication_id}")
    def update(opportunity_id: str, communication_id: str, body: dict):
        return update_communication(store, opportunity_id, communication_id, body)

    @api.post("/{communication_id}/delete")
    def archive(opportunity_id: str, communication_id: str, body: dict):
        return archive_communication(store, opportunity_id, communication_id, body)

    return api
