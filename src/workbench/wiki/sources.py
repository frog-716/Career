"""Resolve stable Career source identities without copying their contents."""

import json

from ..core import Conflict, Missing, digest


RAW_RECORD_KINDS = (
    "raw_material",
    "knowledge_source",
    "work_project_source",
    "work_event",
    "work_evidence",
    "journey_note",
    "interview_raw",
    "communication",
)


def _canonical_scope(store, c, scope_type, scope_id):
    from .. import opportunity as op

    if scope_type in {"personal", "cognition"}:
        return (scope_type, "") if scope_id == "" else None
    if not isinstance(scope_id, str) or not scope_id:
        return None
    if scope_type == "project":
        row = c.execute(
            "SELECT 1 FROM current WHERE id=? AND kind='work_project'", (scope_id,)
        ).fetchone()
        return (scope_type, scope_id) if row else None
    if scope_type == "employment":
        try:
            from ..work import _employment
            employment = _employment(store, c, scope_id)
            return (scope_type, employment["id"])
        except (Missing, KeyError):
            return None
    if scope_type == "person":
        row = c.execute(
            "SELECT body FROM current WHERE id=? AND kind='work_person'", (scope_id,)
        ).fetchone()
        if not row:
            return None
        person = json.loads(row[0])
        if person.get("identity_status") != "confirmed":
            return None
        return (scope_type, scope_id)
    if scope_type == "opportunity":
        try:
            return (scope_type, op.resolve(store, c, scope_id)["id"])
        except (Missing, KeyError):
            return None
    return None


def _legacy_scope(store, c, scope_type, scope_id):
    from .. import opportunity as op
    from ..work import _employment

    if scope_type in {"personal", "cognition"}:
        return (scope_type, "") if scope_id == "" else None
    if scope_type == "project":
        return _canonical_scope(store, c, "project", scope_id)
    if scope_type in {"employment", "episode"}:
        try:
            employment = _employment(store, c, scope_id)
            return ("employment", employment["id"])
        except (Missing, KeyError):
            return None
    if scope_type in {"opportunity", "job"}:
        try:
            return ("opportunity", op.resolve(store, c, scope_id)["id"])
        except (Missing, KeyError):
            return None
    if scope_type == "person":
        return _canonical_scope(store, c, scope_type, scope_id)
    return None


def _raw_value(store, c, kind, identifier):
    """Return a normalized source, or reject kinds that are not Raw material."""
    if kind == "raw_material":
        try:
            value = store._get(c, identifier, kind, record=True)
        except Missing:
            raise
        scope = _canonical_scope(store, c, value.get("scope_type"), value.get("scope_id"))
        if scope is None:
            raise Missing("原始资料不存在")
        return {
            "kind": kind, "id": value["id"], "revision": value["revision"],
            "hash": value["hash"], "title": value["title"],
            "content": value["content"], "source_kind": value["source_kind"],
            "scope_type": scope[0], "scope_id": scope[1],
            "created_at": value["created_at"], "provenance": value["provenance"],
        }

    try:
        value = store._get(c, identifier, kind, record=True)
    except Missing:
        raise

    source_kind = kind
    revision = value.get("revision", 1)
    provenance = value.get("provenance")
    if kind == "knowledge_source":
        scope = _legacy_scope(store, c, value.get("scope_type"), value.get("scope_id"))
        title, content = value.get("title"), value.get("content")
        source_kind = value.get("source_type", kind)
        provenance = provenance or ({"kind": "legacy_origin", "origin": value.get("origin")}
                                    if value.get("origin") else {"kind": "legacy_unknown"})
    elif kind == "work_project_source":
        project_id = value.get("project_id")
        if project_id:
            scope = _legacy_scope(store, c, "project", project_id)
        else:
            scope = _legacy_scope(store, c, value.get("scope_type"), value.get("scope_id", ""))
        title, content = value.get("title"), value.get("content")
        source_kind = "project_material"
        provenance = {"kind": "legacy_record"}
    elif kind == "work_event":
        target_type, target_id = value.get("target_type"), value.get("target_id")
        scope = _legacy_scope(
            store, c, "project" if target_type == "project" else "episode", target_id
        ) if target_type in {"project", "episode"} else None
        title, content = value.get("title"), value.get("content")
        source_kind = "work_event"
        provenance = {"kind": "legacy_record"}
    elif kind == "work_evidence":
        scope = _legacy_scope(store, c, value.get("scope_type"), value.get("scope_id"))
        title, content = value.get("title"), value.get("content")
        source_kind = value.get("source_type", "work_evidence")
        provenance = {"kind": "legacy_record"}
    elif kind == "journey_note":
        scope = _legacy_scope(store, c, value.get("scope_type"), value.get("scope_id"))
        title, content = value.get("title", ""), value.get("content")
        source_kind = "journey_note"
        provenance = {"kind": "user_record"}
    elif kind == "interview_raw":
        session_id = value.get("interview_session_id")
        session_row = c.execute(
            "SELECT body FROM records WHERE id=? AND kind='interview'", (session_id,)
        ).fetchone()
        if not session_row:
            raise Missing("原始资料不存在")
        session = json.loads(session_row[0])
        scope = _legacy_scope(store, c, "opportunity", session.get("opportunity_id"))
        title, content = "面试转写", value.get("content")
        source_kind = "interview_transcript"
        interview_type = session.get("type")
        if interview_type not in {"real", "simulation"}:
            interview_type = "legacy_unknown"
            source_kind = "legacy_interview_transcript"
        elif interview_type == "simulation":
            source_kind = "simulation_interview_transcript"
        else:
            source_kind = "real_interview_transcript"
        revision = value.get("revision")
        provenance = {"kind": "user_record", "interview_type": interview_type}
    elif kind == "communication":
        scope = _legacy_scope(store, c, "opportunity", value.get("opportunity_id"))
        title = value.get("type") or "沟通记录"
        content = value.get("content")
        source_kind = "communication_record"
        provenance = {
            "kind": "user_record", "purpose": value.get("purpose"),
            "occurred_on": value.get("occurred_on") or value.get("occurred_at"),
        }
    else:
        raise Missing("原始资料不存在")

    if scope is None or not isinstance(title, str) or not isinstance(content, str):
        raise Missing("原始资料不存在")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        revision = 1
    source_hash = value.get("hash")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        if kind in {"knowledge_source", "journey_note"}:
            source_hash = digest({"title": title, "content": content})
        elif kind == "communication":
            source_hash = digest({
                "type": value.get("type"), "occurred_on": value.get("occurred_on"),
                "content": content, "archived": value.get("archived", False),
            })
        elif kind in {"work_project_source", "work_event", "work_evidence"}:
            source_hash = digest(value)
        else:
            source_hash = digest({
                "kind": kind, "id": identifier, "revision": revision,
                "title": title, "content": content,
                "scope_type": scope[0], "scope_id": scope[1],
            })
    return {
        "kind": kind, "id": identifier, "revision": revision,
        "hash": source_hash, "title": title, "content": content,
        "source_kind": source_kind, "scope_type": scope[0], "scope_id": scope[1],
        "created_at": value.get("created_at") or value.get("occurred_at") or "",
        "provenance": provenance,
    }


def source_ref(source):
    return {key: source[key] for key in ("kind", "id", "revision", "hash")}


def _source_summary(source):
    return {
        "id": source["id"], "kind": source["kind"], "source_kind": source["source_kind"],
        "title": source["title"], "scope_type": source["scope_type"],
        "scope_id": source["scope_id"], "created_at": source["created_at"],
        "revision": source["revision"], "hash": source["hash"],
        "source_ref": source_ref(source),
    }


def resolve_source(store, c, kind, identifier):
    return _raw_value(store, c, kind, identifier)


def list_sources(store, c, scope_type, scope_id):
    wanted_scope = _canonical_scope(store, c, scope_type, scope_id)
    if wanted_scope is None:
        raise Missing("资料范围不存在")
    result = []
    for kind in RAW_RECORD_KINDS:
        for row in c.execute("SELECT id FROM records WHERE kind=? ORDER BY rowid DESC", (kind,)):
            try:
                value = _raw_value(store, c, kind, row[0])
            except Missing:
                continue
            try:
                validate_reference_scope(store, c, wanted_scope, value)
            except (Conflict, Missing):
                continue
            result.append(_source_summary(value))
    result.sort(key=lambda item: (item.get("created_at", ""), item["id"]), reverse=True)
    return result


def validate_reference_scope(store, c, wiki_scope, source):
    scope_type, scope_id = wiki_scope
    source_scope = (source["scope_type"], source["scope_id"])
    if source_scope == wiki_scope:
        return
    if scope_type == "person":
        from ..work import CURRENT
        person = store._get(c, scope_id, CURRENT["person"])
        employment_id = person.get("employment_id")
        if source_scope == ("employment", employment_id):
            return
    if scope_type == "cognition" and source["scope_type"] in {
        "personal", "project", "employment", "person",
    }:
        return
    if scope_type in {"project", "employment", "person"} and source["scope_type"] == "project":
        from ..work import CURRENT, _project_employment_id
        if scope_type == "project" and source["scope_id"] == scope_id:
            return
        project = store._get(c, source["scope_id"], CURRENT["project"])
        related_employment = _project_employment_id(project)
        if scope_type == "employment" and related_employment == scope_id:
            return
        if scope_type == "person":
            person = store._get(c, scope_id, CURRENT["person"])
            if related_employment and related_employment == person.get("employment_id"):
                return
    if scope_type == "project" and source["scope_type"] == "employment":
        from ..work import CURRENT, _project_employment_id
        project = store._get(c, scope_id, CURRENT["project"])
        if _project_employment_id(project) == source["scope_id"]:
            return
    raise Conflict("source_scope_conflict: 来源与 Wiki 范围不匹配")


def validate_source_refs(store, c, refs, wiki_scope, preserved_refs=()):
    from ..core import Invalid

    if not isinstance(refs, list) or len(refs) > 50:
        raise Invalid("来源最多可选择 50 条")
    normalized = []
    seen = set()
    preserved = {json.dumps(ref, sort_keys=True) for ref in preserved_refs}
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"kind", "id", "revision", "hash"}:
            raise Invalid("来源引用必须包含稳定来源、版本和摘要")
        kind, identifier = ref.get("kind"), ref.get("id")
        revision, content_hash = ref.get("revision"), ref.get("hash")
        if not isinstance(kind, str) or not kind or not isinstance(identifier, str) or not identifier:
            raise Invalid("来源引用格式不合法")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise Invalid("来源版本不合法")
        if not isinstance(content_hash, str) or len(content_hash) != 64:
            raise Invalid("来源摘要不合法")
        key = (kind, identifier)
        if key in seen:
            raise Invalid("来源不能重复")
        seen.add(key)
        key_json = json.dumps(ref, sort_keys=True)
        try:
            source = _raw_value(store, c, kind, identifier)
        except Missing:
            if key_json in preserved:
                normalized.append(ref)
                continue
            raise
        if source_ref(source) != ref:
            if key_json in preserved:
                normalized.append(ref)
                continue
            raise Conflict("source_changed: 来源已更新，请重新选择")
        try:
            validate_reference_scope(store, c, wiki_scope, source)
        except Conflict:
            if key_json in preserved:
                normalized.append(ref)
                continue
            raise
        normalized.append(source_ref(source))
    return normalized
