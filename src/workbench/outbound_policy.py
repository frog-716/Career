"""Shared outbound preparation, scope and budget policy for AI tasks.

The preparation record is deliberately metadata-only.  The final request is
compiled again immediately before execution and the user-facing preview is
returned from that one compilation, but neither the preview nor raw source
content is persisted in the preparation/audit records.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import re

from .core import Conflict, Invalid, Missing, digest, now, uid


POLICY_VERSION = "outbound-policy-v1"
PREPARATION_TTL_MINUTES = 10
REQUEST_BYTES_LIMIT = 256 * 1024
RESPONSE_BYTES_LIMIT = 2 * 1024 * 1024
OUTPUT_TOKENS_LIMIT = 4096
SOURCE_LIMIT = 50
CONNECTION_REQUEST_BYTES_LIMIT = 16 * 1024


TASK_POLICIES = {
    "wiki_cognition_compiler": {
        "required": {"selected_experiences", "existing_cognition"},
        "optional": set(),
        "forbidden": {
            "raw", "raw_archive", "opportunity", "person", "resume",
            "interview", "feedback", "secret", "history",
        },
    },
    "wiki_compiler": {
        "required": {"selected_raw"},
        "optional": {"current_wiki"},
        "forbidden": {"resume", "feedback", "other_opportunities", "full_raw_archive", "authorization", "cognition"},
    },
    "legacy_analysis": {
        "required": {"target_jd"},
        "optional": {"current_fact", "company_identity", "career_context"},
        "forbidden": {"feedback", "other_opportunities", "full_raw_archive", "authorization"},
    },
    "resume_optimization": {
        "required": {"opportunity", "current_resume_document"},
        "optional": {"company_research", "opportunity_research", "current_fact", "career_context"},
        "forbidden": {"phone", "email", "address", "feedback", "other_opportunities", "full_raw_archive", "authorization"},
    },
    "research_update": {
        "required": {"opportunity", "web_source"},
        "optional": {"company_research", "opportunity_research", "selected_communication", "current_interview_raw"},
        "forbidden": {"feedback", "other_opportunities", "full_raw_archive", "authorization"},
    },
    "interview_final_review": {
        "required": {"opportunity", "target_real_interview", "current_interview_raw"},
        "optional": {"submission_resume_snapshot", "opportunity_research", "selected_communication", "selected_final_review_real", "interview_preparation", "career_context"},
        "forbidden": {"selected_final_review_simulation", "feedback", "employment_private_notes", "full_raw_archive", "authorization"},
    },
    "interview_research_patch": {
        "required": {"opportunity", "current_interview_raw"},
        "optional": {"target_real_interview", "submission_resume_snapshot", "opportunity_research", "selected_communication", "career_context"},
        "forbidden": {"simulation", "feedback", "employment_private_notes", "full_raw_archive", "authorization"},
    },
}


_SENSITIVE_CONTACT = re.compile(r"(?:电话|手机|邮箱|电子邮件|地址|email|phone|mobile|address)", re.I)


def _json_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _redact_resume_contacts(value):
    if not isinstance(value, dict):
        return value
    result = deepcopy(value)
    profile = result.get("profile")
    if isinstance(profile, dict) and isinstance(profile.get("contacts"), list):
        profile["contacts"] = [
            contact for contact in profile["contacts"]
            if not isinstance(contact, dict)
            or not _SENSITIVE_CONTACT.search(str(contact.get("content", "")))
        ]
    return result


def sanitize_packet(task_type, packet):
    """Return the exact context shape that may be passed to a provider."""
    if not isinstance(packet, dict):
        raise Invalid("AI 资料包结构不合法")
    if task_type == "wiki_compiler":
        return _sanitize_wiki_compiler_packet(packet)
    if task_type == "wiki_cognition_compiler":
        return _sanitize_wiki_cognition_packet(packet)
    policy = TASK_POLICIES.get(task_type)
    if not policy:
        raise Invalid("AI 任务策略不存在")
    result = deepcopy(packet)
    sources = result.get("sources")
    if not isinstance(sources, list) or len(sources) > SOURCE_LIMIT:
        raise Invalid("资料来源超过预算，请缩小材料范围")
    purposes = set()
    clean_sources = []
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            raise Invalid("AI 来源结构不合法")
        purpose = source.get("purpose")
        if not isinstance(purpose, str):
            raise Invalid("AI 来源用途不合法")
        if purpose in policy["forbidden"]:
            raise Invalid("forbidden_context: 当前任务不允许该资料来源")
        if purpose not in policy["required"] | policy["optional"]:
            raise Invalid("forbidden_context: 当前任务未声明该资料来源")
        purposes.add(purpose)
        clean = {key: value for key, value in source.items() if key != "content"}
        if task_type == "resume_optimization" and purpose == "current_resume_document":
            clean["selected_content"] = _redact_resume_contacts(clean.get("selected_content"))
        clean_sources.append(clean)
    missing = policy["required"] - purposes
    if missing:
        raise Invalid("required_context_missing: " + ",".join(sorted(missing)))
    result["sources"] = clean_sources
    result["policy_version"] = POLICY_VERSION
    result["budget_used"] = dict(result.get("budget_used") or {})
    result["budget_used"]["source_count"] = len(clean_sources)
    result["budget_used"]["content_chars"] = sum(
        len(json.dumps(source.get("selected_content", ""), ensure_ascii=False))
        for source in clean_sources
    )
    return result


def _sanitize_wiki_compiler_packet(packet):
    """Validate D2's purpose-built DTO without adding transport metadata to it."""
    if set(packet) != {"task", "raw", "scopes", "current_knowledge"}:
        raise Invalid("Wiki Compiler Context DTO 字段不符合合同")
    if packet.get("task") != "analyze_new_raw_for_wiki_changes":
        raise Invalid("Wiki Compiler 任务不合法")
    raw = packet.get("raw")
    if not isinstance(raw, dict) or set(raw) != {"id", "source_kind", "created_at", "content"}:
        raise Invalid("Wiki Compiler Raw DTO 不合法")
    if (
        not isinstance(raw.get("id"), str) or not raw["id"]
        or raw.get("source_kind") != "manual_text"
        or not isinstance(raw.get("created_at"), str)
        or not isinstance(raw.get("content"), str) or not raw["content"].strip()
    ):
        raise Invalid("Wiki Compiler Raw DTO 不合法")
    scopes = packet.get("scopes")
    if not isinstance(scopes, list) or not scopes or len(scopes) > 50:
        raise Invalid("Wiki Compiler scope DTO 不合法")
    scope_keys = set()
    allowed_scope_types = {"project", "employment", "opportunity", "person", "personal"}
    for scope in scopes:
        if not isinstance(scope, dict) or set(scope) != {"type", "stable_id", "minimal_identity"}:
            raise Invalid("Wiki Compiler scope DTO 不合法")
        scope_type, scope_id, identity = scope.get("type"), scope.get("stable_id"), scope.get("minimal_identity")
        if scope_type not in allowed_scope_types or not isinstance(scope_id, str) or not isinstance(identity, dict):
            raise Invalid("Wiki Compiler scope DTO 不合法")
        if scope_type == "personal" and scope_id != "":
            raise Invalid("Wiki Compiler personal scope 不合法")
        if scope_type != "personal" and not scope_id:
            raise Invalid("Wiki Compiler scope identity 不合法")
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in identity.items()):
            raise Invalid("Wiki Compiler minimal identity 只能包含文字字段")
        key = (scope_type, scope_id)
        if key in scope_keys:
            raise Invalid("Wiki Compiler scope 重复")
        scope_keys.add(key)
    knowledge = packet.get("current_knowledge")
    if not isinstance(knowledge, list) or len(knowledge) > 200:
        raise Invalid("Wiki Compiler current Wiki DTO 不合法")
    if 1 + len(knowledge) > SOURCE_LIMIT:
        raise Invalid("budget_exceeded: Wiki Compiler 原文与当前知识来源超过 50 条")
    ids = set()
    chars = len(raw["content"])
    valid_types = {"fact", "observation", "hypothesis"}
    for item in knowledge:
        expected = {"knowledge_id", "type", "content", "tags", "revision", "scope_type", "scope_id"}
        if not isinstance(item, dict) or set(item) != expected:
            raise Invalid("Wiki Compiler current Wiki DTO 不合法")
        if (
            not isinstance(item.get("knowledge_id"), str) or not item["knowledge_id"]
            or item.get("type") not in valid_types
            or not isinstance(item.get("content"), str)
            or not isinstance(item.get("tags"), list)
            or not isinstance(item.get("revision"), int) or isinstance(item.get("revision"), bool)
            or (item.get("scope_type"), item.get("scope_id")) not in scope_keys
        ):
            raise Invalid("Wiki Compiler current Wiki DTO 不合法")
        if item["knowledge_id"] in ids:
            raise Invalid("Wiki Compiler current Wiki DTO 重复")
        ids.add(item["knowledge_id"])
        if any(not isinstance(tag, str) for tag in item["tags"]):
            raise Invalid("Wiki Compiler Tags DTO 不合法")
        chars += len(item["content"])
    if chars > 200000:
        raise Invalid("Wiki Compiler Context DTO 超出资料预算")
    return deepcopy(packet)


def _sanitize_wiki_cognition_packet(packet):
    """Validate D4's purpose-built cross-experience DTO; never accept Raw."""
    if set(packet) != {"task", "selected_experiences", "existing_cognition"}:
        raise Invalid("长期认知 Context DTO 字段不符合合同")
    if packet.get("task") != "synthesize_long_term_cognition":
        raise Invalid("长期认知任务不合法")
    experiences = packet.get("selected_experiences")
    if not isinstance(experiences, list) or not 2 <= len(experiences) <= 20:
        raise Invalid("长期认知必须明确选择 2 到 20 段经历")
    experience_keys = set()
    knowledge_ids = set()
    knowledge_count = 0
    content_chars = 0
    for experience in experiences:
        if not isinstance(experience, dict) or set(experience) != {
            "type", "id", "name", "current_knowledge",
        }:
            raise Invalid("长期认知经历 DTO 不合法")
        kind, identifier = experience.get("type"), experience.get("id")
        if kind not in {"project", "employment"} or not isinstance(identifier, str) or not identifier:
            raise Invalid("长期认知只允许项目或任职经历")
        key = (kind, identifier)
        if key in experience_keys:
            raise Invalid("同一经历不能重复计数")
        experience_keys.add(key)
        if not isinstance(experience.get("name"), str) or not experience["name"].strip():
            raise Invalid("长期认知经历名称不合法")
        knowledge = experience.get("current_knowledge")
        if not isinstance(knowledge, list) or not knowledge:
            raise Invalid("所选经历必须有当前 Wiki 知识")
        for item in knowledge:
            if not isinstance(item, dict) or set(item) != {
                "knowledge_id", "type", "content", "tags",
            }:
                raise Invalid("长期认知 Wiki DTO 不合法")
            if (
                not isinstance(item.get("knowledge_id"), str) or not item["knowledge_id"]
                or item["type"] not in {"fact", "observation", "hypothesis"}
                or not isinstance(item.get("content"), str) or not item["content"].strip()
                or not isinstance(item.get("tags"), list)
                or any(not isinstance(tag, str) for tag in item["tags"])
                or item["knowledge_id"] in knowledge_ids
            ):
                raise Invalid("长期认知 Wiki DTO 不合法")
            knowledge_ids.add(item["knowledge_id"])
            knowledge_count += 1
            content_chars += len(item["content"])
    existing = packet.get("existing_cognition")
    if not isinstance(existing, list) or len(existing) > 200:
        raise Invalid("已有长期认知 DTO 不合法")
    existing_ids = set()
    for item in existing:
        if not isinstance(item, dict) or set(item) != {
            "id", "type", "content", "revision", "supporting_experience_ids",
        }:
            raise Invalid("已有长期认知 DTO 不合法")
        if (
            not isinstance(item.get("id"), str) or not item["id"]
            or item["id"] in existing_ids
            or item.get("type") not in {"fact", "observation", "hypothesis"}
            or not isinstance(item.get("content"), str)
            or not isinstance(item.get("revision"), int)
            or isinstance(item.get("revision"), bool)
            or not isinstance(item.get("supporting_experience_ids"), list)
            or any(not isinstance(value, str) for value in item["supporting_experience_ids"])
        ):
            raise Invalid("已有长期认知 DTO 不合法")
        existing_ids.add(item["id"])
        content_chars += len(item["content"])
    if knowledge_count > SOURCE_LIMIT or content_chars > 200000:
        raise Invalid("长期认知 Context 超出资料预算")
    return deepcopy(packet)


def source_refs(packet):
    if isinstance(packet, dict) and packet.get("task") == "synthesize_long_term_cognition":
        return [
            {
                "id": item["knowledge_id"],
                "purpose": "selected_experience_wiki",
            }
            for experience in packet["selected_experiences"]
            for item in experience["current_knowledge"]
        ]
    if isinstance(packet, dict) and packet.get("task") == "analyze_new_raw_for_wiki_changes":
        raw = packet["raw"]
        return [
            {"id": raw["id"], "revision": 1, "purpose": "selected_raw"},
            *[
                {"id": item["knowledge_id"], "revision": item["revision"], "purpose": "current_wiki"}
                for item in packet["current_knowledge"]
            ],
        ]
    return [
        {
            key: source[key]
            for key in ("id", "revision", "hash", "purpose")
            if key in source
        }
        for source in packet.get("sources", [])
    ]


def metadata_manifest(manifest):
    if not isinstance(manifest, dict):
        return None
    target = manifest.get("target") or {}
    return {
        "manifest_version": manifest.get("manifest_version"),
        "task_type": manifest.get("task_type"),
        "target": {
            key: target[key]
            for key in ("kind", "id", "opportunity_id", "company_id")
            if key in target
        },
        "target_revision": manifest.get("target_revision"),
        "dependencies": [
            {
                key: dependency[key]
                for key in ("kind", "id", "revision", "content_hash", "purpose", "owner_id", "expected_absent")
                if key in dependency
            }
            for dependency in manifest.get("dependencies", [])
        ],
        "policy_version": manifest.get("policy_version", POLICY_VERSION),
    }


def budget(packet, payload, *, connection=False):
    request_limit = CONNECTION_REQUEST_BYTES_LIMIT if connection else REQUEST_BYTES_LIMIT
    if isinstance(packet, dict) and packet.get("task") == "synthesize_long_term_cognition":
        source_count = sum(
            len(experience.get("current_knowledge", []))
            for experience in packet.get("selected_experiences", [])
        )
        content_chars = sum(
            len(item.get("content", ""))
            for experience in packet.get("selected_experiences", [])
            for item in experience.get("current_knowledge", [])
        ) + sum(
            len(item.get("content", "")) for item in packet.get("existing_cognition", [])
        )
    elif isinstance(packet, dict) and packet.get("task") == "analyze_new_raw_for_wiki_changes":
        source_count = 1 + len(packet.get("current_knowledge", []))
        content_chars = len(packet.get("raw", {}).get("content", "")) + sum(
            len(item.get("content", "")) for item in packet.get("current_knowledge", [])
        )
    else:
        source_count = len(packet.get("sources", [])) if isinstance(packet, dict) else 0
        content_chars = (packet.get("budget_used") or {}).get("content_chars", 0) if isinstance(packet, dict) else 0
    used = {
        "source_count": source_count,
        "content_chars": content_chars,
        "request_bytes": _json_bytes(payload),
    }
    result = {
        **used,
        "source_count_limit": 0 if connection else SOURCE_LIMIT,
        "content_chars_limit": 0 if connection else 200000,
        "request_bytes_limit": request_limit,
        "response_bytes_limit": RESPONSE_BYTES_LIMIT,
        "output_tokens_limit": 32 if connection else OUTPUT_TOKENS_LIMIT,
        "connect_timeout_seconds": 10,
        "read_timeout_seconds": 45,
        "total_timeout_seconds": 90,
        "concurrent_outbound_limit": 1,
        "automatic_retries": 0,
    }
    if used["request_bytes"] > request_limit:
        raise Invalid("budget_exceeded: 最终请求体超过 256 KiB 上限" if not connection else "budget_exceeded: 连接测试请求过大")
    if not connection and used["content_chars"] > 200000:
        raise Invalid("budget_exceeded: 资料内容超过预算，请缩小材料范围")
    return result


def preview(payload):
    value = deepcopy(payload)
    if isinstance(value, dict):
        headers = value.get("headers")
        if isinstance(headers, dict):
            headers.pop("Authorization", None)
            headers.pop("authorization", None)
    return value


def _expires_at():
    return (datetime.now(timezone.utc) + timedelta(minutes=PREPARATION_TTL_MINUTES)).isoformat()


def create_preparation(store, *, task_type, target, client_intent, packet, payload,
                       manifest=None, diagnostics=None, omissions=None, budget_info=None,
                       extra=None):
    clean_packet = sanitize_packet(task_type, packet)
    request_hash = digest(payload)
    budget_info = budget_info or budget(clean_packet, payload)
    fingerprint = digest(client_intent)
    target = dict(target)
    key = client_intent.get("idempotency_key")
    with store.connect() as c:
        for existing in store._records(c, "ai_preparation"):
            if (
                existing.get("task_type") == task_type
                and existing.get("target") == target
                and existing.get("idempotency_key") == key
            ):
                if existing.get("client_intent_hash") != fingerprint:
                    raise Conflict("请求标识已用于不同 AI 准备操作")
                same_extra = all(existing.get(name) == value for name, value in (extra or {}).items())
                if (
                    existing.get("payload_hash") == request_hash
                    and existing.get("status") == "prepared"
                    and same_extra
                ):
                    return public_preparation(existing, payload_preview=payload)
                store._record(c, "ai_preparation", dict(existing, status="superseded", superseded_at=now()))
        record = {
            "id": "ai-prepared:" + uid(),
            "task_type": task_type,
            "target": target,
            "idempotency_key": key,
            "client_intent_hash": fingerprint,
            "source_refs": source_refs(clean_packet),
            "manifest": metadata_manifest(manifest),
            "model_config_id": (diagnostics or {}).get("model_config_id"),
            "provider": (diagnostics or {}).get("provider"),
            "model": (diagnostics or {}).get("model"),
            "policy_version": POLICY_VERSION,
            "payload_hash": request_hash,
            "budget": budget_info,
            "omissions": list(omissions or clean_packet.get("omissions", [])),
            "expires_at": _expires_at(),
            "created_at": now(),
            "status": "prepared",
        }
        if extra:
            record.update(extra)
        store._record(c, "ai_preparation", record)
    return public_preparation(record, payload_preview=payload)


def public_preparation(record, *, payload_preview=None, status="context_confirmation_required"):
    result = {
        "status": status,
        "prepared_id": record["id"],
        "task_type": record["task_type"],
        "target": record["target"],
        "manifest": record.get("manifest"),
        "source_refs": record.get("source_refs", []),
        "payload_hash": record["payload_hash"],
        "omissions": record.get("omissions", []),
        "budget": record["budget"],
        "expires_at": record["expires_at"],
        "policy_version": record.get("policy_version", POLICY_VERSION),
    }
    if payload_preview is not None:
        result["payload_preview"] = preview(payload_preview)
    return result


class PreparationExpired(Missing):
    code = "prepared_request_expired"


def load_preparation(store, prepared_id):
    with store.connect(False) as c:
        row = c.execute("SELECT body FROM records WHERE id=? AND kind='ai_preparation'", (prepared_id,)).fetchone()
        if not row:
            raise Missing("准备对象不存在或已过期")
        record = json.loads(row[0])
        if record.get("expires_at"):
            try:
                expires = datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
                if datetime.now(timezone.utc) >= expires:
                    raise PreparationExpired("准备对象已过期，请重新预览")
            except ValueError:
                raise PreparationExpired("准备对象已过期，请重新预览") from None
        return record


def validate_preparation(store, prepared_id, *, task_type, target, client_intent,
                         payload_hash, packet, payload, manifest=None):
    record = load_preparation(store, prepared_id)
    if record.get("status") != "prepared":
        raise Conflict("准备对象不可执行")
    if record.get("task_type") != task_type or record.get("target") != target:
        raise Conflict("准备对象目标不匹配")
    if record.get("client_intent_hash") != digest(client_intent):
        raise Conflict("准备对象输入已变化，请重新预览")
    if record.get("payload_hash") != payload_hash or digest(payload) != payload_hash:
        raise Conflict("prepared_request_stale: 实际发送内容已变化，请重新预览")
    if record.get("source_refs") != source_refs(packet):
        raise Conflict("prepared_request_stale: 来源版本已变化，请重新预览")
    if record.get("manifest") != metadata_manifest(manifest):
        raise Conflict("prepared_request_stale: 权限或目标已变化，请重新预览")
    with store.connect() as c:
        store._record(c, "ai_preparation", dict(record, status="executing", executed_at=now()))
    return record


def audit(store, *, task_type, target, event, payload_hash=None, operation_id=None,
          source_refs_value=None, details=None):
    value = {
        "id": "ai-audit:" + uid(), "task_type": task_type, "target": dict(target),
        "event": event, "operation_id": operation_id, "payload_hash": payload_hash,
        "source_refs": list(source_refs_value or []), "policy_version": POLICY_VERSION,
        "details": dict(details or {}), "created_at": now(),
    }
    with store.connect() as c:
        store._record(c, "ai_audit", value)
    return value


def validate_connection_payload(payload):
    if not isinstance(payload, dict) or payload.get("messages") != [
        {"role": "system", "content": "Reply with a compact JSON object and no surrounding prose."},
        {"role": "user", "content": 'Return exactly {"ok":true,"message":"connection test passed"}.'},
    ]:
        raise Invalid("连接测试只能发送固定最小内容")
    clean = {key: value for key, value in payload.items() if key != "_connection_test"}
    if set(clean) - {"model", "messages", "response_format", "max_tokens", "stream"}:
        raise Invalid("连接测试只能发送固定最小内容")
    if clean.get("max_tokens") != 32 or clean.get("stream") is not False:
        raise Invalid("连接测试只能使用固定最小预算")
    return budget({"sources": []}, clean, connection=True)
