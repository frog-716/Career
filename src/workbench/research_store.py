"""唯一的 CompanyResearch / OpportunityResearch 读写入口。"""

from datetime import date

from .core import Conflict, Invalid, Missing, digest, now, uid
from . import opportunity as op


RESEARCH_KINDS = {"company_research", "opportunity_research"}
CATEGORIES = {
    "company", "company_business", "product_business", "current_dynamic", "role",
    "business", "department", "team", "why_role", "recruiting_context", "challenge",
    "process", "unknown",
}
CLASSIFICATIONS = {"fact", "inference", "unknown"}
EVIDENCE_STATUSES = {"lead", "excerpt_present", "user_confirmed", "unknown"}
EVIDENCE_SOURCE_TYPES = {"user_provided_excerpt", "manual_reference", "web_search_result"}
EVIDENCE_INPUT_METHODS = {"user_pasted", "user_entered", "search_result", "manual"}
ITEM_STATUSES = {"active", "retracted"}
MAX_CONTENT_CHARS = 10000
MAX_SOURCE_REFS = 10


class ResearchProposalValidationError(Invalid):
    """Safe model-proposal validation failure; never includes generated values."""

    def __init__(self, code, path):
        self.code = code
        self.path = path
        super().__init__(path)


def research_proposal_output_schema():
    """Describe only the fields accepted from the Research model proposal."""
    item_properties = {
        "category": {
            "type": "string", "enum": sorted(CATEGORIES), "default": "unknown",
            "description": "可省略；省略时 Career 使用 unknown。",
        },
        "classification": {
            "type": "string", "enum": sorted(CLASSIFICATIONS), "default": "unknown",
            "description": "可省略；省略时 Career 使用 unknown。搜索结果不能被模型标成已核实事实。",
        },
        "content": {
            "type": "string", "minLength": 1, "pattern": r"\S",
            "maxLength": MAX_CONTENT_CHARS,
            "description": "必填，去除首尾空白后仍须非空，最多 10,000 个字符。",
        },
        "source_refs": {
            "type": "array", "maxItems": MAX_SOURCE_REFS, "default": [],
            "description": "可省略；省略时为空数组。url 必须精确匹配本轮 packet 中 purpose=web_source 的 selected_content.url；id 可省略或为 null，若提供字符串必须等于同一来源的 packet sources.id。Career 会补齐 kind、owner_id、scope、revision、hash、retrieved_at 和 date_status。",
            "items": {
                "type": "object", "required": ["url"], "additionalProperties": False,
                "properties": {
                    "url": {"type": "string", "minLength": 1},
                    "id": {
                        "type": ["string", "null"],
                        "description": "可省略或为 null；若提供字符串，必须等于同一来源的 packet sources.id。",
                    },
                },
            },
        },
    }
    example = {
        "company_items": [{
            "category": "company_business", "classification": "unknown",
            "content": "虚构星河科技经营虚构的协作产品。", "source_refs": [],
        }],
        "opportunity_items": [{
            "category": "role", "classification": "unknown",
            "content": "虚构岗位负责虚构产品的需求整理。", "source_refs": [],
        }],
    }
    return {
        "version": 1,
        "type": "object",
        "required": ["company_items", "opportunity_items"],
        "additionalProperties": False,
        "properties": {
            "company_items": {
                "description": "公司范围的研究条目。",
                "type": "array", "items": {
                    "type": "object", "required": ["content"],
                    "additionalProperties": False, "properties": item_properties,
                },
            },
            "opportunity_items": {
                "description": "当前岗位/机会范围的研究条目。",
                "type": "array", "items": {
                    "type": "object", "required": ["content"],
                    "additionalProperties": False, "properties": item_properties,
                },
            },
        },
        "example": example,
    }


def normalise_proposal_output(value):
    """Validate and normalize the model-owned portion of a Research proposal."""
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ResearchProposalValidationError("invalid_result", "$")
    required_groups = ("company_items", "opportunity_items")
    if set(value) != set(required_groups):
        raise ResearchProposalValidationError("invalid_result", "$")

    normalized = {}
    allowed_item_fields = {"category", "classification", "content", "source_refs"}
    allowed_ref_fields = {"url", "id"}
    for group in required_groups:
        raw_items = value[group]
        if not isinstance(raw_items, list):
            raise ResearchProposalValidationError("invalid_result", group)
        normalized[group] = []
        for index, raw in enumerate(raw_items):
            item_path = f"{group}[{index}]"
            if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
                raise ResearchProposalValidationError("invalid_result", item_path)
            if not set(raw).issubset(allowed_item_fields):
                raise ResearchProposalValidationError("invalid_result", item_path)

            content_path = item_path + ".content"
            if "content" not in raw:
                raise ResearchProposalValidationError("content_missing", content_path)
            content = raw["content"]
            if not isinstance(content, str):
                raise ResearchProposalValidationError("content_wrong_type", content_path)
            if not content.strip():
                raise ResearchProposalValidationError("content_empty", content_path)
            if len(content) > MAX_CONTENT_CHARS:
                raise ResearchProposalValidationError("content_too_long", content_path)

            for field, allowed in (("category", CATEGORIES), ("classification", CLASSIFICATIONS)):
                if field in raw and (not isinstance(raw[field], str) or raw[field] not in allowed):
                    raise ResearchProposalValidationError("invalid_result", item_path + "." + field)

            refs = raw.get("source_refs", [])
            if not isinstance(refs, list) or len(refs) > MAX_SOURCE_REFS:
                raise ResearchProposalValidationError("source_ref_invalid", item_path + ".source_refs")
            for ref_index, ref in enumerate(refs):
                ref_path = f"{item_path}.source_refs[{ref_index}]"
                if not isinstance(ref, dict) or any(not isinstance(key, str) for key in ref):
                    raise ResearchProposalValidationError("source_ref_invalid", ref_path)
                if not set(ref).issubset(allowed_ref_fields):
                    raise ResearchProposalValidationError("source_ref_invalid", ref_path)
                url = ref.get("url")
                if not isinstance(url, str) or not url.strip():
                    raise ResearchProposalValidationError("source_ref_invalid", ref_path + ".url")
                if "id" in ref and ref["id"] is not None and not isinstance(ref["id"], str):
                    raise ResearchProposalValidationError("source_ref_invalid", ref_path + ".id")

            try:
                normalized[group].append(normalise_item(raw))
            except (Invalid, TypeError, AttributeError, KeyError) as exc:
                raise ResearchProposalValidationError("invalid_result", item_path) from exc
    return normalized


def owner_field(kind):
    if kind == "company_research":
        return "company_id"
    if kind == "opportunity_research":
        return "opportunity_id"
    raise Invalid("Research 类型不合法")


def canonical_owner(kind, owner_id):
    if kind not in RESEARCH_KINDS or not isinstance(owner_id, str) or not owner_id.strip():
        raise Invalid("Research owner 不合法")
    return op.canonical_id(owner_id) if kind == "opportunity_research" else owner_id.strip()


def research_id(kind, owner_id):
    return kind + ":" + digest(canonical_owner(kind, owner_id))


def legacy_ids(kind, owner_id):
    owner = canonical_owner(kind, owner_id)
    current = research_id(kind, owner)
    if kind == "opportunity_research":
        return {current, "opportunity-research:" + digest(owner)}
    return {current}


def _raw_owner(kind, raw):
    fields = ("company_id", "owner_id") if kind == "company_research" else (
        "opportunity_id", "job_id", "owner_id"
    )
    for field in fields:
        value = raw.get(field)
        if isinstance(value, str) and value.strip():
            return canonical_owner(kind, value)
    return None


def _normalise_evidence(value):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 10:
        raise Invalid("Research evidence 必须是最多 10 条的数组")
    result = []
    for raw in value:
        if not isinstance(raw, dict):
            raise Invalid("Research evidence 必须是对象")
        source_id = raw.get("source_id")
        source_type = raw.get("source_type", "user_provided_excerpt")
        input_method = raw.get("input_method", "user_pasted")
        observed_on = raw.get("observed_on")
        scope = raw.get("scope")
        owner_id = raw.get("owner_id")
        excerpt = raw.get("excerpt")
        if not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 200:
            raise Invalid("Research evidence source_id 不合法")
        if source_type not in EVIDENCE_SOURCE_TYPES:
            raise Invalid("Research evidence source_type 不合法")
        if input_method not in EVIDENCE_INPUT_METHODS:
            raise Invalid("Research evidence input_method 不合法")
        if not isinstance(observed_on, str) or not observed_on.strip():
            raise Invalid("Research evidence 必须记录 observed_on")
        try:
            date.fromisoformat(observed_on[:10])
        except ValueError as exc:
            raise Invalid("Research evidence observed_on 不合法") from exc
        if scope not in {"company", "opportunity"}:
            raise Invalid("Research evidence scope 不合法")
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise Invalid("Research evidence 必须记录 owner_id")
        if not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt) > 20000:
            raise Invalid("Research evidence excerpt 不合法")
        evidence = dict(raw)
        evidence.update(
            source_id=source_id.strip(), source_type=source_type,
            input_method=input_method, observed_on=observed_on[:10],
            scope=scope, owner_id=owner_id.strip(), excerpt=excerpt.strip(),
            content_hash=digest({
                "source_id": source_id.strip(), "owner_id": owner_id.strip(),
                "scope": scope, "observed_on": observed_on[:10], "excerpt": excerpt.strip(),
            }),
        )
        result.append(evidence)
    return result


def _relation_ids(value, field):
    if value is None:
        return []
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or len(values) > 10 or any(not isinstance(x, str) or not x.strip() for x in values):
        raise Invalid("Research " + field + " 不合法")
    return list(dict.fromkeys(x.strip() for x in values))


def _normalise_item(value, fallback_id):
    if not isinstance(value, dict):
        raise Invalid("Research item 必须是对象")
    category = value.get("category", "unknown")
    classification = value.get("classification", "unknown")
    content = value.get("content", "")
    if category not in CATEGORIES or classification not in CLASSIFICATIONS:
        raise Invalid("Research item 的 category/classification 不合法")
    if not isinstance(content, str) or not content.strip() or len(content) > MAX_CONTENT_CHARS:
        raise Invalid("Research item 的 content 不合法")
    refs = value.get("source_refs", [])
    if not isinstance(refs, list) or len(refs) > MAX_SOURCE_REFS:
        raise Invalid("Research 来源过多")
    evidence_status = value.get("evidence_status", "unknown")
    if evidence_status not in EVIDENCE_STATUSES:
        raise Invalid("Research evidence_status 不合法")
    evidence = _normalise_evidence(value.get("evidence", []))
    verification = value.get("verification", {})
    if not isinstance(verification, dict):
        raise Invalid("Research verification 不合法")
    verification = {
        "user_confirmed": bool(verification.get("user_confirmed", evidence_status == "user_confirmed")),
        "independently_verified": bool(verification.get("independently_verified", False)),
    }
    status = value.get("status", "active")
    if status not in ITEM_STATUSES:
        raise Invalid("Research item status 不合法")
    item = dict(value)
    item.update(
        id=value.get("id") or fallback_id,
        category=category,
        content=content.strip(),
        classification=classification,
        source_refs=refs,
        evidence_status=evidence_status,
        evidence=evidence,
        verification=verification,
        status=status,
        revision=value.get("revision", 0),
        supersedes=_relation_ids(value.get("supersedes"), "supersedes"),
        replaces=_relation_ids(value.get("replaces"), "replaces"),
        updated_at=value.get("updated_at") or "",
    )
    if type(item["revision"]) is not int or item["revision"] < 0:
        raise Invalid("Research item revision 不合法")
    return item


def normalise_item(value, source_refs=None):
    if not isinstance(value, dict):
        raise Invalid("Research item 必须是对象")
    value = dict(value)
    if source_refs is not None and "source_refs" not in value:
        value["source_refs"] = source_refs
    value.setdefault("updated_at", now())
    return _normalise_item(value, "research-item:" + uid())


def _normalise_document(kind, owner_id, raw):
    owner = canonical_owner(kind, owner_id)
    raw = dict(raw or {})
    key = owner_field(kind)
    items = raw.get("items", [])
    if not isinstance(items, list):
        raise Invalid("Research items 必须是数组")
    stable_items = []
    for index, item in enumerate(items):
        fallback = "research-item:" + digest([raw.get("id"), index, item.get("content") if isinstance(item, dict) else item])
        stable_items.append(_normalise_item(item, fallback))
    raw.update(
        id=raw.get("id") or research_id(kind, owner),
        **{key: owner},
        items=stable_items,
        revision=raw.get("revision", 0),
        created_at=raw.get("created_at") or now(),
    )
    if type(raw["revision"]) is not int or raw["revision"] < 0:
        raise Invalid("Research revision 不合法")
    return raw


def lookup(store, c, kind, owner_id):
    """返回 (当前正本, 是否已经落盘)，读路径不创建记录。"""
    owner = canonical_owner(kind, owner_id)
    candidate_ids = legacy_ids(kind, owner)
    matches = []
    for raw in store._current(c, kind):
        raw_owner = _raw_owner(kind, raw)
        if raw_owner == owner or (raw_owner is None and raw.get("id") in candidate_ids):
            matches.append(raw)
    if len(matches) > 1:
        raise Conflict("research_owner_conflict: 同一规范 owner 存在多个 Research 正本：" + ", ".join(sorted(x["id"] for x in matches)))
    if not matches:
        return _normalise_document(kind, owner, {"id": research_id(kind, owner), "items": [], "revision": 0}), False
    return _normalise_document(kind, owner, matches[0]), True


def get(store, c, kind, owner_id):
    return lookup(store, c, kind, owner_id)[0]


def save(store, c, kind, owner_id, document, expected_revision):
    owner = canonical_owner(kind, owner_id)
    current, exists = lookup(store, c, kind, owner)
    if type(expected_revision) is not int or expected_revision < 0:
        raise Invalid("Research expected_revision 不合法")
    if expected_revision != current["revision"]:
        raise Conflict("Research 已更新，请保留输入并重新载入比较")
    value = _normalise_document(kind, owner, {**current, **dict(document), "id": current["id"] if exists else research_id(kind, owner)})
    saved = store._save(c, kind, value, expected_revision)
    return _normalise_document(kind, owner, saved)


def append(store, c, kind, owner_id, additions, expected_revision):
    current = get(store, c, kind, owner_id)
    items = list(current["items"]) + [normalise_item(item) for item in additions]
    return save(store, c, kind, owner_id, {**current, "items": items}, expected_revision)


def replace_item(store, c, kind, owner_id, item_id, item, expected_revision):
    current = get(store, c, kind, owner_id)
    items = list(current["items"])
    match = next((item for item in items if item["id"] == item_id), None)
    if match is None:
        raise Missing("Research item 不存在")
    replacement = normalise_item({**item, "id": item_id})
    items[items.index(match)] = replacement
    return save(store, c, kind, owner_id, {**current, "items": items}, expected_revision)


def content_hash(document):
    return digest({"owner": document.get("company_id") or document.get("opportunity_id"), "items": document.get("items", [])})
