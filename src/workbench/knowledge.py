"""Manual source intake, confirmation, and scoped Wiki packet selection."""
import json

from fastapi import APIRouter

from .core import Conflict, Invalid, digest, now, required, uid


SOURCE_TYPES = {"text", "document", "local_repository", "git_repository", "url"}
SCOPE_TYPES = {"personal", "job", "episode"}
ENTRY_TYPES = {
    "goal", "constraint", "experience", "capability", "project",
    "achievement", "person", "growth", "strategy",
}
ENTRY_STATUSES = {"active", "withdrawn"}


def _text(value, field, limit=100000, strip=False):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise Invalid(field + "不能为空或超出长度限制")
    return value.strip() if strip else value


def _expected(value, optional=False):
    if optional and value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Invalid("expected_revision 不合法")
    return value


def _scope(store, c, scope_type, scope_id):
    if not isinstance(scope_type, str) or scope_type not in SCOPE_TYPES:
        raise Invalid("资料范围不合法")
    if not isinstance(scope_id, str) or len(scope_id) > 500:
        raise Invalid("范围目标不合法")
    if scope_type == "personal":
        if scope_id != "":
            raise Invalid("个人范围的 scope_id 必须为空")
    else:
        scope_id = required(scope_id, "范围目标", 500)
        store.job_view(c, scope_id) if scope_type == "job" else store._get(c, scope_id, "journey_episode")
    return scope_type, scope_id


def _source_ids(value):
    if (not isinstance(value, list) or not value or len(value) > 30
            or any(not isinstance(item, str) or not item for item in value)
            or len(set(value)) != len(value)):
        raise Invalid("source_ids 必须是 1 至 30 个不重复来源 ID")
    return value


def _entry_values(body):
    entry_type = body.get("entry_type")
    if not isinstance(entry_type, str) or entry_type not in ENTRY_TYPES:
        raise Invalid("Wiki 条目类型不合法")
    title = _text(body.get("title"), "标题", 500, strip=True)
    content = _text(body.get("content"), "内容")
    return entry_type, title, content


def _validate_source_scope(store, c, source_ids, scope_type, scope_id):
    for source_id in source_ids:
        source = store._get(c, source_id, "knowledge_source", True)
        if (source["scope_type"], source["scope_id"]) != (scope_type, scope_id):
            raise Invalid("Wiki 内容范围必须与所有原始来源完全一致")


def _request(store, c, key, action, payload):
    key = required(key, "请求标识", 200)
    fingerprint = digest({"action": action, "payload": payload})
    for record in store._records(c, "knowledge_request"):
        if record["idempotency_key"] == key:
            if record["fingerprint"] != fingerprint:
                raise Conflict("请求标识已用于不同知识库操作")
            return record["result"], key, fingerprint
    return None, key, fingerprint


def _remember(store, c, key, fingerprint, result):
    store._record(c, "knowledge_request", {
        "id": uid(), "idempotency_key": key, "fingerprint": fingerprint,
        "result": result, "created_at": now(),
    })


def _candidate_payload(store, c, body):
    source_ids = _source_ids(body.get("source_ids"))
    entry_type, title, content = _entry_values(body)
    scope_type, scope_id = _scope(store, c, body.get("scope_type"), body.get("scope_id"))
    _validate_source_scope(store, c, source_ids, scope_type, scope_id)
    return dict(source_ids=source_ids, entry_type=entry_type, title=title, content=content,
                scope_type=scope_type, scope_id=scope_id)


def selected_wiki_sources(store, c, ids, job_id):
    """Select current Wiki entries only; callers supply the open transaction."""
    if ids is not None:
        if (not isinstance(ids, list) or len(ids) > 30
                or any(not isinstance(item, str) or not item for item in ids)
                or len(set(ids)) != len(ids)):
            raise Invalid("wiki_ids 必须是不超过 30 个不重复条目 ID")
    if job_id is not None:
        if not isinstance(job_id, str) or not job_id:
            raise Invalid("岗位 ID 不合法")
        store.job_view(c, job_id)

    selected = []
    seen = set()
    mandatory = [entry for entry in store._current(c, "wiki_entry")
                 if entry["status"] == "active" and entry["scope_type"] == "personal"
                 and entry["entry_type"] in {"goal", "constraint"}]
    mandatory.sort(key=lambda entry: (entry.get("created_at", ""), entry["id"]))
    for entry in mandatory:
        selected.append(entry)
        seen.add(entry["id"])

    for entry_id in ids or []:
        if entry_id in seen:
            continue
        entry = store._get(c, entry_id, "wiki_entry")
        if entry.get("status") != "active":
            raise Invalid("所选 Wiki 条目已撤回")
        if entry.get("scope_type") == "episode":
            raise Invalid("任职范围 Wiki 不可用于求职分析")
        if entry.get("scope_type") == "job" and entry.get("scope_id") != job_id:
            raise Invalid("所选 Wiki 条目不属于当前岗位")
        if entry.get("scope_type") not in {"personal", "job"}:
            raise Invalid("所选 Wiki 条目范围不合法")
        selected.append(entry)
        seen.add(entry_id)

    if len(selected) > 30:
        raise Invalid("Wiki 选材超过 30 条限制")
    if sum(len(entry["content"]) for entry in selected) > 100000:
        raise Invalid("Wiki 选材正文超过 100000 字符限制")
    return [{
        "id": entry["id"],
        "revision": entry["revision"],
        "hash": digest({"title": entry["title"], "entry_type": entry["entry_type"],
                        "content": entry["content"], "scope_type": entry["scope_type"],
                        "scope_id": entry["scope_id"]}),
        "purpose": "current_fact" if entry["scope_type"] == "personal" else "task_context",
        "content": {"title": entry["title"], "entry_type": entry["entry_type"],
                    "content": entry["content"], "scope_type": entry["scope_type"],
                    "scope_id": entry["scope_id"]},
        "source_ids": entry["source_ids"],
    } for entry in selected]


def knowledge_router(store):
    router = APIRouter()

    @router.get("/api/knowledge")
    def knowledge():
        with store.connect(False) as c:
            return {
                "sources": store._records(c, "knowledge_source"),
                "candidates": store._current(c, "knowledge_candidate"),
                "entries": store._current(c, "wiki_entry"),
            }

    @router.post("/api/knowledge/sources")
    def create_source(body: dict):
        title = _text(body.get("title"), "标题", 500, strip=True)
        content = _text(body.get("content"), "内容")
        source_type = body.get("source_type")
        if not isinstance(source_type, str) or source_type not in SOURCE_TYPES:
            raise Invalid("来源类型不合法")
        locator = body.get("locator", "")
        if not isinstance(locator, str) or len(locator) > 10000:
            raise Invalid("来源定位信息不合法")
        with store.connect() as c:
            scope_type, scope_id = _scope(store, c, body.get("scope_type"), body.get("scope_id"))
            payload = dict(title=title, content=content, source_type=source_type, locator=locator,
                           scope_type=scope_type, scope_id=scope_id)
            previous, key, fingerprint = _request(
                store, c, body.get("idempotency_key"), "create_source", payload)
            if previous is not None:
                return previous
            obj = dict(id=uid(), created_at=now(), **payload)
            store._record(c, "knowledge_source", obj)
            _remember(store, c, key, fingerprint, obj)
            return obj

    @router.post("/api/knowledge/candidates")
    def create_candidate(body: dict):
        expected = _expected(body.get("expected_revision"), optional=True)
        if expected != 0:
            raise Conflict("新候选的 expected_revision 必须为 0")
        with store.connect() as c:
            payload = _candidate_payload(store, c, body)
            previous, key, fingerprint = _request(
                store, c, body.get("idempotency_key"), "create_candidate", payload)
            if previous is not None:
                return previous
            timestamp = now()
            obj = dict(id=uid(), status="pending", entry_id=None, created_at=timestamp, **payload)
            obj = store._save(c, "knowledge_candidate", obj, 0)
            _remember(store, c, key, fingerprint, obj)
            return obj

    @router.post("/api/knowledge/candidates/{candidate_id}")
    def edit_candidate(candidate_id: str, body: dict):
        expected = _expected(body.get("expected_revision"))
        with store.connect() as c:
            payload = _candidate_payload(store, c, body)
            request_payload = dict(candidate_id=candidate_id, expected_revision=expected, **payload)
            previous, key, fingerprint = _request(
                store, c, body.get("idempotency_key"), "edit_candidate", request_payload)
            if previous is not None:
                return previous
            old = store._get(c, candidate_id, "knowledge_candidate")
            if old["status"] != "pending":
                raise Conflict("仅待确认候选可以编辑")
            obj = store._save(c, "knowledge_candidate", dict(old, **payload), expected)
            _remember(store, c, key, fingerprint, obj)
            return obj

    @router.post("/api/knowledge/candidates/{candidate_id}/resolve")
    def resolve_candidate(candidate_id: str, body: dict):
        decision = body.get("decision")
        if not isinstance(decision, str) or decision not in {"confirm", "reject"}:
            raise Invalid("候选处理决定不合法")
        expected = _expected(body.get("expected_revision"))
        request_payload = dict(candidate_id=candidate_id, decision=decision,
                               expected_revision=expected)
        with store.connect() as c:
            previous, key, fingerprint = _request(
                store, c, body.get("idempotency_key"), "resolve_candidate", request_payload)
            if previous is not None:
                return previous
            candidate = store._get(c, candidate_id, "knowledge_candidate")
            if candidate["status"] != "pending":
                raise Conflict("候选已处理")
            if candidate["revision"] != expected:
                raise Conflict("候选已在其它窗口更新，请重新载入")
            entry = None
            if decision == "confirm":
                entry = store._save(c, "wiki_entry", {
                    "id": uid(), "title": candidate["title"], "content": candidate["content"],
                    "entry_type": candidate["entry_type"], "scope_type": candidate["scope_type"],
                    "scope_id": candidate["scope_id"], "source_ids": candidate["source_ids"],
                    "status": "active", "verification": "user_asserted", "created_at": now(),
                }, 0)
            candidate = store._save(c, "knowledge_candidate", dict(
                candidate, status="confirmed" if decision == "confirm" else "rejected",
                entry_id=entry["id"] if entry else None, resolved_at=now()), expected)
            if decision == "confirm":
                store._bump(c)
            _remember(store, c, key, fingerprint, candidate)
            return candidate

    @router.post("/api/knowledge/entries/{entry_id}")
    def edit_entry(entry_id: str, body: dict):
        entry_type, title, content = _entry_values(body)
        status = body.get("status")
        if not isinstance(status, str) or status not in ENTRY_STATUSES:
            raise Invalid("Wiki 条目状态不合法")
        expected = _expected(body.get("expected_revision"))
        with store.connect() as c:
            old = store._get(c, entry_id, "wiki_entry")
            source_ids = old["source_ids"]
            if "source_ids" in body:
                source_ids = _source_ids(body.get("source_ids"))
                _validate_source_scope(store, c, source_ids, old["scope_type"], old["scope_id"])
            obj = store._save(c, "wiki_entry", dict(
                old, title=title, content=content, entry_type=entry_type,
                status=status, source_ids=source_ids, verification="user_asserted"), expected)
            store._bump(c)
            return obj

    @router.get("/api/knowledge/entries/{entry_id}/history")
    def entry_history(entry_id: str):
        with store.connect(False) as c:
            store._get(c, entry_id, "wiki_entry")
            rows = c.execute(
                "SELECT body FROM revisions WHERE id=? ORDER BY revision", (entry_id,)).fetchall()
            return {"revisions": [json.loads(row[0]) for row in rows]}

    return router
