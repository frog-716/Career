"""User-maintained Wiki Knowledge and typed Raw-source endpoints."""

from fastapi import APIRouter

from ..core import Conflict, Invalid, Missing, digest, now, required, uid
from ..pagination import page
from . import sources


KNOWLEDGE_TYPES = {"fact", "observation", "hypothesis"}
SCOPE_TYPES = {"project", "employment", "opportunity", "person", "personal", "cognition"}
STATUSES = {"current", "retired"}


def _request(store, c, action, key, payload):
    key = required(key, "请求标识", 200)
    fingerprint = digest({"action": action, "payload": payload})
    for row in store._records(c, "wiki_d1_request"):
        if row["idempotency_key"] == key:
            if row["fingerprint"] != fingerprint:
                raise Conflict("请求标识已用于不同 Wiki 操作")
            return row["result"], key, fingerprint
    return None, key, fingerprint


def _remember(store, c, key, fingerprint, result):
    store._record(c, "wiki_d1_request", {
        "id": uid(), "idempotency_key": key, "fingerprint": fingerprint,
        "result": result, "created_at": now(),
    })


def _revision_result(c, identifier, revision):
    row = c.execute(
        "SELECT body FROM revisions WHERE id=? AND revision=?",
        (identifier, revision),
    ).fetchone()
    if not row:
        raise Missing("Wiki 修订不存在")
    import json
    return json.loads(row[0])


def _scope(store, c, scope_type, scope_id):
    if scope_type not in SCOPE_TYPES or not isinstance(scope_id, str):
        raise Invalid("Wiki 范围不合法")
    normalized = sources._canonical_scope(store, c, scope_type, scope_id)
    if normalized is None:
        if scope_type == "person":
            raise Missing("人物不存在或身份尚未确认")
        raise Missing("Wiki 范围不存在")
    return normalized


def _text(value, label, limit=100000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise Invalid(label + "不能为空或超出长度限制")
    return value


def _tags(value):
    if not isinstance(value, list) or len(value) > 100:
        raise Invalid("Tags 必须是最多 100 个标签的列表")
    result = []
    seen = set()
    for tag in value:
        if not isinstance(tag, str) or not tag.strip() or len(tag.strip()) > 100:
            raise Invalid("Tag 不能为空或超出长度限制")
        tag = tag.strip()
        if tag in seen:
            raise Invalid("Tags 不能重复")
        seen.add(tag)
        result.append(tag)
    return result


def _knowledge_values(store, c, body, scope, old=None):
    kind = body.get("knowledge_type", (old or {}).get("knowledge_type"))
    if kind not in KNOWLEDGE_TYPES:
        raise Invalid("Wiki 知识类型只能是 Fact、Observation 或 Hypothesis")
    content = _text(body.get("content", (old or {}).get("content")), "Wiki 内容")
    tags = _tags(body.get("tags", (old or {}).get("tags", [])))
    refs = body.get("source_refs", (old or {}).get("source_refs", []))
    refs = sources.validate_source_refs(
        store, c, refs, scope, (old or {}).get("source_refs", ()),
    )
    status = body.get("status", (old or {}).get("status", "current"))
    if status not in STATUSES:
        raise Invalid("Wiki 状态只能是当前或已退役")
    return {
        "knowledge_type": kind, "content": content, "tags": tags,
        "source_refs": refs, "status": status,
    }


def _raw_with_pending_counts(store, c, scope, raw_items):
    """Display only: count unresolved patches for this exact business scope."""
    ids = {item["id"] for item in raw_items if item["kind"] == "raw_material"}
    counts = {identifier: 0 for identifier in ids}
    target = {"scope_type": scope[0], "scope_id": scope[1]}
    for proposal in store._records(c, "wiki_compiler_proposal"):
        raw_id = proposal.get("raw_id")
        if (proposal.get("status") != "pending" or raw_id not in counts
                or proposal.get("target_scope") != target):
            continue
        counts[raw_id] += sum(
            patch.get("status") == "pending" for patch in proposal.get("patches", ())
        )
    return [dict(item, pending_patch_count=counts.get(item["id"], 0))
            for item in raw_items]


def _source_catalog(store, c, items):
    """Titles for the visible Wiki page only; never include Raw bodies."""
    catalog = []
    seen = set()
    for item in items:
        for ref in item.get("source_refs", ()):
            if not isinstance(ref, dict) or not all(
                name in ref for name in ("kind", "id", "revision", "hash")
            ):
                continue
            key = (ref.get("kind"), ref.get("id"), ref.get("revision"), ref.get("hash"))
            if key in seen:
                continue
            seen.add(key)
            try:
                source = sources.resolve_source(store, c, key[0], key[1])
            except (Missing, Conflict):
                continue
            catalog.append({
                "source_ref": {name: ref[name] for name in ("kind", "id", "revision", "hash")},
                "kind": source["kind"], "title": source["title"],
                "source_kind": source["source_kind"],
                "version_changed": (source["revision"], source["hash"]) != key[2:],
            })
    return catalog


def raw_wiki_router(store):
    router = APIRouter()

    @router.get("/api/raw")
    def list_raw(scope_type: str, scope_id: str = ""):
        with store.connect(False) as c:
            scope = _scope(store, c, scope_type, scope_id)
            items = sources.list_sources(store, c, scope[0], scope[1])
            return {"items": _raw_with_pending_counts(store, c, scope, items)}

    @router.get("/api/raw/{source_kind}/{source_id}")
    def get_raw(
        source_kind: str, source_id: str,
        revision: int | None = None, hash: str | None = None,
    ):
        with store.connect(False) as c:
            value = sources.resolve_source(store, c, source_kind, source_id)
            if revision is not None and revision != value["revision"]:
                raise Conflict("source_changed: 这份原始资料已更新，旧版本没有可回放的正文")
            if hash is not None and hash != value["hash"]:
                raise Conflict("source_changed: 来源摘要不匹配，不能显示为原版本")
            return dict(value, source_ref=sources.source_ref(value))

    @router.post("/api/raw")
    def create_raw(body: dict):
        allowed = {"scope_type", "scope_id", "source_kind", "title", "content", "idempotency_key"}
        if set(body) - allowed:
            raise Invalid("原始资料包含不允许的字段")
        title = required(body.get("title"), "标题", 500)
        content = _text(body.get("content"), "原始资料")
        source_kind = body.get("source_kind")
        if source_kind != "manual_text":
            raise Invalid("本阶段只接收用户手工输入的文本")
        with store.connect() as c:
            scope = _scope(store, c, body.get("scope_type"), body.get("scope_id"))
            payload = {
                "scope_type": scope[0], "scope_id": scope[1],
                "source_kind": source_kind, "title": title, "content": content,
            }
            previous, key, fingerprint = _request(
                store, c, "create_raw", body.get("idempotency_key"), payload,
            )
            if previous is not None:
                replay = sources.resolve_source(store, c, "raw_material", previous["raw_id"])
                return dict(replay, source_ref=sources.source_ref(replay))
            timestamp = now()
            value = dict(
                id=uid(), kind="raw_material", **payload, revision=1,
                hash=digest(payload), provenance={"kind": "user"},
                created_at=timestamp,
            )
            store._record(c, "raw_material", value)
            result = dict(value, source_ref=sources.source_ref(value))
            _remember(store, c, key, fingerprint, {"raw_id": value["id"]})
            return result

    @router.get("/api/wiki")
    def list_knowledge(
        scope_type: str = "all", scope_id: str = "", status: str = "current",
        limit: int | None = None, cursor: str | None = None,
        include_source_titles: bool = False,
    ):
        if status not in {"current", "retired", "all"}:
            raise Invalid("Wiki 状态筛选不合法")
        with store.connect(False) as c:
            if scope_type == "all":
                if scope_id:
                    raise Invalid("全部范围不能指定目标")
                normalized_scope = None
            else:
                normalized_scope = _scope(store, c, scope_type, scope_id)
            items = store._current(c, "wiki_knowledge")
            if normalized_scope:
                items = [item for item in items if
                         (item["scope_type"], item["scope_id"]) == normalized_scope]
            else:
                # Opportunity knowledge is private to an explicit opportunity
                # view; the general Wiki view must not preload it.
                items = [item for item in items if item["scope_type"] != "opportunity"]
            if status != "all":
                items = [item for item in items if item["status"] == status]
            scope_key = f"wiki:{scope_type}:{scope_id}:{status}"
            result = page(items, scope=scope_key, limit=limit, cursor=cursor)
            if include_source_titles:
                visible = result["items"] if isinstance(result, dict) else result
                return dict(result, source_catalog=_source_catalog(store, c, visible)) \
                    if isinstance(result, dict) else {
                        "items": result, "source_catalog": _source_catalog(store, c, visible),
                    }
            return result

    @router.get("/api/wiki/workspace")
    def wiki_workspace(scope_type: str, scope_id: str):
        with store.connect(False) as c:
            scope = _scope(store, c, scope_type, scope_id)
            knowledge = [item for item in store._current(c, "wiki_knowledge")
                         if (item["scope_type"], item["scope_id"]) == scope]
            current = [item for item in knowledge if item["status"] == "current"]
            retired = [item for item in knowledge if item["status"] == "retired"]
            raw_items = _raw_with_pending_counts(
                store, c, scope, sources.list_sources(store, c, scope[0], scope[1]),
            )
            return {"knowledge": current, "retired": retired, "raw": raw_items}

    @router.post("/api/wiki")
    def create_knowledge(body: dict):
        allowed = {
            "scope_type", "scope_id", "knowledge_type", "content", "tags",
            "source_refs", "idempotency_key",
        }
        if set(body) - allowed:
            raise Invalid("Wiki 知识包含不允许的字段")
        with store.connect() as c:
            request_payload = {key: value for key, value in body.items() if key != "idempotency_key"}
            previous, key, fingerprint = _request(
                store, c, "create_knowledge", body.get("idempotency_key"), request_payload,
            )
            if previous is not None:
                return _revision_result(c, previous["knowledge_id"], previous["revision"])
            scope = _scope(store, c, body.get("scope_type"), body.get("scope_id"))
            values = _knowledge_values(store, c, body, scope)
            payload = {"scope_type": scope[0], "scope_id": scope[1], **values}
            value = store._save(c, "wiki_knowledge", dict(
                id=uid(), **payload, provenance={"kind": "user"}, created_at=now(),
            ), 0)
            _remember(store, c, key, fingerprint, {
                "knowledge_id": value["id"], "revision": value["revision"],
            })
            return value

    @router.post("/api/wiki/{knowledge_id}")
    def update_knowledge(knowledge_id: str, body: dict):
        allowed = {
            "knowledge_type", "content", "tags", "source_refs", "status",
            "expected_revision", "idempotency_key",
        }
        if set(body) - allowed:
            raise Invalid("Wiki 修改包含不允许的字段")
        expected = body.get("expected_revision")
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
            raise Invalid("expected_revision 不合法")
        with store.connect() as c:
            request_payload = {
                "knowledge_id": knowledge_id, "expected_revision": expected,
                "request": {key: value for key, value in body.items() if key != "idempotency_key"},
            }
            previous, key, fingerprint = _request(
                store, c, "update_knowledge", body.get("idempotency_key"), request_payload,
            )
            if previous is not None:
                return _revision_result(c, previous["knowledge_id"], previous["revision"])
            old = store._get(c, knowledge_id, "wiki_knowledge")
            scope = _scope(store, c, old["scope_type"], old["scope_id"])
            values = _knowledge_values(store, c, body, scope, old)
            value = store._save(c, "wiki_knowledge", dict(old, **values), expected)
            _remember(store, c, key, fingerprint, {
                "knowledge_id": value["id"], "revision": value["revision"],
            })
            return value

    @router.get("/api/wiki/{knowledge_id}/history")
    def knowledge_history(knowledge_id: str):
        with store.connect(False) as c:
            store._get(c, knowledge_id, "wiki_knowledge")
            rows = c.execute(
                "SELECT body FROM revisions WHERE id=? ORDER BY revision", (knowledge_id,)
            ).fetchall()
            return {"revisions": [__import__("json").loads(row[0]) for row in rows]}

    return router
