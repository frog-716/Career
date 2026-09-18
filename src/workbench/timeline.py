"""Read-only Opportunity Timeline projection; no Timeline facts are stored."""
import json

from fastapi import APIRouter

from .communication import list_communications
from .core import Conflict, Invalid
from .opportunity import business_day, resolve


RANK = {"opportunity_result": 6, "offer": 5, "interview": 4,
        "communication": 3, "submission": 2, "opportunity_created": 1}


def _summary(content, limit=80):
    text = " ".join(str(content or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def project(store, c, opportunity_id):
    opportunity = resolve(store, c, opportunity_id)
    created = {
        "source_type": "opportunity_created", "object_id": opportunity["id"],
        "occurred_on": opportunity.get("created_on"), "title": "加入 Career",
        "summary": opportunity.get("company", "") + " · " + opportunity.get("title", ""),
        "status": None, "target": {"kind": "opportunity", "id": opportunity["id"]},
        "_timestamp": opportunity.get("created_at", ""),
    }
    items = [created] if created["occurred_on"] else []
    unknown = [] if created["occurred_on"] else [created]
    alias = opportunity.get("legacy_job_id") or opportunity["id"].split(":", 1)[1]
    for canonical_owner, raw in c.execute("SELECT canonical_opportunity_id,body FROM applications"):
        submission = json.loads(raw)
        explicit = submission.get("opportunity_id")
        if canonical_owner != opportunity["id"] and explicit != opportunity["id"]:
            continue
        if canonical_owner is None and explicit is None and submission.get("job_id") != alias:
            continue
        material = submission.get("resume_snapshot")
        summary = "本次未使用简历" if material is None else "已冻结实际投递材料"
        items.append({
            "source_type": "submission", "object_id": submission["id"],
            "occurred_on": submission.get("submitted_on"), "title": "完成投递",
            "summary": summary, "status": None,
            "target": {"kind": "submission", "id": submission["id"]},
            "_timestamp": submission.get("recorded_at", submission.get("applied_at", "")),
        })
    raw_ids = {}
    communications = list_communications(store, c, opportunity["id"])
    for event in communications:
        note_id = event.get("raw_note_id")
        if note_id:
            raw_ids[note_id] = raw_ids.get(note_id, 0) + 1
    for event in communications:
        if event.get("raw_note_id") and raw_ids[event["raw_note_id"]] > 1:
            continue
        label = ("谈薪沟通" if event.get("purpose") == "negotiation" else
                 {"text": "线上沟通", "phone": "电话沟通", "other": "其他沟通"}.get(event.get("type"), "历史沟通 · 类型待核对"))
        item = {
            "source_type": "communication", "object_id": event["id"],
            "occurred_on": event.get("occurred_on"), "title": label,
            "summary": _summary(event.get("content")), "status": None,
            "target": {"kind": "communication", "id": event["id"]},
            "_timestamp": event.get("updated_at", event.get("created_at", "")),
        }
        (items if item["occurred_on"] else unknown).append(item)
    from .offer import get_offer
    try:
        offer = get_offer(store, c, opportunity["id"])
    except Conflict:
        offer = {"id": "legacy:multiple-offers", "legacy": True, "received_on": None,
                 "created_at": "", "note_only": False}
    if offer:
        if offer.get("legacy"):
            unknown.append({
                "source_type": "offer", "object_id": offer["id"], "occurred_on": None,
                "title": "历史 Offer · 待核对", "summary": "日期、当前条件与决定尚未确认",
                "status": None, "target": {"kind": "legacy_offer", "id": offer["id"]},
                "_timestamp": offer.get("created_at", ""),
            })
        else:
            terms = offer["terms"]
            parts = [terms.get("offered_role_title"), terms.get("location"),
                     terms.get("compensation", {}).get("guaranteed_cash")]
            summary = "当前条件：" + (" · ".join(part for part in parts if part) or "待确认")
            items.append({
                "source_type": "offer", "object_id": offer["id"],
                "occurred_on": offer.get("received_on"), "title": "收到 Offer",
                "summary": summary, "status": opportunity.get("result"),
                "target": {"kind": "offer", "id": offer["id"]},
                "_timestamp": offer.get("updated_at", offer.get("created_at", "")),
            })
    from .interview import list_interviews
    for session in list_interviews(store, c, opportunity["id"]):
        if session.get("legacy"):
            item = {
                "source_type": "interview", "object_id": session["id"],
                "occurred_on": None, "title": "历史 Interview · 待核对",
                "summary": "类型、状态与业务日期尚未确认", "status": None,
                "target": {"kind": "interview", "id": session["id"]},
                "_timestamp": session.get("created_at", ""),
            }
            unknown.append(item)
            continue
        status = session["status"]
        occurred_on = (session.get("completed_on") if status == "completed" else
                       session.get("scheduled_on") if status == "scheduled" else
                       session.get("cancelled_on") if status == "cancelled" else
                       session.get("confirmed_on"))
        review = c.execute(
            "SELECT 1 FROM records WHERE kind='interview_final_review' AND json_extract(body,'$.interview_session_id')=?",
            (session["id"],),
        ).fetchone()
        labels = {"pending": "时间待定", "scheduled": "待进行", "completed": "已完成",
                  "cancelled": "已永久取消"}
        summary = labels[status] + (" · 已复盘" if review else "")
        item = {
            "source_type": "interview", "object_id": session["id"],
            "occurred_on": occurred_on, "title": session["name"], "summary": summary,
            "status": status, "interview_type": session["type"],
            "target": {"kind": "interview", "id": session["id"]},
            "_timestamp": session.get("updated_at", session.get("created_at", "")),
        }
        (items if occurred_on else unknown).append(item)
    if not opportunity.get("read_only") and opportunity.get("result") != "active":
        changed_at = opportunity.get("result_changed_at")
        try:
            changed_on = business_day(changed_at) if changed_at else None
        except (Invalid, ValueError, AttributeError):
            changed_on = None
        titles = {"accepted": "接受 Offer", "rejected": "招聘方结束机会", "withdrawn": "主动退出"}
        result_item = {
            "source_type": "opportunity_result", "object_id": opportunity["id"],
            "occurred_on": changed_on, "title": titles.get(opportunity.get("result"), "机会结束"),
            "summary": "已结束，最后阶段：" + str(opportunity.get("phase", "")),
            "status": opportunity.get("result"),
            "target": {"kind": "opportunity", "id": opportunity["id"]},
            "_timestamp": changed_at or "",
        }
        (items if changed_on else unknown).append(result_item)
    items = sorted(items, key=lambda item: (item.get("occurred_on") or "", item["_timestamp"], RANK[item["source_type"]], item["object_id"]), reverse=True)
    unknown = sorted(unknown, key=lambda item: (item["_timestamp"], item["object_id"]), reverse=True)
    for item in items + unknown:
        item.pop("_timestamp", None)
    return {"items": items, "unknown_date_items": unknown}


def router(store):
    api = APIRouter(prefix="/api/opportunities")

    @api.get("/{opportunity_id}/timeline")
    def timeline(opportunity_id: str):
        with store.connect(False) as c:
            return project(store, c, opportunity_id)

    return api
