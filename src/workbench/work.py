"""Explicit work-domain objects layered on the compatible journey records."""
import json
from datetime import date

from fastapi import APIRouter

from .core import Conflict, Invalid, Missing, digest, now, required, uid


CURRENT = {
    "project": "work_project",
    "person": "work_person",
    "achievement": "work_achievement",
    "stage": "work_employment_stage",
}
IMMUTABLE = {
    "source": "work_project_source",
    "event": "work_event",
    "evidence": "work_evidence",
    "participant": "work_project_participant",
    "evidence_link": "work_evidence_link",
}


def _text(value, field, limit=100000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise Invalid(field + "不能为空或超出长度限制")
    return value.strip()


def _expected(value):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Invalid("expected_revision 不合法")
    return value


def _date_value(value, field):
    if value in (None, ""):
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


def _employment(store, c, employment_id):
    if not isinstance(employment_id, str) or not employment_id:
        raise Invalid("任职标识不合法")
    ident = employment_id if employment_id.startswith("employment:") else "employment:" + employment_id
    row = c.execute("SELECT body FROM current WHERE id=? AND kind='employment'", (ident,)).fetchone()
    if row:
        return json.loads(row[0])
    legacy_id = ident.split(":", 1)[1]
    episode = store._get(c, legacy_id, "journey_episode")
    return dict(id=ident, legacy_episode_id=legacy_id, company=episode["company"], role=episode["role"],
                start_date=episode.get("start_date"), end_date=episode.get("end_date"),
                focus=episode.get("focus", ""), revision=episode.get("revision", 0),
                created_at=episode.get("created_at"))


def _stage_values(body, employment):
    name = _text(body.get("name"), "阶段名称", 500)
    start = _date_value(body.get("start_date"), "阶段开始日期")
    end = _date_value(body.get("end_date"), "阶段结束日期")
    if start and end and end < start:
        raise Invalid("阶段结束日期不能早于开始日期")
    if employment.get("start_date") and start and start < employment["start_date"]:
        raise Invalid("阶段开始日期不能早于任职开始日期")
    if employment.get("end_date") and end and end > employment["end_date"]:
        raise Invalid("阶段结束日期不能晚于任职结束日期")
    focus = body.get("focus", "")
    if not isinstance(focus, str) or len(focus) > 100000:
        raise Invalid("阶段重点超出长度限制")
    status = body.get("status", "active")
    if status not in {"planned", "active", "completed", "paused"}:
        raise Invalid("阶段状态不合法")
    return dict(name=name, start_date=start, end_date=end, focus=focus, status=status)


def _request(store, c, key, action, payload):
    key = required(key, "请求标识", 200)
    fingerprint = digest({"action": action, "payload": payload})
    row = c.execute("SELECT body FROM records WHERE kind='work_request' AND json_extract(body,'$.key')=?", (key,)).fetchone()
    if row:
        old = json.loads(row[0])
        if old["fingerprint"] != fingerprint:
            raise Conflict("请求标识已用于不同工作域操作")
        return old["result"], key, fingerprint
    return None, key, fingerprint


def _remember(store, c, key, fingerprint, result):
    store._record(c, "work_request", {"id": uid(), "key": key, "fingerprint": fingerprint,
                                       "result": result, "created_at": now()})


def _scope(store, c, scope_type, scope_id, allowed):
    if scope_type not in allowed or not isinstance(scope_id, str):
        raise Invalid("工作资料范围不合法")
    if scope_type == "personal":
        if scope_id != "":
            raise Invalid("个人范围的 scope_id 必须为空")
    elif scope_type == "episode":
        store._get(c, required(scope_id, "任职范围", 500), "journey_episode")
    elif scope_type == "employment":
        ident = required(scope_id, "任职范围", 500)
        try:
            store._get(c, ident, "employment")
        except Missing:
            if not ident.startswith("employment:"):
                raise
            episode = store._get(c, ident.split(":", 1)[1], "journey_episode")
            from .employment import sync_episode
            sync_episode(store, c, episode)
    elif scope_type == "project":
        store._get(c, required(scope_id, "项目范围", 500), "work_project")
    return scope_type, scope_id


def _target(store, c, body, allow_project=True):
    episode_id = body.get("episode_id")
    project_id = body.get("project_id")
    if bool(episode_id) == bool(project_id) or (project_id and not allow_project):
        raise Invalid("必须明确一个任职或项目目标")
    if episode_id:
        store._get(c, required(episode_id, "任职目标", 500), "journey_episode")
        return "episode", episode_id
    store._get(c, required(project_id, "项目目标", 500), "work_project")
    return "project", project_id


def _create_current(store, c, kind, body, values):
    obj = dict(id=uid(), **values, created_at=now())
    result = store._save(c, CURRENT[kind], obj, 0)
    return result


def work_router(store):
    router = APIRouter()

    @router.get("/api/work-domain")
    def read_domain():
        with store.connect(False) as c:
            from .employment import current_employments
            return {
                "employments": current_employments(store, c),
                "stages": store._current(c, CURRENT["stage"]),
                "projects": store._current(c, CURRENT["project"]),
                "sources": store._records(c, IMMUTABLE["source"]),
                "persons": store._current(c, CURRENT["person"]),
                "participants": store._records(c, IMMUTABLE["participant"]),
                "events": store._records(c, IMMUTABLE["event"]),
                "achievements": store._current(c, CURRENT["achievement"]),
                "evidence": store._records(c, IMMUTABLE["evidence"]),
                "evidence_links": store._records(c, IMMUTABLE["evidence_link"]),
            }

    @router.post("/api/work/employments/{employment_id}/stages")
    def create_stage(employment_id: str, body: dict):
        with store.connect() as c:
            employment = _employment(store, c, employment_id)
            values = _stage_values(body, employment)
            payload = dict(employment_id=employment["id"], **values)
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "create_stage", payload)
            if previous is not None:
                return previous
            result = _create_current(store, c, "stage", body, payload)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.post("/api/work/stages/{stage_id}")
    def update_stage(stage_id: str, body: dict):
        expected = _expected(body.get("expected_revision"))
        with store.connect() as c:
            old = store._get(c, stage_id, CURRENT["stage"])
            employment = _employment(store, c, old["employment_id"])
            values = _stage_values(body, employment)
            payload = dict(stage_id=stage_id, expected_revision=expected, **values)
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "update_stage", payload)
            if previous is not None:
                return previous
            result = store._save(c, CURRENT["stage"], dict(old, **values), expected)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.post("/api/work/projects")
    def create_project(body: dict):
        name = _text(body.get("name"), "项目名称", 500)
        description = body.get("description", "")
        if not isinstance(description, str) or len(description) > 100000:
            raise Invalid("项目说明超出长度限制")
        scope_type = body.get("scope_type")
        scope_id = body.get("scope_id", "")
        with store.connect() as c:
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "create_project", body)
            if previous is not None:
                return previous
            if scope_type is not None:
                _scope(store, c, scope_type, scope_id, {"personal", "episode", "employment"})
            result = _create_current(store, c, "project", body, dict(name=name, description=description,
                scope_type=scope_type, scope_id=scope_id if scope_type else ""))
            _remember(store, c, key, fingerprint, result)
            return result

    @router.post("/api/work/projects/{project_id}")
    def update_project(project_id: str, body: dict):
        expected = _expected(body.get("expected_revision"))
        name = _text(body.get("name"), "项目名称", 500)
        description = body.get("description", "")
        if not isinstance(description, str) or len(description) > 100000:
            raise Invalid("项目说明超出长度限制")
        with store.connect() as c:
            old = store._get(c, project_id, CURRENT["project"])
            payload = dict(project_id=project_id, expected_revision=expected, name=name, description=description)
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "update_project", payload)
            if previous is not None:
                return previous
            result = store._save(c, CURRENT["project"], dict(old, name=name, description=description), expected)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.post("/api/work/sources")
    def create_source(body: dict):
        title = _text(body.get("title"), "来源标题", 500)
        content = _text(body.get("content"), "来源内容")
        semantics = _text(body.get("semantics"), "来源语义", 10000)
        project_id = body.get("project_id")
        with store.connect() as c:
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "create_source", body)
            if previous is not None:
                return previous
            if project_id is not None:
                store._get(c, required(project_id, "项目", 500), CURRENT["project"])
            scope_type, scope_id = _scope(store, c, body.get("scope_type"), body.get("scope_id", ""), {"personal", "episode", "employment"})
            result = dict(id=uid(), project_id=project_id, scope_type=scope_type, scope_id=scope_id,
                          title=title, content=content, semantics=semantics, created_at=now())
            store._record(c, IMMUTABLE["source"], result)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.post("/api/work/persons")
    def create_person(body: dict):
        name = _text(body.get("name"), "人物姓名", 500)
        role = body.get("role", "")
        if not isinstance(role, str) or len(role) > 500:
            raise Invalid("人物角色超出长度限制")
        with store.connect() as c:
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "create_person", body)
            if previous is not None:
                return previous
            result = _create_current(store, c, "person", body, dict(name=name, role=role))
            _remember(store, c, key, fingerprint, result)
            return result

    @router.post("/api/work/projects/{project_id}/participants")
    def add_participant(project_id: str, body: dict):
        person_id = required(body.get("person_id"), "人物", 500)
        with store.connect() as c:
            store._get(c, project_id, CURRENT["project"])
            person = store._get(c, person_id, CURRENT["person"])
            payload = dict(project_id=project_id, person_id=person_id, role=body.get("role", ""))
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "add_participant", payload)
            if previous is not None:
                return previous
            if not isinstance(payload["role"], str) or len(payload["role"]) > 500:
                raise Invalid("参与角色超出长度限制")
            exists = c.execute("SELECT body FROM records WHERE kind=? AND json_extract(body,'$.project_id')=? AND json_extract(body,'$.person_id')=?", (IMMUTABLE["participant"], project_id, person_id)).fetchone()
            if exists:
                raise Conflict("项目与人物已经建立参与关系")
            result = dict(id=uid(), project_id=project_id, person_id=person_id,
                          person_revision=person["revision"], role=payload["role"], created_at=now())
            store._record(c, IMMUTABLE["participant"], result)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.post("/api/work/events")
    def create_event(body: dict):
        title = _text(body.get("title"), "事件标题", 500)
        content = _text(body.get("content"), "事件原文")
        kind = _text(body.get("kind"), "事件类型", 100)
        with store.connect() as c:
            target_type, target_id = _target(store, c, body)
            payload = dict(title=title, content=content, kind=kind, target_type=target_type, target_id=target_id)
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "create_event", payload)
            if previous is not None:
                return previous
            result = dict(id=uid(), **payload, created_at=now())
            store._record(c, IMMUTABLE["event"], result)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.post("/api/work/achievements")
    def create_achievement(body: dict):
        title = _text(body.get("title"), "成果标题", 500)
        content = _text(body.get("content"), "成果内容")
        project_id = body.get("project_id")
        with store.connect() as c:
            if project_id is not None:
                store._get(c, required(project_id, "项目", 500), CURRENT["project"])
            payload = dict(title=title, content=content, project_id=project_id)
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "create_achievement", payload)
            if previous is not None:
                return previous
            result = _create_current(store, c, "achievement", body, payload)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.post("/api/work/achievements/{achievement_id}")
    def update_achievement(achievement_id: str, body: dict):
        expected = _expected(body.get("expected_revision"))
        title = _text(body.get("title"), "成果标题", 500)
        content = _text(body.get("content"), "成果内容")
        with store.connect() as c:
            old = store._get(c, achievement_id, CURRENT["achievement"])
            payload = dict(achievement_id=achievement_id, expected_revision=expected, title=title, content=content)
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "update_achievement", payload)
            if previous is not None:
                return previous
            result = store._save(c, CURRENT["achievement"], dict(old, title=title, content=content), expected)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.post("/api/work/evidence")
    def create_evidence(body: dict):
        title = _text(body.get("title"), "证据标题", 500)
        content = _text(body.get("content"), "证据原文")
        source_type = _text(body.get("source_type"), "证据类型", 100)
        with store.connect() as c:
            scope_type, scope_id = _scope(store, c, body.get("scope_type"), body.get("scope_id", ""), {"personal", "episode", "employment", "project"})
            payload = dict(title=title, content=content, source_type=source_type, scope_type=scope_type, scope_id=scope_id)
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "create_evidence", payload)
            if previous is not None:
                return previous
            result = dict(id=uid(), **payload, created_at=now())
            store._record(c, IMMUTABLE["evidence"], result)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.post("/api/work/evidence-links")
    def link_evidence(body: dict):
        achievement_id = required(body.get("achievement_id"), "成果", 500)
        evidence_id = required(body.get("evidence_id"), "证据", 500)
        with store.connect() as c:
            achievement = store._get(c, achievement_id, CURRENT["achievement"])
            evidence = store._get(c, evidence_id, IMMUTABLE["evidence"], True)
            payload = dict(achievement_id=achievement_id, evidence_id=evidence_id)
            previous, key, fingerprint = _request(store, c, body.get("idempotency_key"), "link_evidence", payload)
            if previous is not None:
                return previous
            if evidence.get("scope_type") == "project" and achievement.get("project_id") != evidence.get("scope_id"):
                raise Invalid("项目证据必须与成果属于同一项目")
            exists = c.execute("SELECT body FROM records WHERE kind=? AND json_extract(body,'$.achievement_id')=? AND json_extract(body,'$.evidence_id')=?", (IMMUTABLE["evidence_link"], achievement_id, evidence_id)).fetchone()
            if exists:
                raise Conflict("成果与证据已经建立关系")
            result = dict(id=uid(), **payload, achievement_revision=achievement["revision"], evidence_created_at=evidence["created_at"], created_at=now())
            store._record(c, IMMUTABLE["evidence_link"], result)
            _remember(store, c, key, fingerprint, result)
            return result

    return router
