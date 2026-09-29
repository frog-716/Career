"""Context dependency manifests used by Research and Resume proposals."""
import json

from .core import Conflict, Invalid, digest


POLICY_VERSION = "career-context-v1"


def selected_opportunity(opportunity):
    return {
        "company_id": opportunity.get("company_id"),
        "company": opportunity.get("company"),
        "title": opportunity.get("title"),
        "jd": opportunity.get("jd", ""),
        "action_url": opportunity.get("action_url", ""),
    }


def dependency(kind, identifier, revision, value, purpose, *, content_hash=None, expected_absent=False, owner_id=None):
    if expected_absent:
        revision, content_hash = None, None
    elif content_hash is None:
        content_hash = digest(value)
    result = {
        "kind": kind, "id": identifier, "revision": revision,
        "content_hash": content_hash, "purpose": purpose,
    }
    if owner_id is not None:
        result["owner_id"] = owner_id
    if expected_absent:
        result["expected_absent"] = True
    return result


def manifest(task_type, target, target_revision, dependencies):
    if not isinstance(task_type, str) or not task_type:
        raise Invalid("manifest task_type 不合法")
    if not isinstance(target, dict) or not isinstance(target.get("kind"), str) or not isinstance(target.get("id"), str):
        raise Invalid("manifest target 不合法")
    return {
        "manifest_version": 1,
        "task_type": task_type,
        "target": target,
        "target_revision": target_revision,
        "dependencies": list(dependencies),
        "policy_version": POLICY_VERSION,
    }


def _fail(code, message):
    raise Conflict(code + ": " + message)


def _current_research(store, c, kind, identifier):
    from .research_store import lookup
    return lookup(store, c, kind, identifier)


def _check_target(store, c, target, expected_revision):
    kind, identifier = target.get("kind"), target.get("id")
    if kind in {"company_research", "opportunity_research"}:
        current, exists = _current_research(store, c, kind, identifier if kind == "company_research" else target.get("opportunity_id", identifier))
        if target.get("expected_absent"):
            if exists:
                _fail("target_changed", "Research 档案已经创建")
            return
        if not exists or current["id"] != identifier or current["revision"] != expected_revision:
            _fail("target_changed", "Research 目标已变化")
        return
    if kind == "opportunity":
        from . import opportunity as op
        current = op.resolve(store, c, identifier)
        if current.get("revision") != expected_revision:
            _fail("target_changed", "Opportunity 已变化")
        return
    if kind == "resume_document":
        row = c.execute("SELECT revision FROM current WHERE id=? AND kind='resume_document'", (identifier,)).fetchone()
        if not row or row[0] != expected_revision:
            _fail("target_changed", "ResumeDocument 已变化")
        return
    _fail("proposal_requires_regeneration", "manifest target 类型不受支持")


def _check_dependency(store, c, item):
    kind, identifier = item.get("kind"), item.get("id")
    expected_absent = item.get("expected_absent") is True
    if kind in {"company_research", "opportunity_research"}:
        owner = item.get("owner_id") or identifier
        current, exists = _current_research(store, c, kind, owner)
        if expected_absent:
            if exists:
                _fail("source_changed", "Research 预期不存在但已存在")
            return
        if not exists or current["id"] != identifier or current["revision"] != item.get("revision"):
            _fail("source_changed", "Research 来源已变化")
        if item.get("content_hash") != _research_hash(current):
            _fail("source_changed", "Research 内容已变化")
        return
    if kind == "opportunity":
        from . import opportunity as op
        current = op.resolve(store, c, identifier)
        if current.get("revision") != item.get("revision") or digest(selected_opportunity(current)) != item.get("content_hash"):
            _fail("source_changed", "Opportunity/JD 来源已变化")
        return
    if kind == "resume_document":
        row = c.execute("SELECT revision,body FROM current WHERE id=? AND kind='resume_document'", (identifier,)).fetchone()
        if not row or row[0] != item.get("revision") or digest(json.loads(row[1]).get("document")) != item.get("content_hash"):
            _fail("source_changed", "ResumeDocument 来源已变化")
        return
    if kind == "interview_raw":
        row = c.execute("SELECT body FROM records WHERE id=? AND kind='interview_raw'", (identifier,)).fetchone()
        if not row:
            _fail("source_changed", "Interview Raw 已删除")
        raw = json.loads(row[0])
        if raw.get("revision") != item.get("revision") or raw.get("hash") != item.get("content_hash"):
            _fail("source_changed", "Interview Raw 已变化")
        return
    if kind == "communication":
        row = c.execute("SELECT body FROM records WHERE id=? AND kind='communication'", (identifier,)).fetchone()
        if not row:
            _fail("source_changed", "沟通记录已删除")
        raw = json.loads(row[0])
        value = {
            "type": raw.get("type"), "occurred_on": raw.get("occurred_on"),
            "content": raw.get("content"), "archived": raw.get("archived", False),
        }
        if raw.get("revision") != item.get("revision") or digest(value) != item.get("content_hash"):
            _fail("source_changed", "沟通记录已变化")
        return
    if kind == "wiki_entry":
        row = c.execute("SELECT revision,body FROM current WHERE id=? AND kind='wiki_entry'", (identifier,)).fetchone()
        if not row:
            _fail("source_changed", "Wiki 来源已变化")
        raw = json.loads(row[1])
        value = {
            "title": raw.get("title"), "entry_type": raw.get("entry_type"),
            "content": raw.get("content"), "scope_type": raw.get("scope_type"),
            "scope_id": raw.get("scope_id"),
        }
        if row[0] != item.get("revision") or digest(value) != item.get("content_hash"):
            _fail("source_changed", "Wiki 来源已变化")
        return
    if kind == "wiki_knowledge":
        current = store._get(c, identifier, "wiki_knowledge")
        if current.get("revision") != item.get("revision") or digest(current) != item.get("content_hash"):
            _fail("source_changed", "Career Wiki 来源已变化")
        return
    if kind in {"work_project", "employment"}:
        if kind == "employment":
            from .work import _employment
            current = _employment(store, c, identifier)
        else:
            current = store._get(c, identifier, kind)
        if current.get("revision") != item.get("revision") or digest(current) != item.get("content_hash"):
            _fail("source_changed", "Career 经历已变化")
        return
    if kind in {"raw_material", "work_evidence"}:
        from .wiki import sources as wiki_sources
        current = wiki_sources.resolve_source(store, c, kind, identifier)
        if current['revision'] != item.get('revision') or current['hash'] != item.get('content_hash'):
            _fail('source_changed', '指定 Raw 来源已变化')
        return
    if kind == "web_source":
        return
    _fail("proposal_requires_regeneration", "manifest dependency 类型不受支持")


def _research_hash(document):
    from .research_store import content_hash
    return content_hash(document)


def validate(store, c, value):
    if not isinstance(value, dict) or value.get("manifest_version") != 1:
        _fail("proposal_requires_regeneration", "提案缺少可验证的来源清单")
    target = value.get("target")
    dependencies = value.get("dependencies")
    if not isinstance(target, dict) or not isinstance(dependencies, list):
        _fail("proposal_requires_regeneration", "提案来源清单结构不完整")
    _check_target(store, c, target, value.get("target_revision"))
    for item in dependencies:
        if not isinstance(item, dict) or not item.get("kind") or not item.get("id"):
            _fail("proposal_requires_regeneration", "提案依赖项结构不完整")
        _check_dependency(store, c, item)
    return True
