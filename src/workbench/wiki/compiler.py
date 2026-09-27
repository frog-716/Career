"""D2 Wiki Compiler: prepare a narrow context, then store user-reviewable patches."""

from copy import deepcopy
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .. import ai_operations, context_manifest, outbound_policy
from ..core import Conflict, Invalid, Missing, digest, now, required, uid
from ..model_gateway import ModelGateway
from .. import work
from .. import opportunity
from . import api as wiki_api
from . import sources


TASK_TYPE = "wiki_compiler"
TASK_NAME = "analyze_new_raw_for_wiki_changes"
MAX_PATCHES = 20
MAX_CURRENT_KNOWLEDGE = 200
MAX_CONTENT_CHARS = 200000


def _scope_key(scope_type, scope_id):
    return scope_type, scope_id


def _domain_dependency(scope_type, scope_id, revision, identity, relation=None):
    value = {"scope_type": scope_type, "scope_id": scope_id, "identity": identity}
    if relation is not None:
        value["relation"] = relation
    return context_manifest.dependency(
        "wiki_scope", scope_id, revision, value, "scope_identity",
        owner_id=scope_type,
    )


def _make_context(store, c, raw_id):
    try:
        raw = sources.resolve_source(store, c, "raw_material", raw_id)
    except Missing:
        raise
    if raw.get("source_kind") != "manual_text":
        raise Invalid("Wiki Compiler 只接受用户明确选择的新手工 Raw")
    direct = (raw["scope_type"], raw["scope_id"])
    if direct[0] == "cognition":
        raise Invalid("D2 不处理跨经历认知范围")

    scope_values = {}
    scope_dependencies = []
    relation_dependencies = []

    def add_scope(scope_type, scope_id, identity, revision, relation=None):
        if scope_type == "cognition":
            raise Invalid("D2 不处理跨经历认知范围")
        canonical = sources._canonical_scope(store, c, scope_type, scope_id)
        if canonical is None:
            raise Missing("Raw 关联的业务对象不存在")
        key = _scope_key(*canonical)
        if key in scope_values:
            return
        if scope_type == "person":
            person = store._get(c, scope_id, work.CURRENT["person"])
            if person.get("identity_status") != "confirmed":
                raise Missing("人物不存在或身份尚未确认")
        identity = dict(identity)
        scope_values[key] = {
            "type": canonical[0], "stable_id": canonical[1],
            "minimal_identity": identity,
        }
        scope_dependencies.append(
            _domain_dependency(canonical[0], canonical[1], revision, identity, relation)
        )

    def add_employment(employment_id, relation=None):
        employment = work._employment(store, c, employment_id)
        identity = {"company": employment.get("company", ""), "role": employment.get("role", "")}
        add_scope("employment", employment["id"], identity, employment.get("revision", 0), relation)
        return employment

    def add_person(person_id, project_role=None, relation=None):
        person = store._get(c, person_id, work.CURRENT["person"])
        if person.get("identity_status") != "confirmed":
            return
        identity = {"name": person.get("name", ""), "employment_role": person.get("role", "")}
        if project_role is not None:
            identity["project_role"] = project_role
        add_scope("person", person["id"], identity, person.get("revision", 0), relation)

    scope_type, scope_id = direct
    if scope_type == "project":
        project = work._project_view(store._get(c, scope_id, work.CURRENT["project"]))
        employment_id = work._project_employment_id(project)
        relation = {"employment_id": employment_id}
        add_scope("project", project["id"], {"name": project.get("name", "")},
                  project.get("revision", 0), relation)
        if employment_id:
            employment = add_employment(employment_id, {"project_id": project["id"]})
            allowed_employment = employment["id"]
            participant_rows = c.execute(
                "SELECT body FROM records WHERE kind=? AND json_extract(body,'$.project_id')=?",
                (work.IMMUTABLE["participant"], project["id"]),
            ).fetchall()
            for (participant_body,) in participant_rows:
                participant = json.loads(participant_body)
                try:
                    person = store._get(c, participant.get("person_id"), work.CURRENT["person"])
                except (Missing, TypeError):
                    continue
                if person.get("employment_id") != allowed_employment or person.get("identity_status") != "confirmed":
                    continue
                add_person(person["id"], participant.get("role", ""), {
                    "participant_id": participant["id"],
                    "project_id": project["id"],
                    "person_revision": participant.get("person_revision"),
                })
                relation_dependencies.append(context_manifest.dependency(
                    "wiki_relation", participant["id"], 1, participant,
                    "confirmed_project_person",
                ))
    elif scope_type == "employment":
        employment = add_employment(scope_id)
        person_rows = c.execute(
            """SELECT body FROM current
                 WHERE kind=? AND json_extract(body,'$.employment_id')=?
                   AND json_extract(body,'$.identity_status')='confirmed'""",
            (work.CURRENT["person"], employment["id"]),
        ).fetchall()
        for (person_body,) in person_rows:
            person = json.loads(person_body)
            add_person(person["id"], relation={"employment_id": employment["id"]})
    elif scope_type == "person":
        person = store._get(c, scope_id, work.CURRENT["person"])
        if person.get("identity_status") != "confirmed":
            raise Missing("人物不存在或身份尚未确认")
        employment = add_employment(person.get("employment_id"), {"person_id": person["id"]})
        add_person(person["id"], relation={"employment_id": employment["id"]})
    elif scope_type == "opportunity":
        item = opportunity.resolve(store, c, scope_id)
        identity = {"company": item.get("company", ""), "title": item.get("title", "")}
        add_scope("opportunity", item["id"], identity, item.get("revision", 0))
    elif scope_type == "personal":
        add_scope("personal", "", {}, 0)
    else:
        raise Invalid("D2 不支持这类 Raw 范围")

    scopes = sorted(scope_values.values(), key=lambda item: (item["type"], item["stable_id"]))
    allowed_scope_keys = set(scope_values)
    current_knowledge = []
    wiki_dependencies = []
    for key in sorted(allowed_scope_keys):
        rows = c.execute(
            """SELECT body FROM current
                 WHERE kind='wiki_knowledge'
                   AND json_extract(body,'$.scope_type')=?
                   AND json_extract(body,'$.scope_id')=?
                   AND json_extract(body,'$.status')='current'""",
            key,
        ).fetchall()
        for (body,) in rows:
            item = json.loads(body)
            current_knowledge.append({
                "knowledge_id": item["id"], "type": item["knowledge_type"],
                "content": item["content"], "tags": list(item.get("tags", [])),
                "revision": item["revision"], "scope_type": item["scope_type"],
                "scope_id": item["scope_id"],
            })
    current_knowledge.sort(key=lambda item: (item["scope_type"], item["scope_id"], item["knowledge_id"]))
    if len(current_knowledge) > MAX_CURRENT_KNOWLEDGE:
        raise Invalid("相关范围的当前 Wiki 条目过多，请先缩小整理范围")
    content_chars = len(raw["content"]) + sum(len(item["content"]) for item in current_knowledge)
    if content_chars > MAX_CONTENT_CHARS:
        raise Invalid("相关 Raw 与当前 Wiki 超出资料预算，未发送")
    for item in current_knowledge:
        wiki_dependencies.append(context_manifest.dependency(
            "wiki_knowledge", item["knowledge_id"], item["revision"], item,
            "current_wiki",
        ))

    raw_ref = sources.source_ref(raw)
    dto = {
        "task": TASK_NAME,
        "raw": {
            "id": raw["id"], "source_kind": raw["source_kind"],
            "created_at": raw["created_at"], "content": raw["content"],
        },
        "scopes": scopes,
        "current_knowledge": current_knowledge,
    }
    dependencies = [
        context_manifest.dependency(
            "raw_material", raw["id"], raw["revision"],
            {"id": raw["id"], "scope_type": raw["scope_type"], "scope_id": raw["scope_id"]},
            "selected_raw", content_hash=raw["hash"],
        ),
        *sorted(scope_dependencies, key=lambda item: (item["kind"], item["owner_id"], item["id"])),
        *sorted(relation_dependencies, key=lambda item: item["id"]),
        *wiki_dependencies,
    ]
    manifest = context_manifest.manifest(
        TASK_TYPE, {"kind": "raw_material", "id": raw["id"]},
        raw["revision"], dependencies,
    )
    return dto, manifest, raw, raw_ref, scopes, current_knowledge


def _schema(dto):
    scopes = dto["scopes"]
    knowledge = dto["current_knowledge"]
    raw = dto["raw"]
    source_ref_schema = {
        "type": "object", "additionalProperties": False,
        "required": ["kind", "id", "revision"],
        "properties": {
            "kind": {"const": "raw_material"}, "id": {"const": raw["id"]},
            "revision": {"const": raw.get("revision", 1)},
        },
    }
    refs = {"type": "array", "minItems": 1, "maxItems": 1, "items": source_ref_schema}
    reason = {"type": "string", "minLength": 1, "maxLength": 1000}
    content = {"type": "string", "minLength": 1, "maxLength": 4000}
    add = {
        "type": "object", "additionalProperties": False,
        "required": ["operation", "scope_type", "scope_id", "knowledge_type", "content", "tags", "source_refs", "reason"],
        "properties": {
            "operation": {"const": "add"},
            "scope_type": {"enum": sorted({item["type"] for item in scopes})},
            "scope_id": {"enum": sorted({item["stable_id"] for item in scopes})},
            "knowledge_type": {"enum": sorted(wiki_api.KNOWLEDGE_TYPES)},
            "content": content,
            "tags": {"type": "array", "maxItems": 20, "uniqueItems": True,
                     "items": {"type": "string", "minLength": 1, "maxLength": 100}},
            "source_refs": refs, "reason": reason,
        },
    }
    target_ids = sorted({item["knowledge_id"] for item in knowledge})
    revisions_by_id = {item["knowledge_id"]: item["revision"] for item in knowledge}
    target = {"enum": target_ids} if target_ids else {"enum": ["__no_current_knowledge__"]}
    revision = {"enum": sorted(set(revisions_by_id.values()))} if revisions_by_id else {"enum": [-1]}
    rewrite = {
        "type": "object", "additionalProperties": False,
        "required": ["operation", "target_knowledge_id", "before_revision", "content", "source_refs", "reason"],
        "properties": {"operation": {"const": "rewrite"}, "target_knowledge_id": target,
                       "before_revision": revision, "content": content,
                       "source_refs": refs, "reason": reason},
    }
    retire = {
        "type": "object", "additionalProperties": False,
        "required": ["operation", "target_knowledge_id", "before_revision", "source_refs", "reason"],
        "properties": {"operation": {"const": "retire"}, "target_knowledge_id": target,
                       "before_revision": revision, "source_refs": refs, "reason": reason},
    }
    return {
        "version": 1, "type": "object", "additionalProperties": False,
        "required": ["patches"],
        "properties": {"patches": {"type": "array", "maxItems": MAX_PATCHES,
                                    "items": {"oneOf": [add, rewrite, retire]}}},
        "example": {"patches": []},
    }


def _exact_keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise Invalid(label + "字段不符合合同")


def _validate_source_refs(value, raw):
    expected = {"kind": "raw_material", "id": raw["id"], "revision": raw["revision"]}
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise Invalid("Patch 必须引用本轮唯一选中的 Raw")
    ref = value[0]
    if (
        set(ref) != {"kind", "id", "revision"}
        or not isinstance(ref.get("kind"), str)
        or not isinstance(ref.get("id"), str)
        or not isinstance(ref.get("revision"), int)
        or isinstance(ref.get("revision"), bool)
        or ref != expected
    ):
        raise Invalid("Patch 必须引用本轮唯一选中的 Raw")
    return [sources.source_ref(raw)]


def _validate_output(result, dto, raw):
    _exact_keys(result, {"patches"}, "Compiler 输出")
    patches = result["patches"]
    if not isinstance(patches, list) or len(patches) > MAX_PATCHES:
        raise Invalid("Compiler Patch 数量不合法")
    scope_keys = {(item["type"], item["stable_id"]) for item in dto["scopes"]}
    current = {item["knowledge_id"]: item for item in dto["current_knowledge"]}
    targets = set()
    validated = []
    for item in patches:
        if not isinstance(item, dict):
            raise Invalid("Compiler Patch 结构不合法")
        operation = item.get("operation")
        if not isinstance(operation, str):
            raise Invalid("Compiler 只允许 add、rewrite、retire")
        if operation == "add":
            _exact_keys(item, {"operation", "scope_type", "scope_id", "knowledge_type", "content", "tags", "source_refs", "reason"}, "add Patch")
            if not isinstance(item["scope_type"], str) or not isinstance(item["scope_id"], str):
                raise Invalid("add Patch 目标不在本轮合法范围内")
            if (item["scope_type"], item["scope_id"]) not in scope_keys:
                raise Invalid("add Patch 目标不在本轮合法范围内")
            if not isinstance(item["knowledge_type"], str) or item["knowledge_type"] not in wiki_api.KNOWLEDGE_TYPES:
                raise Invalid("Wiki 知识类型只能是 Fact、Observation 或 Hypothesis")
            content = wiki_api._text(item["content"], "Patch 内容", 4000)
            tags = wiki_api._tags(item["tags"])
            identity = ("add", item["scope_type"], item["scope_id"], item["knowledge_type"], content)
            patch = {
                "operation": "add", "scope_type": item["scope_type"], "scope_id": item["scope_id"],
                "knowledge_type": item["knowledge_type"], "content": content, "tags": tags,
                "source_refs": _validate_source_refs(item["source_refs"], raw),
                "reason": wiki_api._text(item["reason"], "Patch 原因", 1000),
            }
        elif operation in {"rewrite", "retire"}:
            required_keys = {"operation", "target_knowledge_id", "before_revision", "source_refs", "reason"}
            if operation == "rewrite":
                required_keys.add("content")
            _exact_keys(item, required_keys, operation + " Patch")
            if not isinstance(item["target_knowledge_id"], str) or not item["target_knowledge_id"]:
                raise Invalid("Patch 只能修改本轮上下文中的当前 Wiki")
            if not isinstance(item["before_revision"], int) or isinstance(item["before_revision"], bool):
                raise Invalid("Patch before revision 不合法")
            target = current.get(item["target_knowledge_id"])
            if target is None:
                raise Invalid("Patch 只能修改本轮上下文中的当前 Wiki")
            if item["before_revision"] != target["revision"]:
                raise Invalid("Patch 目标 revision 与本轮输入不一致")
            # A knowledge item may receive at most one semantic action in a
            # proposal; rewrite + retire would make the second decision stale.
            identity = ("knowledge", target["knowledge_id"])
            patch = {
                "operation": operation, "target_knowledge_id": target["knowledge_id"],
                "before_revision": target["revision"],
                "scope_type": target["scope_type"], "scope_id": target["scope_id"],
                "source_refs": _validate_source_refs(item["source_refs"], raw),
                "reason": wiki_api._text(item["reason"], "Patch 原因", 1000),
            }
            if operation == "rewrite":
                patch["content"] = wiki_api._text(item["content"], "Patch 内容", 4000)
        else:
            raise Invalid("Compiler 只允许 add、rewrite、retire")
        if identity in targets:
            raise Invalid("Compiler 重复提议了同一目标")
        targets.add(identity)
        patch["id"] = "wiki-patch:" + uid()
        patch["status"] = "pending"
        validated.append(patch)
    return validated


def _preview(scopes, knowledge, diagnostics):
    return {
        "raw_count": 1,
        "scopes": scopes,
        "wiki_count": len(knowledge),
        "provider": diagnostics.get("provider") or diagnostics.get("mode"),
        "model": diagnostics.get("model"),
        "other_career_data_included": False,
    }


def _readable_context(dto):
    """Project only the DTO's user-meaningful content for the send preview.

    This deliberately takes the already-sanitized DTO, so the UI cannot widen
    the context with a second store read or accidentally show unrelated data.
    Stable IDs and revision markers remain in the provider packet, not in the
    user-facing content projection.
    """
    scopes = [
        {"type": item["type"], "minimal_identity": deepcopy(item["minimal_identity"])}
        for item in dto["scopes"]
    ]
    scope_by_key = {
        (item["type"], item["stable_id"]): item["minimal_identity"]
        for item in dto["scopes"]
    }
    knowledge = []
    for item in dto["current_knowledge"]:
        key = (item["scope_type"], item["scope_id"])
        identity = scope_by_key.get(key)
        if identity is None:
            raise Invalid("当前 Wiki 的归属不在本轮发送范围内")
        knowledge.append({
            "type": item["type"], "content": item["content"],
            "tags": list(item["tags"]), "scope_type": item["scope_type"],
            "scope_identity": deepcopy(identity),
        })
    return {
        "raw": {
            "content": dto["raw"]["content"],
            "created_at": dto["raw"]["created_at"],
        },
        "scopes": scopes,
        "current_knowledge": knowledge,
    }


def _preview_details(dto, diagnostics):
    provider = str(diagnostics.get("provider") or diagnostics.get("mode") or "").lower()
    model = "DeepSeek" if provider == "deepseek" else "测试模型" if provider == "test" else "当前配置"
    type_names = {"project": "项目", "employment": "任职", "person": "人物",
                  "opportunity": "机会", "personal": "个人职业资料"}
    labels = []
    for scope in dto["scopes"]:
        identity = scope["minimal_identity"]
        label = type_names.get(scope["type"])
        if scope["type"] == "project":
            label = f"项目 · {identity.get('name') or '项目'}"
        elif scope["type"] == "employment":
            name = " / ".join(value for value in (identity.get("company"), identity.get("role")) if value)
            label = f"任职 · {name or '任职'}"
        elif scope["type"] == "person":
            role = identity.get("project_role") or identity.get("employment_role")
            label = f"人物 · {identity.get('name') or '人物'}" + (f" · {role}" if role else "")
        elif scope["type"] == "opportunity":
            name = " / ".join(value for value in (identity.get("company"), identity.get("title")) if value)
            label = f"机会 · {name or '机会'}"
        if label and label not in labels:
            labels.append(label)
    return {
        "model": model,
        "raw_count": 1,
        "wiki_count": len(dto["current_knowledge"]),
        "scopes": labels,
    }


def _client_intent(raw_id, model_config_id, idempotency_key):
    return {
        "raw_id": raw_id, "model_config_id": model_config_id,
        "idempotency_key": idempotency_key,
    }


def _operation_input(body, allowed):
    if not isinstance(body, dict) or set(body) - set(allowed):
        raise Invalid("Wiki Compiler 请求字段不合法")
    raw_id = required(body.get("raw_id"), "Raw", 500)
    key = required(body.get("idempotency_key"), "请求标识", 200)
    model_config_id = body.get("model_config_id")
    if model_config_id is not None and (not isinstance(model_config_id, str) or not model_config_id):
        raise Invalid("模型配置不合法")
    return raw_id, key, model_config_id


def _latest_context(store, raw_id):
    with store.connect(False) as c:
        return _make_context(store, c, raw_id)


def _proposal_expected_wiki(proposal):
    expected = {}
    for scope in proposal["scopes"]:
        key = (scope["type"], scope["stable_id"])
        expected[key] = {
            item["knowledge_id"]: item["revision"]
            for item in proposal["initial_wiki"]
            if (item["scope_type"], item["scope_id"]) == key
        }
    for patch in proposal["patches"]:
        if patch.get("status") != "accepted":
            continue
        result = patch.get("resolution", {}).get("result") or {}
        key = (patch["scope_type"], patch["scope_id"])
        if patch["operation"] == "add":
            expected.setdefault(key, {})[result["knowledge_id"]] = result["revision"]
        elif patch["operation"] == "retire":
            expected.setdefault(key, {}).pop(patch["target_knowledge_id"], None)
        else:
            expected.setdefault(key, {})[patch["target_knowledge_id"]] = result["revision"]
    return expected


def _assert_proposal_fresh(store, c, proposal, patch):
    dto, manifest, raw, raw_ref, scopes, wiki = _make_context(store, c, proposal["raw_id"])
    if raw_ref != proposal["raw_ref"]:
        raise Conflict("stale_proposal: Raw 已变化，请重新整理")
    expected_scope_dependencies = proposal["scope_dependencies"]
    actual_scope_dependencies = [
        item for item in manifest["dependencies"]
        if item.get("kind") in {"wiki_scope", "wiki_relation"}
    ]
    if scopes != proposal["scopes"] or actual_scope_dependencies != expected_scope_dependencies:
        raise Conflict("stale_proposal: Raw 的业务范围或关联已变化")
    expected = _proposal_expected_wiki(proposal)
    actual = {key: {} for key in expected}
    for item in wiki:
        key = (item["scope_type"], item["scope_id"])
        actual.setdefault(key, {})[item["knowledge_id"]] = item["revision"]
    if actual != expected:
        raise Conflict("stale_proposal: 当前 Wiki 已变化，请重新整理")
    if (patch["scope_type"], patch["scope_id"]) not in {
        (item["type"], item["stable_id"]) for item in scopes
    }:
        raise Conflict("stale_proposal: Patch 目标范围已不再关联")
    if patch["operation"] in {"rewrite", "retire"}:
        target = store._get(c, patch["target_knowledge_id"], "wiki_knowledge")
        if target.get("revision") != patch["before_revision"]:
            raise Conflict("stale_proposal: Wiki 目标 revision 已变化")
        if (target.get("scope_type"), target.get("scope_id")) != (patch["scope_type"], patch["scope_id"]):
            raise Conflict("stale_proposal: Wiki 目标范围已变化")
    return raw


def _proposal_result(proposal):
    public_patches = []
    for patch in proposal["patches"]:
        item = {key: deepcopy(value) for key, value in patch.items() if key != "resolution"}
        resolution = patch.get("resolution")
        if resolution:
            item["resolution"] = {
                key: deepcopy(resolution[key])
                for key in ("decision", "result", "resolved_at", "edited_reason") if key in resolution
            }
        public_patches.append(item)
    return {
        "id": proposal["id"], "raw_id": proposal["raw_id"],
        "status": proposal["status"], "patches": public_patches,
        "created_at": proposal["created_at"],
    }


def compiler_router(store):
    router = APIRouter()
    gateway = ModelGateway(store)

    @router.post("/api/wiki/compiler/prepare")
    def prepare(body: dict):
        raw_id, key, model_config_id = _operation_input(
            body, {"raw_id", "idempotency_key", "model_config_id"},
        )
        dto, manifest, raw, raw_ref, scopes, knowledge = _latest_context(store, raw_id)
        schema = _schema(dto)
        payload, diagnostics, selected_config, clean_dto, budget_info = gateway.prepare_payload(
            TASK_TYPE, dto, schema, model_config_id,
        )
        gateway_request_hash = digest({
            "model_config_id": selected_config["id"] if selected_config else None,
            "provider": diagnostics.get("provider", "test"),
            "model": diagnostics.get("model"), "payload": payload,
        })
        intent = _client_intent(raw_id, model_config_id, key)
        prepared = outbound_policy.create_preparation(
            store, task_type=TASK_TYPE,
            target={"kind": "raw_material", "id": raw_id},
            client_intent=intent, packet=clean_dto, payload=payload,
            manifest=manifest, diagnostics=diagnostics,
            budget_info=budget_info,
            extra={"gateway_request_hash": gateway_request_hash},
        )
        return {
            "status": prepared["status"], "prepared_id": prepared["prepared_id"],
            "task_type": TASK_TYPE, "target": prepared["target"],
            "payload_hash": prepared["payload_hash"], "expires_at": prepared["expires_at"],
            "preview": _preview(scopes, knowledge, diagnostics),
            "readable_context": _readable_context(clean_dto),
            "preview_details": _preview_details(clean_dto, diagnostics),
        }

    @router.post("/api/wiki/compiler/execute")
    def execute(body: dict):
        allowed = {"raw_id", "idempotency_key", "model_config_id", "prepared_id", "payload_hash", "confirm_outbound"}
        if not isinstance(body, dict) or set(body) - allowed or not {
            "raw_id", "idempotency_key", "prepared_id", "payload_hash", "confirm_outbound",
        }.issubset(body):
            raise Invalid("Wiki Compiler 执行请求字段不合法")
        raw_id, key, model_config_id = _operation_input(
            {name: body[name] for name in ("raw_id", "idempotency_key", "model_config_id") if name in body},
            {"raw_id", "idempotency_key", "model_config_id"},
        )
        prepared_id = required(body.get("prepared_id"), "AI 预览", 500)
        payload_hash = required(body.get("payload_hash"), "AI 预览摘要", 200)
        if body.get("confirm_outbound") is not True:
            raise Invalid("只有明确确认发送后才能调用 Provider")
        intent = {**_client_intent(raw_id, model_config_id, key),
                  "prepared_id": prepared_id, "payload_hash": payload_hash}

        def prepare_operation():
            dto, manifest, raw, raw_ref, scopes, knowledge = _latest_context(store, raw_id)
            schema = _schema(dto)
            payload, diagnostics, selected_config, clean_dto, budget_info = gateway.prepare_payload(
                TASK_TYPE, dto, schema, model_config_id,
            )
            frozen = outbound_policy.validate_preparation(
                store, prepared_id, task_type=TASK_TYPE,
                target={"kind": "raw_material", "id": raw_id},
                client_intent=_client_intent(raw_id, model_config_id, key),
                payload_hash=payload_hash, packet=clean_dto, payload=payload,
                manifest=manifest,
            )
            gateway_request_hash = digest({
                "model_config_id": selected_config["id"] if selected_config else None,
                "provider": diagnostics.get("provider", "test"),
                "model": diagnostics.get("model"), "payload": payload,
            })
            if frozen.get("gateway_request_hash") != gateway_request_hash:
                raise Conflict("prepared_request_stale: 预览后所选模型配置或发送内容已变化，请重新预览")
            return {
                "dto": clean_dto, "manifest": manifest, "schema": schema,
                "payload_hash": digest(payload), "diagnostics": diagnostics,
                "gateway_request_hash": gateway_request_hash,
                "model_config_id": model_config_id, "scopes": scopes,
                "knowledge": knowledge, "raw_ref": raw_ref,
            }

        def dispatch(prepared, binder):
            def before_call(actual_hash):
                _dto, live_manifest, _raw, _ref, _scopes, _knowledge = _latest_context(store, raw_id)
                if live_manifest != prepared["manifest"] or actual_hash != prepared["gateway_request_hash"]:
                    from ..ai_operations import PreDispatchFailure
                    raise PreDispatchFailure("prepared_request_stale: Raw、范围或 Wiki 已变化，请重新预览")
                binder(actual_hash, live_manifest)
            return gateway.generate(
                TASK_TYPE, prepared["dto"], prepared["schema"],
                prepared["model_config_id"], before_call=before_call,
                operation_id=prepared.get("_operation_id"),
                target={"kind": "raw_material", "id": raw_id},
            )

        def persist(prepared, result, diagnostics):
            try:
                with store.connect() as c:
                    dto, live_manifest, raw, raw_ref, scopes, knowledge = _make_context(store, c, raw_id)
                    if live_manifest != prepared["manifest"]:
                        raise Invalid("Provider 返回时 Raw、范围或 Wiki 已变化；没有创建提案")
                    patches = _validate_output(result, dto, raw)
                    if not patches:
                        return {
                            "status": "no_changes", "message": "这份资料没有发现值得更新到 Wiki 的长期知识。",
                            "patch_count": 0,
                        }
                    scope_deps = [
                        item for item in live_manifest["dependencies"]
                        if item.get("kind") in {"wiki_scope", "wiki_relation"}
                    ]
                    proposal = {
                        "id": "wiki-compiler-proposal:" + uid(),
                        "raw_id": raw_id, "raw_ref": raw_ref,
                        "operation_id": prepared.get("_operation_id"),
                        "status": "pending", "created_at": now(),
                        "scopes": scopes, "scope_dependencies": scope_deps,
                        "initial_wiki": [
                            {key: item[key] for key in ("knowledge_id", "revision", "scope_type", "scope_id")}
                            for item in knowledge
                        ],
                        "patches": patches,
                    }
                    store._record(c, "wiki_compiler_proposal", proposal)
                    return {
                        "status": "proposal_pending", "proposal_id": proposal["id"],
                        "patch_count": len(patches),
                    }
            except Exception as exc:
                if isinstance(exc, ai_operations.AIValidationError):
                    raise
                if isinstance(exc, (Invalid, Conflict, Missing)):
                    raise ai_operations.AIValidationError(str(exc), getattr(exc, "code", "invalid_result")) from exc
                raise

        try:
            execution = ai_operations.execute(
                store, task_type=TASK_TYPE, target_kind="raw_material", target_id=raw_id,
                idempotency_key=key, client_intent=intent, prepare=prepare_operation,
                dispatch=dispatch, persist=persist,
            )
        except ai_operations.PreDispatchFailure as exc:
            raise Conflict(str(exc)) from exc
        except Exception:
            row = ai_operations.find(store, TASK_TYPE, "raw_material", raw_id, key)
            if row and row.get("state") == "outcome_unknown":
                return JSONResponse({
                    "operation_id": row["op_id"], "status": "outcome_unknown",
                    "state": "outcome_unknown",
                    "message": "Provider 结果未知；不会自动重试，也没有创建 Wiki 提案。",
                }, status_code=409)
            raise
        if execution.state == "succeeded":
            value = execution.value
            if value.get("status") == "proposal_pending":
                with store.connect(False) as c:
                    proposal = store._get(c, value["proposal_id"], "wiki_compiler_proposal", True)
                return {
                    "status": value["status"], "patch_count": value["patch_count"],
                    "proposal": _proposal_result(proposal),
                    "operation_id": value.get("operation_id"),
                }
            return value
        return ai_operations.unwrap(execution)

    @router.get("/api/wiki/compiler/proposals")
    def list_proposals(raw_id: str):
        with store.connect(False) as c:
            items = [item for item in store._records(c, "wiki_compiler_proposal") if item.get("raw_id") == raw_id]
            items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
            return {"proposals": [_proposal_result(item) for item in items]}

    @router.get("/api/wiki/compiler/proposals/{proposal_id}")
    def get_proposal(proposal_id: str):
        with store.connect(False) as c:
            return _proposal_result(store._get(c, proposal_id, "wiki_compiler_proposal", True))

    @router.post("/api/wiki/compiler/proposals/{proposal_id}/patches/{patch_id}/resolve")
    def resolve_patch(proposal_id: str, patch_id: str, body: dict):
        if not isinstance(body, dict) or set(body) - {"decision", "content", "reason", "idempotency_key"}:
            raise Invalid("Patch 审批请求字段不合法")
        decision = body.get("decision")
        if decision not in {"accept", "edit_accept", "reject"}:
            raise Invalid("每次只能接受、编辑后接受或拒绝一条 Patch")
        edited_content = None
        edited_reason = None
        if decision == "edit_accept":
            if ("content" in body) == ("reason" in body):
                raise Invalid("编辑后接受必须只提交正文或退役原因")
            if "content" in body:
                edited_content = wiki_api._text(body.get("content"), "编辑后的 Wiki 内容", 100000)
            else:
                edited_reason = wiki_api._text(body.get("reason"), "编辑后的退役原因", 1000)
        else:
            if "content" in body or "reason" in body:
                raise Invalid("只有编辑后接受才能提交修改内容或退役原因")
        key = required(body.get("idempotency_key"), "请求标识", 200)
        fingerprint = digest({"proposal_id": proposal_id, "patch_id": patch_id,
                              "decision": decision, "content": edited_content,
                              "reason": edited_reason})
        with store.connect() as c:
            proposal = store._get(c, proposal_id, "wiki_compiler_proposal", True)
            patch = next((item for item in proposal["patches"] if item["id"] == patch_id), None)
            if patch is None:
                raise Missing("Wiki Patch 不存在")
            if decision == "edit_accept":
                if patch["operation"] == "retire":
                    if edited_reason is None or edited_content is not None:
                        raise Invalid("退役 Patch 只能编辑退役原因")
                elif edited_content is None or edited_reason is not None:
                    raise Invalid("新增或改写 Patch 只能编辑 Wiki 正文")
            for existing_proposal in store._records(c, "wiki_compiler_proposal"):
                for existing_patch in existing_proposal.get("patches", []):
                    existing_resolution = existing_patch.get("resolution") or {}
                    if existing_resolution.get("idempotency_key") != key:
                        continue
                    if (
                        existing_proposal["id"] == proposal_id
                        and existing_patch["id"] == patch_id
                        and existing_resolution.get("fingerprint") == fingerprint
                    ):
                        return {"proposal": _proposal_result(proposal), "patch": patch, "replay": True}
                    raise Conflict("请求标识已用于另一条 Wiki Patch")
            resolution = patch.get("resolution")
            if resolution:
                if resolution.get("idempotency_key") == key and resolution.get("fingerprint") == fingerprint:
                    return {"proposal": _proposal_result(proposal), "patch": patch, "replay": True}
                raise Conflict("这条 Patch 已经处理，不能重复写入")
            if patch.get("status") != "pending":
                raise Conflict("这条 Patch 已经处理")

            result = None
            if decision != "reject":
                raw = _assert_proposal_fresh(store, c, proposal, patch)
                scope = wiki_api._scope(store, c, patch["scope_type"], patch["scope_id"])
                refs = sources.validate_source_refs(
                    store, c, patch["source_refs"], scope,
                    preserved_refs=(),
                )
                if decision == "edit_accept":
                    edited_value = edited_reason if patch["operation"] == "retire" else edited_content
                    if not edited_value or not edited_value.strip():
                        raise Invalid("编辑后的 Wiki 内容或退役原因不能为空")
                if patch["operation"] == "add":
                    values = wiki_api._knowledge_values(store, c, {
                        "knowledge_type": patch["knowledge_type"],
                        "content": edited_content if decision == "edit_accept" else patch["content"],
                        "tags": patch["tags"], "source_refs": refs,
                    }, scope)
                    result = store._save(c, "wiki_knowledge", {
                        "id": uid(), "scope_type": scope[0], "scope_id": scope[1],
                        **values, "provenance": {"kind": "user"}, "created_at": now(),
                    }, 0)
                else:
                    old = store._get(c, patch["target_knowledge_id"], "wiki_knowledge")
                    if old["revision"] != patch["before_revision"]:
                        raise Conflict("stale_proposal: Wiki 目标 revision 已变化")
                    if patch["operation"] == "rewrite":
                        new_content = edited_content if decision == "edit_accept" else patch["content"]
                        all_refs = list(old.get("source_refs", []))
                        all_refs.extend(ref for ref in refs if ref not in all_refs)
                        values = wiki_api._knowledge_values(store, c, {
                            "knowledge_type": old["knowledge_type"], "content": new_content,
                            "tags": old.get("tags", []), "source_refs": all_refs,
                            "status": old["status"],
                        }, scope, old)
                    else:
                        all_refs = list(old.get("source_refs", []))
                        all_refs.extend(ref for ref in refs if ref not in all_refs)
                        values = wiki_api._knowledge_values(store, c, {
                            "knowledge_type": old["knowledge_type"], "content": old["content"],
                            "tags": old.get("tags", []), "source_refs": all_refs,
                            "status": "retired",
                        }, scope, old)
                    result = store._save(c, "wiki_knowledge", dict(old, **values), patch["before_revision"])

            patch["status"] = "rejected" if decision == "reject" else "accepted"
            patch["resolution"] = {
                "decision": decision, "idempotency_key": key,
                "fingerprint": fingerprint,
                "result": ({"knowledge_id": result["id"], "revision": result["revision"]} if result else None),
                "resolved_at": now(),
            }
            if edited_reason is not None:
                patch["resolution"]["edited_reason"] = edited_reason
            if all(item.get("status") != "pending" for item in proposal["patches"]):
                proposal["status"] = "resolved"
                proposal["resolved_at"] = now()
            store._record(c, "wiki_compiler_proposal", proposal)
            return {"proposal": _proposal_result(proposal), "patch": patch, "replay": False}

    return router
