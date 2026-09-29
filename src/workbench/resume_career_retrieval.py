"""Bounded local Career search for Resume AI; models receive no store access."""

import re
import json

from .core import Conflict, Invalid
from .employment import current_employments


_MAX_QUERY = 200
_MAX_CANDIDATES = 12
_MAX_KNOWLEDGE = 8
_MAX_KNOWLEDGE_CHARS = 12000


def _allowed_scope(item, opportunity_id):
    scope = item.get("scope_type")
    return scope in {"personal", "cognition", "project", "employment"} or (
        scope == "opportunity" and item.get("scope_id") == opportunity_id
    )


def _current_allowed_wiki(connection, opportunity_id):
    """Filter private Opportunity Wiki in SQLite before materializing any body."""
    rows = connection.execute(
        "SELECT body FROM current WHERE kind='wiki_knowledge' "
        "AND json_extract(body, '$.status')='current' "
        "AND (json_extract(body, '$.scope_type') IN ('personal','cognition','project','employment') "
        "OR (json_extract(body, '$.scope_type')='opportunity' "
        "AND json_extract(body, '$.scope_id')=?)) ORDER BY rowid DESC",
        (opportunity_id,),
    )
    return [json.loads(row[0]) for row in rows]


def _terms(query):
    if not isinstance(query, str) or not query.strip() or len(query) > _MAX_QUERY:
        raise Invalid("检索词不能为空或超出长度限制")
    parts = re.findall(r"[A-Za-z0-9+#.-]+|[\u3400-\u9fff]+", query.casefold())
    terms = set()
    for part in parts:
        if re.fullmatch(r"[\u3400-\u9fff]+", part) and len(part) > 2:
            terms.add(part)
            terms.update(part[index:index + 2] for index in range(len(part) - 1))
        else:
            terms.add(part)
    return terms


def search_candidates(store, connection, opportunity_id, query, *, limit=8):
    """Search current objects locally and return only IDs/revisions, never bodies."""
    if not isinstance(opportunity_id, str) or not opportunity_id:
        raise Invalid("机会标识不合法")
    if type(limit) is not int or not 1 <= limit <= _MAX_CANDIDATES:
        raise Invalid("检索数量超出限制")
    terms = _terms(query)
    ranked = []

    def consider(kind, item, text):
        haystack = text.casefold()
        score = sum(len(term) for term in terms if term in haystack)
        if score:
            ranked.append((-score, kind, item["id"], {
                "kind": kind, "id": item["id"], "revision": item["revision"],
            }))

    for item in _current_allowed_wiki(connection, opportunity_id):
        if item.get("status") != "current" or not _allowed_scope(item, opportunity_id):
            continue
        consider("wiki_knowledge", item, " ".join([
            item.get("content", ""), *item.get("tags", []),
        ]))
    for item in store._current(connection, "work_project"):
        consider("work_project", item, " ".join([
            item.get("name", ""), item.get("description", ""), *item.get("tags", []),
        ]))
    for item in current_employments(store, connection):
        consider("employment", item, " ".join([
            item.get("company", ""), item.get("role", ""), item.get("focus", ""),
        ]))
    ranked.sort()
    return [item for _, _, _, item in ranked[:limit]]


def read_selected_knowledge(store, connection, opportunity_id, candidates, selected_ids):
    """Read only current Wiki explicitly chosen from a search result."""
    if not isinstance(candidates, list) or len(candidates) > _MAX_CANDIDATES:
        raise Invalid("检索候选范围不合法")
    if not isinstance(selected_ids, list) or len(selected_ids) > _MAX_KNOWLEDGE or any(not isinstance(identifier, str) for identifier in selected_ids) or len(set(selected_ids)) != len(selected_ids):
        raise Invalid("选中知识数量不合法")
    available = {
        item.get("id"): item.get("revision") for item in candidates
        if isinstance(item, dict) and item.get("kind") == "wiki_knowledge"
    }
    if any(not isinstance(identifier, str) or identifier not in available for identifier in selected_ids):
        raise Invalid("只能读取本轮检索到的 Wiki 知识")
    result = []
    chars = 0
    for identifier in selected_ids:
        item = store._get(connection, identifier, "wiki_knowledge")
        if item.get("revision") != available[identifier] or item.get("status") != "current":
            raise Conflict("检索到的知识已变化，请重新检索")
        if not _allowed_scope(item, opportunity_id):
            raise Invalid("知识不属于当前可读取范围")
        content = item.get("content")
        if not isinstance(content, str):
            raise Invalid("Wiki 内容不合法")
        chars += len(content)
        if chars > _MAX_KNOWLEDGE_CHARS:
            raise Invalid("选中知识超出本次预算，请缩小范围")
        result.append({
            "id": item["id"], "revision": item["revision"],
            "scope_type": item["scope_type"], "scope_id": item["scope_id"],
            "knowledge_type": item["knowledge_type"], "content": content,
            "source_refs": [
                {key: ref[key] for key in ("kind", "id", "revision", "hash")}
                for ref in item.get("source_refs", [])
            ],
        })
    return result


def read_selected_context(store, connection, opportunity_id, candidates, selected_ids, queries):
    """Expand chosen Career IDs into small current DTOs; never read Raw bodies."""
    if not isinstance(candidates, list) or len(candidates) > _MAX_CANDIDATES:
        raise Invalid("检索候选范围不合法")
    if not isinstance(selected_ids, list) or not 1 <= len(selected_ids) <= 8 or any(not isinstance(identifier, str) for identifier in selected_ids) or len(set(selected_ids)) != len(selected_ids):
        raise Invalid("选中候选数量不合法")
    by_id = {item.get("id"): item for item in candidates if isinstance(item, dict)}
    if any(identifier not in by_id for identifier in selected_ids):
        raise Invalid("只能读取本轮检索到的候选经历")
    sources = []
    knowledge_ids = []
    terms = set()
    for query in queries:
        terms.update(_terms(query))
    all_knowledge = [item for item in _current_allowed_wiki(connection, opportunity_id)
                     if item.get("status") == "current" and _allowed_scope(item, opportunity_id)]

    def include_related(scope_type, scope_id):
        matches = []
        for item in all_knowledge:
            if (item.get("scope_type"), item.get("scope_id")) != (scope_type, scope_id):
                continue
            text = (item.get("content", "") + " " + " ".join(item.get("tags", []))).casefold()
            score = sum(len(term) for term in terms if term in text)
            if score:
                matches.append((-score, item["id"]))
        for _, identifier in sorted(matches)[:3]:
            knowledge_ids.append(identifier)

    for identifier in selected_ids:
        candidate = by_id[identifier]
        kind = candidate.get("kind")
        if kind == "wiki_knowledge":
            current = store._get(connection, identifier, kind)
            if current['revision'] != candidate.get('revision') or current.get('status') != 'current':
                raise Conflict('Wiki 候选已变化，请重新检索')
            knowledge_ids.append(identifier)
        elif kind == "work_project":
            item = store._get(connection, identifier, kind)
            if item["revision"] != candidate.get("revision"):
                raise Conflict("项目候选已变化，请重新检索")
            sources.append({"kind": kind, "id": identifier, "revision": item["revision"],
                            "purpose": "career_project", "selected_content": {
                                "name": item["name"], "tags": item.get("tags", []),
                                "status": item.get("status", "active"),
                            }})
            include_related("project", identifier)
        elif kind == "employment":
            from .work import _employment
            item = _employment(store, connection, identifier)
            if item["revision"] != candidate.get("revision"):
                raise Conflict("任职候选已变化，请重新检索")
            sources.append({"kind": kind, "id": identifier, "revision": item["revision"],
                            "purpose": "career_employment", "selected_content": {
                                "company": item["company"], "role": item["role"],
                                "start_date": item.get("start_date") or "",
                                "end_date": item.get("end_date") or "",
                            }})
            include_related("employment", identifier)
        else:
            raise Invalid("候选经历类型不在 Resume 范围内")
    unique_ids = list(dict.fromkeys(knowledge_ids))
    if len(unique_ids) > _MAX_KNOWLEDGE:
        raise Invalid("关联知识超出预算，请缩小候选范围")
    wiki_candidates = [{"kind": "wiki_knowledge", "id": item["id"], "revision": item["revision"]}
                       for item in all_knowledge if item["id"] in unique_ids]
    wiki = read_selected_knowledge(store, connection, opportunity_id, wiki_candidates, unique_ids)
    sources.extend({"kind": "wiki_knowledge", "id": item["id"], "revision": item["revision"],
                    "purpose": "career_wiki", "selected_content": {
                        key: item[key] for key in ("scope_type", "scope_id", "knowledge_type", "content", "source_refs")
                    }} for item in wiki)
    return sources
