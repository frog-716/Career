"""D4: synthesize reviewable long-term Cognition from selected experience Wiki."""
from copy import deepcopy
import json
import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .. import ai_operations, context_manifest, outbound_policy, work
from ..core import Conflict, Invalid, Missing, digest, now, required, uid
from ..employment import current_employments
from ..model_gateway import ModelGateway
from . import api as wiki_api
from . import compiler, sources


TASK_TYPE = "wiki_cognition_compiler"
TASK_NAME = "synthesize_long_term_cognition"
MAX_EXPERIENCES = 20
MAX_KNOWLEDGE = 50
MAX_CONTENT_CHARS = 200000


def _selected_experience_refs(value):
    if not isinstance(value, list) or not 2 <= len(value) <= MAX_EXPERIENCES:
        raise Invalid("整理长期认知至少要选择两段项目或任职经历")
    result = []
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"type", "id"}:
            raise Invalid("所选经历格式不合法")
        kind, identifier = item.get("type"), item.get("id")
        if kind not in {"project", "employment"} or not isinstance(identifier, str) or not identifier:
            raise Invalid("长期认知只支持项目或任职经历")
        key = (kind, identifier)
        if key in seen:
            raise Invalid("同一段经历不能重复选择")
        seen.add(key)
        result.append({"type": kind, "id": identifier})
    return sorted(result, key=lambda item: (item["type"], item["id"]))


def supersede_pending_proposal(store, proposal_id, *, expected_operation_id, expected_experiences):
    """System-terminalize a still-pending proposal when its smoke input scope was replaced.

    This is not a user decision and must not be recorded as a rejection. It only
    permits replacing a successful Cognition proposal whose selected scope
    strictly contains the newly approved smoke scope.
    """
    expected = _selected_experience_refs(expected_experiences)
    expected_keys = {(item["type"], item["id"]) for item in expected}
    with store.connect() as c:
        proposal = store._get(c, proposal_id, "wiki_compiler_proposal", True)
        if proposal.get("context_kind") != "cognition" or proposal.get("task_type") != TASK_TYPE:
            raise Conflict("只有长期认知建议可以按此方式终结")
        if proposal.get("status") != "pending":
            raise Conflict("长期认知建议已离开待处理状态")
        if proposal.get("operation_id") != expected_operation_id:
            raise Conflict("长期认知建议与预期操作不匹配")
        selected = _selected_experience_refs(proposal.get("selected_experiences"))
        selected_keys = {(item["type"], item["id"]) for item in selected}
        if not expected_keys.issubset(selected_keys) or len(selected_keys) <= len(expected_keys):
            raise Conflict("这条建议不是来自被替换的更大经历范围")
        operation = c.execute(
            "SELECT task_type, state, target_kind, target_id FROM ai_operations WHERE op_id=?",
            (expected_operation_id,),
        ).fetchone()
        if not operation or tuple(operation) != (TASK_TYPE, "succeeded", "wiki_scope", "cognition"):
            raise Conflict("关联操作不是已成功的长期认知生成")
        patches = proposal.get("patches")
        if not isinstance(patches, list) or not patches or any(
            not isinstance(patch, dict) or patch.get("status") != "pending" for patch in patches
        ):
            raise Conflict("建议条目已被处理或状态不一致")

        resolved_at = now()
        for patch in patches:
            patch["status"] = "superseded"
        proposal["status"] = "superseded"
        proposal["superseded_at"] = resolved_at
        proposal["system_resolution"] = {
            "from_status": "pending",
            "to_status": "superseded",
            "reason_code": "smoke_scope_replaced",
            "operation_id": expected_operation_id,
        }
        store._record(c, "wiki_compiler_proposal", proposal)
        return {"status": "superseded", "patch_count": len(patches)}


def _load_experience(store, c, reference):
    if reference["type"] == "project":
        raw = store._get(c, reference["id"], work.CURRENT["project"])
        project = work._project_view(raw)
        identity = {
            "name": project.get("name", ""),
            "status": project.get("status", "active"),
            "employment_id": work._project_employment_id(project),
        }
        return {
            "type": "project", "id": project["id"],
            "name": project.get("name") or "未命名项目",
            "status": project.get("status", "active"),
            "revision": project.get("revision", 0),
            "identity": identity,
        }
    employment = work._employment(store, c, reference["id"])
    label = " / ".join(value for value in (
        employment.get("company", ""), employment.get("role", ""),
    ) if value) or "任职"
    identity = {
        "company": employment.get("company", ""),
        "role": employment.get("role", ""),
        "start_date": employment.get("start_date"),
        "end_date": employment.get("end_date"),
    }
    return {
        "type": "employment", "id": employment["id"], "name": label,
        "status": "ended" if employment.get("end_date") else "active",
        "revision": employment.get("revision", 0), "identity": identity,
    }


def _knowledge_rows(store, c, scope_type, scope_id):
    rows = c.execute(
        """SELECT body FROM current
             WHERE kind='wiki_knowledge'
               AND json_extract(body,'$.scope_type')=?
               AND json_extract(body,'$.scope_id')=?
               AND json_extract(body,'$.status')='current'
             ORDER BY id""",
        (scope_type, scope_id),
    ).fetchall()
    return [json.loads(row[0]) for row in rows]


def _knowledge_dependency(item, purpose):
    return context_manifest.dependency(
        "wiki_knowledge", item["id"], item["revision"], item,
        purpose, content_hash=digest(item),
    )


def _experience_dependency(item):
    return context_manifest.dependency(
        "work_project" if item["type"] == "project" else "employment",
        item["id"], item["revision"], item["identity"],
        "selected_experience",
    )


def _supporting_ids(store, c, cognition):
    result = []
    seen = set()
    for reference in cognition.get("source_refs", ()):
        if not isinstance(reference, dict) or reference.get("kind") != "wiki_knowledge":
            continue
        row = c.execute(
            """SELECT json_extract(body,'$.scope_type'), json_extract(body,'$.scope_id')
                 FROM current WHERE id=? AND kind='wiki_knowledge'""",
            (reference.get("id"),),
        ).fetchone()
        if not row:
            continue
        scope_type, scope_id = row
        if scope_type not in {"project", "employment"} or not isinstance(scope_id, str):
            continue
        if scope_id not in seen:
            result.append(scope_id)
            seen.add(scope_id)
    return result


def _make_context(store, c, selected_refs):
    selected = _selected_experience_refs(selected_refs)
    experiences = []
    dependencies = []
    source_knowledge = {}
    content_chars = 0
    for reference in selected:
        experience = _load_experience(store, c, reference)
        rows = _knowledge_rows(store, c, experience["type"], experience["id"])
        if not rows:
            raise Invalid("每段所选经历都需要至少一条当前 Wiki 知识")
        rows.sort(key=lambda item: item["id"])
        clean_rows = []
        for item in rows:
            clean = {
                "knowledge_id": item["id"], "type": item["knowledge_type"],
                "content": item["content"], "tags": list(item.get("tags", [])),
            }
            clean_rows.append(clean)
            source_knowledge[item["id"]] = {
                "experience": {
                    "type": experience["type"], "id": experience["id"],
                    "name": experience["name"],
                },
                "source": sources.source_ref({
                    "kind": "wiki_knowledge", "id": item["id"],
                    "revision": item["revision"], "hash": digest(item),
                }),
            }
            content_chars += len(item["content"])
            dependencies.append(_knowledge_dependency(item, "selected_experience_wiki"))
        experiences.append({
            "type": experience["type"], "id": experience["id"],
            "name": experience["name"], "current_knowledge": clean_rows,
        })
        dependencies.append(_experience_dependency(experience))

    if len(source_knowledge) > MAX_KNOWLEDGE:
        raise Invalid("所选经历的当前 Wiki 条目过多，请减少经历范围")

    cognition_rows = _knowledge_rows(store, c, "cognition", "")
    cognition_rows.sort(key=lambda item: item["id"])
    existing = []
    for item in cognition_rows:
        existing.append({
            "id": item["id"], "type": item["knowledge_type"],
            "content": item["content"], "revision": item["revision"],
            "supporting_experience_ids": _supporting_ids(store, c, item),
        })
        content_chars += len(item["content"])
        dependencies.append(_knowledge_dependency(item, "current_cognition"))

    if content_chars > MAX_CONTENT_CHARS:
        raise Invalid("所选经历与已有长期认知超出资料预算")
    dto = {
        "task": TASK_NAME,
        "selected_experiences": experiences,
        "existing_cognition": existing,
    }
    manifest = context_manifest.manifest(
        TASK_TYPE, {"kind": "wiki_scope", "id": "cognition"}, 0,
        sorted(dependencies, key=lambda item: (item["purpose"], item["kind"], item["id"])),
    )
    return dto, manifest, selected, source_knowledge, cognition_rows, experiences


def _schema(dto):
    source_ids = sorted(
        item["knowledge_id"]
        for experience in dto["selected_experiences"]
        for item in experience["current_knowledge"]
    )
    def refs(min_items):
        return {
            "type": "array", "minItems": min_items,
            "maxItems": min(len(source_ids), MAX_KNOWLEDGE), "uniqueItems": True,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["knowledge_id"],
                "properties": {"knowledge_id": {"enum": source_ids}},
            },
        }
    reason = {"type": "string", "minLength": 1, "maxLength": 1000}
    content = {"type": "string", "minLength": 1, "maxLength": 4000}
    tags = {"type": "array", "maxItems": 20, "uniqueItems": True,
            "items": {"type": "string", "minLength": 1, "maxLength": 100}}
    add = {
        "type": "object", "additionalProperties": False,
        "required": ["operation", "knowledge_type", "content", "tags", "source_refs", "reason"],
        "properties": {
            "operation": {"const": "add"},
            "knowledge_type": {"enum": sorted(wiki_api.KNOWLEDGE_TYPES)},
            "content": content, "tags": tags, "source_refs": refs(2), "reason": reason,
        },
    }
    existing = dto["existing_cognition"]
    operations = [add]
    for target_item in existing:
        target = {"const": target_item["id"]}
        revision = {"const": target_item["revision"]}
        operations.extend((
            {
                "type": "object", "additionalProperties": False,
                "required": ["operation", "target_knowledge_id", "before_revision", "content", "source_refs", "reason"],
                "properties": {
                    "operation": {"const": "rewrite"}, "target_knowledge_id": target,
                    "before_revision": revision, "content": content,
                    "source_refs": refs(2), "reason": reason,
                },
            },
            {
                "type": "object", "additionalProperties": False,
                "required": ["operation", "target_knowledge_id", "before_revision", "source_refs", "reason"],
                "properties": {
                    "operation": {"const": "retire"}, "target_knowledge_id": target,
                    "before_revision": revision, "source_refs": refs(1), "reason": reason,
                },
            },
        ))
    first_refs = []
    seen_experiences = set()
    for experience in dto["selected_experiences"]:
        if experience["id"] in seen_experiences or not experience["current_knowledge"]:
            continue
        seen_experiences.add(experience["id"])
        first_refs.append({"knowledge_id": experience["current_knowledge"][0]["knowledge_id"]})
        if len(first_refs) == 2:
            break
    example_patch = {
        "operation": "add", "knowledge_type": "observation",
        "content": "在两段虚构经历中，都先明确系统边界再开始实现。",
        "tags": ["示例"], "source_refs": first_refs,
        "reason": "两段虚构经历的当前 Wiki 都支持这一观察。",
    }
    return {
        "version": 1, "type": "object", "additionalProperties": False,
        "required": ["patches"],
        "properties": {"patches": {"type": "array", "maxItems": compiler.MAX_PATCHES,
                                    "items": {"oneOf": operations}}},
        "example": {"patches": [example_patch]},
    }


_SCORE = re.compile(
    r"(?:\d{1,4}\s*(?:分|%|/\s*(?:100|10|5))"
    r"|(?:执行力|领导力|沟通能力|抗压能力|管理能力|情商|智商).{0,12}\d{1,4}"
    r"|(?:评分|得分|分数|指数).{0,8}\d{1,4})"
)
_PSYCHOLOGY_TERMS = (
    "人格", "心理分析", "控制型", "完美主义", "内向型", "外向型",
    "抑郁症", "焦虑症", "偏执型", "自恋型", "讨好型人格",
)


class CognitionOutputInvalid(Invalid):
    """A model result failed a strict rule; expose only a fixed code and JSON path."""

    def __init__(self, code, field_path):
        self.code = code
        self.diagnostics = {"field_path": field_path}
        self.field_path = field_path
        super().__init__("AI 返回的结果无法安全使用，本次没有修改长期认知。")


def _output_error(code, field_path):
    raise CognitionOutputInvalid(code, field_path)


def _safe_cognition_text(value, field_path, *, field="content", limit=4000):
    code_prefix = "content" if field == "content" else "reason" if field == "reason" else "tag"
    if not isinstance(value, str):
        _output_error(code_prefix + "_wrong_type", field_path)
    if not value.strip():
        _output_error(code_prefix + "_empty", field_path)
    if len(value) > limit:
        _output_error(code_prefix + "_invalid_length", field_path)
    text = value
    if _SCORE.search(text) or any(term in text for term in _PSYCHOLOGY_TERMS):
        _output_error("content_policy_violation", field_path)
    return text


def _validate_source_ids(value, source_knowledge, *, min_experiences, field_path):
    if not isinstance(value, list) or not value or len(value) > MAX_KNOWLEDGE:
        _output_error("source_experiences_missing", field_path)
    ids, experience_keys = set(), set()
    ordered_ids = []
    result = []
    for index, item in enumerate(value):
        item_path = f"{field_path}[{index}]"
        if not isinstance(item, dict):
            _output_error("source_wiki_invalid", item_path)
        extra = set(item) - {"knowledge_id"}
        if extra:
            _output_error("extra_field", item_path + ".<extra_field>")
        if "knowledge_id" not in item:
            _output_error("source_wiki_invalid", item_path + ".knowledge_id")
        identifier = item.get("knowledge_id")
        if not isinstance(identifier, str) or identifier not in source_knowledge:
            _output_error("source_experience_unknown", item_path + ".knowledge_id")
        if identifier in ids:
            _output_error("source_wiki_invalid", item_path + ".knowledge_id")
        ids.add(identifier)
        ordered_ids.append(identifier)
        source = source_knowledge[identifier]
        experience = source["experience"]
        experience_keys.add((experience["type"], experience["id"]))
        result.append(source["source"])
    if len(experience_keys) < min_experiences:
        _output_error("source_experiences_insufficient", field_path)
    experiences = []
    seen_experiences = set()
    for identifier in ordered_ids:
        experience = source_knowledge[identifier]["experience"]
        key = (experience["type"], experience["id"])
        if key not in seen_experiences:
            seen_experiences.add(key)
            experiences.append(experience)
    return result, experiences


def _validate_output(result, dto, source_knowledge):
    if not isinstance(result, dict):
        _output_error("top_level_invalid", "$")
    extra = set(result) - {"patches"}
    if extra:
        _output_error("extra_field", "$.<extra_field>")
    if "patches" not in result:
        _output_error("patches_missing", "$.patches")
    patches = result["patches"]
    if not isinstance(patches, list) or len(patches) > compiler.MAX_PATCHES:
        _output_error("patch_wrong_type", "$.patches")
    current = {item["id"]: item for item in dto["existing_cognition"]}
    targets, validated = set(), []
    for index, item in enumerate(patches):
        path = f"$.patches[{index}]"
        if not isinstance(item, dict):
            _output_error("patch_wrong_type", path)
        operation = item.get("operation")
        if not isinstance(operation, str) or operation not in {"add", "rewrite", "retire"}:
            _output_error("operation_invalid", path + ".operation")
        if operation == "add":
            allowed = {
                "operation", "knowledge_type", "content", "tags", "source_refs", "reason",
            }
            extra = set(item) - allowed
            if extra:
                _output_error("extra_field", path + ".<extra_field>")
            for field in sorted(allowed - set(item)):
                code = {
                    "content": "content_missing",
                    "source_refs": "source_experiences_missing",
                    "knowledge_type": "knowledge_type_invalid",
                    "reason": "reason_missing",
                    "tags": "tags_invalid",
                }.get(field, "patch_field_missing")
                _output_error(code, path + "." + field)
            if not isinstance(item["knowledge_type"], str) or item["knowledge_type"] not in wiki_api.KNOWLEDGE_TYPES:
                _output_error("knowledge_type_invalid", path + ".knowledge_type")
            content = _safe_cognition_text(item["content"], path + ".content", field="content")
            refs, supporting = _validate_source_ids(
                item["source_refs"], source_knowledge, min_experiences=2,
                field_path=path + ".source_refs",
            )
            if not isinstance(item["tags"], list) or len(item["tags"]) > 20:
                _output_error("tags_invalid", path + ".tags")
            tags = []
            for tag_index, tag in enumerate(item["tags"]):
                tag_path = f"{path}.tags[{tag_index}]"
                clean_tag = _safe_cognition_text(tag, tag_path, field="tag", limit=100)
                if clean_tag.strip() != clean_tag or clean_tag in tags:
                    _output_error("tags_invalid", tag_path)
                tags.append(clean_tag)
            reason = _safe_cognition_text(
                item["reason"], path + ".reason", field="reason", limit=1000,
            )
            identity = ("add", item["knowledge_type"], content)
            patch = {
                "operation": "add", "scope_type": "cognition", "scope_id": "",
                "knowledge_type": item["knowledge_type"], "content": content,
                "tags": tags, "source_refs": refs, "reason": reason,
                "supporting_experiences": supporting,
            }
        elif operation in {"rewrite", "retire"}:
            required = {"operation", "target_knowledge_id", "before_revision", "source_refs", "reason"}
            if operation == "rewrite":
                required.add("content")
            extra = set(item) - required
            if extra:
                _output_error("extra_field", path + ".<extra_field>")
            for field in sorted(required - set(item)):
                code = {
                    "target_knowledge_id": "target_missing",
                    "before_revision": "target_revision_mismatch",
                    "source_refs": "source_experiences_missing",
                    "content": "content_missing",
                    "reason": "reason_missing",
                }.get(field, "patch_field_missing")
                _output_error(code, path + "." + field)
            identifier = item.get("target_knowledge_id")
            if not isinstance(identifier, str):
                _output_error("target_missing", path + ".target_knowledge_id")
            target = current.get(identifier)
            revision = item.get("before_revision")
            if not target:
                _output_error("target_missing", path + ".target_knowledge_id")
            if type(revision) is not int or revision != target["revision"]:
                _output_error("target_revision_mismatch", path + ".before_revision")
            refs, supporting = _validate_source_ids(
                item["source_refs"], source_knowledge,
                min_experiences=2 if operation == "rewrite" else 1,
                field_path=path + ".source_refs",
            )
            identity = ("knowledge", identifier)
            patch = {
                "operation": operation, "target_knowledge_id": identifier,
                "before_revision": revision, "scope_type": "cognition", "scope_id": "",
                "knowledge_type": target["type"],
                "source_refs": refs,
                "reason": _safe_cognition_text(
                    item["reason"], path + ".reason", field="reason", limit=1000,
                ),
                "supporting_experiences": supporting,
            }
            if operation == "rewrite":
                patch["content"] = _safe_cognition_text(
                    item["content"], path + ".content", field="content",
                )
        if identity in targets:
            raise Invalid("长期认知重复提议了同一目标")
        targets.add(identity)
        patch["id"] = "wiki-patch:" + uid()
        patch["status"] = "pending"
        validated.append(patch)
    return validated


def _client_intent(selected, model_config_id, key):
    return {
        "selected_experiences": deepcopy(selected),
        "model_config_id": model_config_id, "idempotency_key": key,
    }


def _prepare_input(body, allowed):
    if not isinstance(body, dict) or set(body) - allowed:
        raise Invalid("长期认知请求字段不合法")
    selected = _selected_experience_refs(body.get("selected_experiences"))
    key = required(body.get("idempotency_key"), "请求标识", 200)
    model_config_id = body.get("model_config_id")
    if model_config_id is not None and (not isinstance(model_config_id, str) or not model_config_id):
        raise Invalid("模型配置不合法")
    return selected, key, model_config_id


def _latest_context(store, selected):
    with store.connect(False) as c:
        return _make_context(store, c, selected)


def _selected_dependencies(manifest):
    return [
        item for item in manifest["dependencies"]
        if item.get("purpose") in {"selected_experience", "selected_experience_wiki"}
    ]


def _assert_proposal_fresh(store, c, proposal, patch):
    dto, manifest, selected, _source_map, _cognition, _experiences = _make_context(
        store, c, proposal["selected_experiences"],
    )
    if selected != proposal["selected_experiences"]:
        raise Conflict("stale_proposal: 所选经历范围已变化")
    if _selected_dependencies(manifest) != proposal["selected_dependencies"]:
        raise Conflict("stale_proposal: 所选经历或 Wiki 知识已变化")
    expected = compiler._proposal_expected_wiki(proposal)
    actual = {("cognition", ""): {item["id"]: item["revision"] for item in _cognition_rows(store, c)}}
    if actual != expected:
        raise Conflict("stale_proposal: 当前长期认知已变化")
    if patch["scope_type"] != "cognition" or patch["scope_id"] != "":
        raise Conflict("stale_proposal: Patch 不属于长期认知")
    if patch["operation"] in {"rewrite", "retire"}:
        target = store._get(c, patch["target_knowledge_id"], "wiki_knowledge")
        if target.get("revision") != patch["before_revision"]:
            raise Conflict("stale_proposal: 长期认知目标已变化")
    return None


def _cognition_rows(store, c):
    return _knowledge_rows(store, c, "cognition", "")


def _experience_status(store, c, experience):
    try:
        value = _load_experience(store, c, {"type": experience["type"], "id": experience["id"]})
    except Missing:
        return None
    return {
        "type": value["type"], "id": value["id"], "name": value["name"],
    }


def _source_trace(store, c, cognition):
    traces = []
    seen = set()
    for ref in cognition.get("source_refs", ()):
        if not isinstance(ref, dict) or ref.get("kind") != "wiki_knowledge":
            continue
        identifier, revision = ref.get("id"), ref.get("revision")
        row = c.execute(
            """SELECT json_extract(body,'$.scope_type'), json_extract(body,'$.scope_id')
                 FROM revisions WHERE id=? AND revision=?""",
            (identifier, revision),
        ).fetchone()
        if not row or row[0] not in {"project", "employment"}:
            continue
        row = c.execute(
            "SELECT body FROM revisions WHERE id=? AND revision=?",
            (identifier, revision),
        ).fetchone()
        if not row:
            continue
        source = json.loads(row[0])
        if digest(source) != ref.get("hash"):
            continue
        if source.get("scope_type") not in {"project", "employment"}:
            continue
        key = (source["scope_type"], source["scope_id"], source["id"])
        if key in seen:
            continue
        seen.add(key)
        experience = _experience_status(store, c, {"type": source["scope_type"], "id": source["scope_id"]})
        if not experience:
            continue
        current = store._get(c, source["id"], "wiki_knowledge")
        raw_refs = []
        for raw_ref in source.get("source_refs", ()):
            if (
                not isinstance(raw_ref, dict)
                or raw_ref.get("kind") not in sources.RAW_RECORD_KINDS
                or not all(key in raw_ref for key in ("id", "revision", "hash"))
            ):
                continue
            raw_refs.append({
                "source_ref": {
                    key: deepcopy(raw_ref[key])
                    for key in ("kind", "id", "revision", "hash")
                },
            })
        traces.append({
            "experience": experience,
            "wiki_knowledge": {
                "id": source["id"], "type": source.get("knowledge_type"),
                "content": source.get("content", ""), "tags": list(source.get("tags", [])),
                "revision": source.get("revision"), "source_ref": deepcopy(ref),
                "version_changed": (current.get("revision"), digest(current)) != (
                    ref.get("revision"), ref.get("hash"),
                ),
            },
            "raw_sources": raw_refs,
        })
    return traces


def _with_supporting_experiences(store, c, item):
    traces = _source_trace(store, c, item)
    experiences = []
    seen = set()
    for trace in traces:
        key = (trace["experience"]["type"], trace["experience"]["id"])
        if key not in seen:
            seen.add(key)
            experiences.append(trace["experience"])
    return dict(item, supporting_experiences=experiences)


def cognition_router(store, *, allow_compiler_start=False):
    router = APIRouter()
    gateway = ModelGateway(store)

    @router.get("/api/wiki/cognition/experiences")
    def list_experiences():
        with store.connect(False) as c:
            result = []
            for project in store._current(c, work.CURRENT["project"]):
                item = work._project_view(project)
                result.append({
                    "type": "project", "id": item["id"],
                    "name": item.get("name") or "未命名项目",
                    "status": item.get("status", "active"),
                    "current_knowledge_count": len(_knowledge_rows(store, c, "project", item["id"])),
                })
            for employment in current_employments(store, c):
                result.append({
                    "type": "employment", "id": employment["id"],
                    "name": " / ".join(value for value in (
                        employment.get("company", ""), employment.get("role", ""),
                    ) if value) or "任职",
                    "status": "ended" if employment.get("end_date") else "active",
                    "current_knowledge_count": len(_knowledge_rows(store, c, "employment", employment["id"])),
                })
            result.sort(key=lambda item: (item["type"], item["name"].casefold(), item["id"]))
            return {"experiences": result}

    @router.get("/api/wiki/cognition/workspace")
    def read_workspace():
        with store.connect(False) as c:
            rows = [item for item in store._current(c, "wiki_knowledge")
                    if item.get("scope_type") == "cognition" and item.get("scope_id") == ""]
            current = [_with_supporting_experiences(store, c, item)
                       for item in rows if item.get("status") == "current"]
            retired = [_with_supporting_experiences(store, c, item)
                       for item in rows if item.get("status") == "retired"]
            proposals = [item for item in store._records(c, "wiki_compiler_proposal")
                         if item.get("context_kind") == "cognition"]
            proposals.sort(key=lambda item: item.get("created_at", ""), reverse=True)
            return {
                "knowledge": current, "retired": retired,
                "proposals": [compiler._proposal_result(item) for item in proposals],
            }

    @router.get("/api/wiki/cognition/knowledge/{knowledge_id}/sources")
    def read_cognition_sources(knowledge_id: str):
        with store.connect(False) as c:
            item = store._get(c, knowledge_id, "wiki_knowledge")
            if (item.get("scope_type"), item.get("scope_id")) != ("cognition", ""):
                raise Missing("长期认知不存在")
            return {"knowledge_id": knowledge_id, "sources": _source_trace(store, c, item)}

    @router.post("/api/wiki/cognition/compiler/prepare")
    def prepare(body: dict):
        if not allow_compiler_start:
            raise Conflict("cognition_compiler_retired: 自动长期认知提炼已停用")
        selected, key, model_config_id = _prepare_input(
            body, {"selected_experiences", "idempotency_key", "model_config_id"},
        )
        dto, manifest, _selected, _source_map, _cognition, _experiences = _latest_context(store, selected)
        schema = _schema(dto)
        payload, diagnostics, selected_config, clean_dto, budget_info = gateway.prepare_payload(
            TASK_TYPE, dto, schema, model_config_id,
        )
        gateway_hash = digest({
            "model_config_id": selected_config["id"] if selected_config else None,
            "provider": diagnostics.get("provider", "test"),
            "model": diagnostics.get("model"), "payload": payload,
        })
        intent = _client_intent(selected, model_config_id, key)
        prepared = outbound_policy.create_preparation(
            store, task_type=TASK_TYPE,
            target={"kind": "wiki_scope", "id": "cognition"},
            client_intent=intent, packet=clean_dto, payload=payload,
            manifest=manifest, diagnostics=diagnostics, budget_info=budget_info,
            extra={"gateway_request_hash": gateway_hash},
        )
        return {
            "status": prepared["status"], "prepared_id": prepared["prepared_id"],
            "task_type": TASK_TYPE, "payload_hash": prepared["payload_hash"],
            "expires_at": prepared["expires_at"],
            "selected_experiences": selected,
            "readable_context": deepcopy(clean_dto),
            "preview": {
                "experience_count": len(clean_dto["selected_experiences"]),
                "wiki_count": sum(len(item["current_knowledge"])
                                   for item in clean_dto["selected_experiences"]),
                "other_career_data_included": False,
            },
            "preview_details": {
                "model": "测试模型" if diagnostics.get("mode") == "test" else diagnostics.get("model"),
                "experiences": [item["name"] for item in clean_dto["selected_experiences"]],
            },
        }

    @router.post("/api/wiki/cognition/compiler/execute")
    def execute(body: dict):
        if not allow_compiler_start:
            raise Conflict("cognition_compiler_retired: 自动长期认知提炼已停用")
        allowed = {
            "selected_experiences", "idempotency_key", "model_config_id",
            "prepared_id", "payload_hash", "confirm_outbound",
        }
        required_fields = {"selected_experiences", "idempotency_key", "prepared_id",
                           "payload_hash", "confirm_outbound"}
        if not isinstance(body, dict) or set(body) - allowed or not required_fields.issubset(body):
            raise Invalid("长期认知确认请求字段不合法")
        selected, key, model_config_id = _prepare_input(
            {field: body[field] for field in ("selected_experiences", "idempotency_key", "model_config_id")
             if field in body},
            {"selected_experiences", "idempotency_key", "model_config_id"},
        )
        prepared_id = required(body.get("prepared_id"), "AI 预览", 500)
        payload_hash = required(body.get("payload_hash"), "AI 预览摘要", 200)
        if body.get("confirm_outbound") is not True:
            raise Invalid("只有用户明确确认后才能调用 Provider")
        intent = {**_client_intent(selected, model_config_id, key),
                  "prepared_id": prepared_id, "payload_hash": payload_hash}

        def prepare_operation():
            dto, manifest, _refs, _source_map, _cognition, _experiences = _latest_context(store, selected)
            schema = _schema(dto)
            payload, diagnostics, selected_config, clean_dto, budget_info = gateway.prepare_payload(
                TASK_TYPE, dto, schema, model_config_id,
            )
            frozen = outbound_policy.validate_preparation(
                store, prepared_id, task_type=TASK_TYPE,
                target={"kind": "wiki_scope", "id": "cognition"},
                client_intent=_client_intent(selected, model_config_id, key),
                packet=clean_dto, payload=payload, manifest=manifest,
                payload_hash=payload_hash,
            )
            actual_gateway_hash = digest({
                "model_config_id": selected_config["id"] if selected_config else None,
                "provider": diagnostics.get("provider", "test"),
                "model": diagnostics.get("model"), "payload": payload,
            })
            if frozen.get("gateway_request_hash") != actual_gateway_hash:
                raise Conflict("prepared_request_stale: 模型配置或发送内容已变化，请重新预览")
            return {
                "dto": clean_dto, "manifest": manifest, "schema": schema,
                "diagnostics": diagnostics, "gateway_request_hash": actual_gateway_hash,
                "model_config_id": model_config_id, "payload_hash": digest(payload),
                "budget": budget_info,
            }

        def dispatch(prepared, binder):
            def before_call(actual_hash):
                _dto, live_manifest, *_rest = _latest_context(store, selected)
                if live_manifest != prepared["manifest"] or actual_hash != prepared["gateway_request_hash"]:
                    raise ai_operations.PreDispatchFailure(
                        "prepared_request_stale: 所选经历或当前 Wiki 已变化，请重新预览",
                    )
                binder(actual_hash, live_manifest)
            return gateway.generate(
                TASK_TYPE, prepared["dto"], prepared["schema"],
                prepared["model_config_id"], before_call=before_call,
                operation_id=prepared.get("_operation_id"),
                target={"kind": "wiki_scope", "id": "cognition"},
            )

        def persist(prepared, result, diagnostics):
            try:
                with store.connect() as c:
                    dto, live_manifest, _refs, source_map, cognition_rows, experiences = _make_context(
                        store, c, selected,
                    )
                    if live_manifest != prepared["manifest"]:
                        raise Invalid("Provider 返回时所选经历或 Wiki 已变化；没有创建提案")
                    patches = _validate_output(result, dto, source_map)
                    if not patches:
                        return {
                            "status": "no_changes",
                            "message": "这些经历中暂时没有发现值得沉淀为长期认知的新模式。",
                            "patch_count": 0,
                        }
                    experience_deps = _selected_dependencies(live_manifest)
                    proposal = {
                        "id": "wiki-compiler-proposal:" + uid(),
                        "context_kind": "cognition", "task_type": TASK_TYPE,
                        "selected_experiences": deepcopy(selected),
                        "selected_dependencies": experience_deps,
                        "operation_id": prepared.get("_operation_id"),
                        "status": "pending", "created_at": now(),
                        "scopes": [{"type": "cognition", "stable_id": "", "minimal_identity": {}}],
                        "scope_dependencies": [],
                        "initial_wiki": [
                            {"knowledge_id": item["id"], "revision": item["revision"],
                             "scope_type": "cognition", "scope_id": ""}
                            for item in cognition_rows
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
                if isinstance(exc, CognitionOutputInvalid):
                    raise ai_operations.AIValidationError(
                        str(exc), exc.code, field_path=exc.field_path,
                    ) from exc
                if isinstance(exc, (Invalid, Conflict, Missing)):
                    raise ai_operations.AIValidationError(
                        str(exc), getattr(exc, "code", "invalid_result"),
                    ) from exc
                raise

        try:
            execution = ai_operations.execute(
                store, task_type=TASK_TYPE, target_kind="wiki_scope", target_id="cognition",
                idempotency_key=key, client_intent=intent,
                prepare=prepare_operation, dispatch=dispatch, persist=persist,
            )
        except ai_operations.PreDispatchFailure as exc:
            raise Conflict(str(exc)) from exc
        except Exception:
            operation = ai_operations.find(store, TASK_TYPE, "wiki_scope", "cognition", key)
            if operation and operation.get("state") == "outcome_unknown":
                return JSONResponse({
                    "operation_id": operation["op_id"], "status": "outcome_unknown",
                    "state": "outcome_unknown",
                    "message": "Provider 结果未知；不会自动重试，也没有创建长期认知提案。",
                }, status_code=409)
            raise
        if execution.state != "succeeded":
            return ai_operations.unwrap(execution)
        value = execution.value
        if value.get("status") == "proposal_pending":
            with store.connect(False) as c:
                proposal = store._get(c, value["proposal_id"], "wiki_compiler_proposal", True)
            return {
                "status": value["status"], "patch_count": value["patch_count"],
                "proposal": compiler._proposal_result(proposal),
                "operation_id": value.get("operation_id"),
            }
        return value

    @router.get("/api/wiki/cognition/proposals")
    def list_proposals():
        with store.connect(False) as c:
            items = [item for item in store._records(c, "wiki_compiler_proposal")
                     if item.get("context_kind") == "cognition"]
            items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
            return {"proposals": [compiler._proposal_result(item) for item in items]}

    return router
