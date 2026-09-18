"""Journey records: job plans, work episodes, and immutable manual notes."""
import json
from datetime import date

from fastapi import APIRouter
from fastapi.responses import Response

from .core import Conflict, Invalid, Missing, digest, dump, now, required, uid


STAGES = {"screening", "research", "resume", "outreach", "applied", "interview", "offer", "closed"}
NOTE_SCOPES = {"job", "episode"}
NOTE_KINDS = {"research", "communication", "interview", "offer", "action", "collaboration", "reflection"}


def _date(value, field):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise Invalid(field + "必须是 YYYY-MM-DD 或为空")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise Invalid(field + "必须是 YYYY-MM-DD 或为空") from None
    if len(value) != 10:
        raise Invalid(field + "必须是 YYYY-MM-DD 或为空")
    return value


def _expected(value):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Invalid("expected_revision 不合法")
    return value


def _text(value, field, limit, strip=True):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise Invalid(field + "不能为空或超出长度限制")
    return value.strip() if strip else value


def _episode_values(body):
    company = required(body.get("company"), "公司", 500)
    role = required(body.get("role"), "角色", 500)
    start = _date(body.get("start_date"), "开始日期")
    end = _date(body.get("end_date"), "结束日期")
    if start and end and end < start:
        raise Invalid("结束日期不能早于开始日期")
    focus = body.get("focus", "")
    if not isinstance(focus, str) or len(focus) > 100000:
        raise Invalid("重点内容超出长度限制")
    return company, role, start, end, focus


def _plan_values(body):
    stage = body.get("stage")
    if not isinstance(stage, str) or stage not in STAGES:
        raise Invalid("阶段不合法")
    next_action = _text(body.get("next_action"), "下一行动", 100000)
    due = _date(body.get("due_date"), "截止日期")
    return stage, next_action, due


def _note_view(store, c, note):
    """Return the note with its correction overlay; the record itself stays immutable."""
    revision_id = "note-revision:" + note["id"]
    row = c.execute("SELECT body FROM current WHERE id=? AND kind='journey_note_revision'", (revision_id,)).fetchone()
    correction = json.loads(row[0]) if row else None
    return dict(note,
                title=correction["title"] if correction else note["title"],
                content=correction["content"] if correction else note["content"],
                note_revision=correction["revision"] if correction else 0,
                original_title=note["title"], original_content=note["content"])


def _request(store, c, key, action, payload):
    key = required(key, "请求标识", 200)
    fingerprint = digest({"action": action, "payload": payload})
    row = c.execute("SELECT body FROM records WHERE kind='journey_request' AND json_extract(body,'$.idempotency_key')=?", (key,)).fetchone()
    if row:
        old = json.loads(row[0])
        if old["fingerprint"] != fingerprint:
            raise Conflict("请求标识已用于不同记录整理")
        return old["result"], key, fingerprint
    return None, key, fingerprint


def _remember(store, c, key, fingerprint, result):
    store._record(c, "journey_request", {"id": uid(), "idempotency_key": key,
                                          "fingerprint": fingerprint, "result": result,
                                          "created_at": now()})


def _submission_for_note(store, c, note, submission_id):
    if submission_id is None:
        return
    if note["scope_type"] != "job":
        raise Invalid("只有岗位记录可以关联投递")
    if not isinstance(submission_id, str) or not submission_id:
        raise Invalid("submission_id 不合法")
    row = c.execute("SELECT body FROM applications WHERE id=?", (submission_id,)).fetchone()
    if not row:
        raise Missing("投递不存在")
    submission = json.loads(row[0])
    if submission.get("job_id") != note["scope_id"]:
        raise Invalid("投递与记录不属于同一岗位")
    return submission


def journey_router(store):
    router = APIRouter()

    @router.get("/api/journey/episodes/{episode_id}/export")
    def export_episode(episode_id: str):
        with store.connect(False) as c:
            episode = store._get(c, episode_id, "journey_episode")
            notes = sorted((n for n in store._records(c, "journey_note")
                            if n["scope_type"] == "episode" and n["scope_id"] == episode_id),
                           key=lambda n: n["created_at"])
            snapshots = []
            for note in notes:
                view = _note_view(store, c, note)
                rows = c.execute("SELECT body FROM revisions WHERE id=? ORDER BY revision", ("note-revision:" + note["id"],)).fetchall()
                snapshots.append((note, view, [json.loads(row[0]) for row in rows]))
            text = "# " + episode["company"] + " · " + episode["role"] + "\n\n"
            text += "阶段：" + (episode["start_date"] or "未设置") + " — " + (episode["end_date"] or "至今") + "\n\n"
            text += "重点：\n" + episode["focus"] + "\n\n## 用户记录汇编（非 AI 总结）\n\n"
            for note, view, history in snapshots:
                text += "### " + (view["title"] or "未命名记录") + " · " + note["created_at"] + "\n\n"
                text += "当前更正视图：\n" + view["content"] + "\n\n"
                text += "原始记录（不可变）：\n" + note["content"] + "\n\n"
                if history:
                    text += "更正历史：\n"
                    for revision in history:
                        text += "- revision " + str(revision["revision"]) + " · " + revision["created_at"] + " · " + revision["title"] + "：\n"
                        text += revision["content"] + "\n"
                    text += "\n"
        return Response(text, media_type="text/markdown",
                        headers={"Content-Disposition": 'attachment; filename="career-stage.md"'})

    @router.get("/api/journey")
    def journey():
        with store.connect(False) as c:
            return {
                "plans": store._current(c, "journey_plan"),
                "episodes": store._current(c, "journey_episode"),
                "notes": [_note_view(store, c, n) for n in store._records(c, "journey_note")],
            }

    @router.post("/api/journey/notes/{note_id}/correct")
    def correct_note(note_id: str, body: dict):
        expected = _expected(body.get("expected_revision"))
        title = body.get("title", "")
        if not isinstance(title, str) or len(title) > 500:
            raise Invalid("标题超出长度限制")
        content = _text(body.get("content"), "内容", 100000, strip=False)
        with store.connect() as c:
            note = store._get(c, note_id, "journey_note", True)
            if note.get("scope_type") == "job" and c.execute(
                "SELECT 1 FROM records WHERE kind IN ('communication','interview') AND json_extract(body,'$.raw_note_id')=?",
                (note_id,),
            ).fetchone():
                raise Conflict("domain_action_required: 请在对应 Communication / Interview Detail 中更正")
            payload = dict(note_id=note_id, expected_revision=expected, title=title, content=content)
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "correct_note", payload)
            if previous is not None:
                return previous
            current_id = "note-revision:" + note_id
            row = c.execute("SELECT revision FROM current WHERE id=?", (current_id,)).fetchone()
            current_revision = row[0] if row else 0
            if expected != current_revision:
                raise Conflict("记录已在其它窗口更正，请重新载入")
            correction = store._save(c, "journey_note_revision", dict(
                id=current_id, note_id=note_id, title=title, content=content,
                created_at=now()), expected)
            result = _note_view(store, c, note)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.get("/api/journey/notes/{note_id}/history")
    def note_history(note_id: str):
        with store.connect(False) as c:
            note = store._get(c, note_id, "journey_note", True)
            rows = c.execute("SELECT body FROM revisions WHERE id=? ORDER BY revision", ("note-revision:" + note_id,)).fetchall()
            revisions = [{"revision": 0, "title": note["title"], "content": note["content"], "created_at": note["created_at"]}]
            revisions.extend({k: value[k] for k in ("revision", "title", "content", "created_at")}
                             for value in (json.loads(row[0]) for row in rows))
            return {"revisions": revisions}

    @router.post("/api/journey/notes/{note_id}/candidate")
    def note_candidate(note_id: str, body: dict):
        expected = _expected(body.get("expected_revision"))
        title = _text(body.get("title"), "标题", 500, strip=True)
        content = _text(body.get("content"), "内容", 100000)
        entry_type = body.get("entry_type")
        if not isinstance(entry_type, str) or entry_type not in {"goal", "constraint", "experience", "capability", "project", "achievement", "person", "growth", "strategy"}:
            raise Invalid("候选条目类型不合法")
        promote = body.get("promote_to_personal", False)
        if not isinstance(promote, bool):
            raise Invalid("promote_to_personal 必须是布尔值")
        with store.connect() as c:
            note = store._get(c, note_id, "journey_note", True)
            if note.get("scope_type") == "job" and c.execute(
                "SELECT 1 FROM records WHERE kind='interview' AND json_extract(body,'$.raw_note_id')=?",
                (note_id,),
            ).fetchone():
                raise Conflict("interview_action_required: Interview 来源不能从旧 Candidate 入口产生 Patch")
            fixed_submission = note.get("submission_id")
            requested_submission = body.get("submission_id")
            if requested_submission is not None and requested_submission != fixed_submission:
                raise Conflict("候选不能更换原记录关联的投递")
            _submission_for_note(store, c, note, fixed_submission)
            effective_submission = fixed_submission
            scope_type = body.get("scope_type")
            scope_id = body.get("scope_id")
            payload = dict(note_id=note_id, expected_revision=expected, title=title, content=content,
                           entry_type=entry_type, scope_type=scope_type, scope_id=scope_id,
                           promote_to_personal=promote, submission_id=effective_submission)
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "note_candidate", payload)
            if previous is not None:
                return previous
            revision_id = "note-revision:" + note_id
            row = c.execute("SELECT revision FROM current WHERE id=?", (revision_id,)).fetchone()
            actual = row[0] if row else 0
            if expected != actual:
                raise Conflict("记录已在其它窗口更正，请重新载入")
            if promote:
                if scope_type != "personal" or scope_id != "":
                    raise Invalid("提升个人范围时必须明确使用 personal 且 scope_id 为空")
            elif (scope_type, scope_id) != (note["scope_type"], note["scope_id"]):
                raise Invalid("未明确提升时只能使用原记录范围")
            if scope_type not in {"personal", "job", "episode"}:
                raise Invalid("候选范围不合法")
            if scope_type == "job":
                store.job_view(c,scope_id)
            elif scope_type == "episode":
                store._get(c, scope_id, "journey_episode")
            elif scope_id != "":
                raise Invalid("个人范围的 scope_id 必须为空")
            source_id = uid()
            source_hash = digest({"title": title, "content": content})
            note_view = _note_view(store, c, note)
            origin_hash = digest({"title": note_view["title"], "content": note_view["content"]})
            source = dict(id=source_id, title=title, content=content, source_type="text", locator=note_id,
                          scope_type=scope_type, scope_id=scope_id, hash=source_hash,
                          origin=dict(kind="journey_note", id=note_id, revision=actual, hash=origin_hash,
                                      scope_type=note["scope_type"], scope_id=note["scope_id"]), created_at=now())
            store._record(c, "knowledge_source", source)
            candidate = store._save(c, "knowledge_candidate", dict(
                id=uid(), status="pending", entry_id=None, source_ids=[source_id],
                entry_type=entry_type, title=title, content=content,
                scope_type=scope_type, scope_id=scope_id, created_at=now(),
                origin=source["origin"], submission_id=effective_submission), 0)
            _remember(store, c, key, fingerprint, candidate)
            return candidate

    @router.post("/api/journey/plans/{job_id}")
    def save_plan(job_id: str, body: dict):
        from .opportunity import active
        expected = _expected(body.get('expected_revision'))
        with store.connect() as c:
            opportunity = active(store,c,job_id)
            alias = opportunity.get('legacy_job_id') or opportunity['id'].split(':',1)[1]
            rows=c.execute("SELECT body FROM current WHERE kind='journey_plan' AND json_extract(body,'$.job_id')=?",(alias,)).fetchall()
            if len(rows)>1: raise Conflict('存在多个历史计划，不能自动选择')
            old=json.loads(rows[0][0]) if rows else {}
            if 'stage' in body and not isinstance(body['stage'],str):raise Invalid('阶段值不合法')
            if 'stage' in body and body['stage']!=old.get('stage'): raise Conflict('legacy_stage_retired: 计划不能改变机会阶段')
            if set(body)-{'expected_revision','stage','next_action','due_date'}: raise Invalid('计划只接受下一步和提醒日期')
            next_action=_text(body.get('next_action',''),'下一步',1000)
            due=_date(body.get('due_date'),'提醒日期')
            obj=dict(old,id=old.get('id','journey:'+alias),job_id=alias,next_action=next_action,due_date=due)
            return store._save(c,'journey_plan',obj,expected)

    @router.post("/api/journey/episodes")
    def create_episode(body: dict):
        company, role, start, end, focus = _episode_values(body)
        timestamp = now()
        obj = dict(id=uid(), revision=0, company=company, role=role, start_date=start, end_date=end,
                   focus=focus, created_at=timestamp, updated_at=timestamp)
        with store.connect() as c:
            c.execute("INSERT INTO current VALUES(?,?,?,?)", (obj["id"], "journey_episode", 0, dump(obj)))
            from .employment import sync_episode
            sync_episode(store, c, obj)
        return obj

    @router.post("/api/journey/episodes/{episode_id}")
    def update_episode(episode_id: str, body: dict):
        company, role, start, end, focus = _episode_values(body)
        expected = _expected(body.get("expected_revision"))
        with store.connect() as c:
            old = store._get(c, episode_id, "journey_episode")
            obj = dict(old, company=company, role=role, start_date=start, end_date=end, focus=focus)
            saved = store._save(c, "journey_episode", obj, expected)
            from .employment import sync_episode
            sync_episode(store, c, saved)
            return saved

    @router.post("/api/journey/notes")
    def create_note(body: dict):
        scope_type = body.get("scope_type")
        if not isinstance(scope_type, str) or scope_type not in NOTE_SCOPES:
            raise Invalid("记录范围不合法")
        scope_id = required(body.get("scope_id"), "目标", 500)
        if scope_type == "job":scope_id=scope_id.removeprefix("opportunity:")
        kind = body.get("kind")
        if not isinstance(kind, str) or kind not in NOTE_KINDS:
            raise Invalid("记录类型不合法")
        title = body.get("title", "")
        if not isinstance(title, str) or len(title) > 500:
            raise Invalid("标题超出长度限制")
        content = _text(body.get("content"), "内容", 100000, strip=False)
        key = required(body.get("idempotency_key"), "请求标识", 200)
        submission_id = body.get("submission_id")
        request = dict(scope_type=scope_type, scope_id=scope_id, kind=kind, title=title, content=content,
                       submission_id=submission_id)
        with store.connect() as c:
            existing = c.execute("SELECT body FROM records WHERE kind='journey_note' AND json_extract(body,'$.idempotency_key')=?", (key,)).fetchone()
            if existing:
                old = json.loads(existing[0])
                if any(old.get(k) != request[k] for k in request):
                    raise Conflict("请求标识已用于不同记录")
                return _note_view(store, c, old)
            if scope_type == "job":
                from .opportunity import active
                if kind == "communication":
                    raise Conflict("communication_action_required: 请在Opportunity中记录沟通")
                if kind in {'interview','offer'}:raise Conflict('lifecycle_action_pending: 隔离v2等待真实轮次/Offer动作接管')
                active(store,c,scope_id)
            else:
                store._get(c, scope_id, "journey_episode")
            _submission_for_note(store, c, dict(scope_type=scope_type, scope_id=scope_id), submission_id)
            timestamp = now()
            obj = dict(id=uid(), scope_type=scope_type, scope_id=scope_id, kind=kind, title=title,
                       content=content, submission_id=submission_id, idempotency_key=key, created_at=timestamp)
            store._record(c, "journey_note", obj)
            if scope_type == "job" and kind in {"research", "communication", "interview", "offer"}:
                from .engagement import create_activity
                create_activity(store, c, kind, dict(body, idempotency_key=key, _raw_note=obj))
            return _note_view(store, c, obj)

    return router
