"""Opportunity-owned current resumes; immutable versions reuse the paper editor."""
from contextlib import contextmanager
from copy import deepcopy
import json
import html
import re
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from .core import Conflict, Invalid, Missing, digest, dump, now, uid
from .editor import apply_profile, blank_document, fact_allowed, item_ids, validate_document
from . import opportunity as op
from . import ai_operations as ao
from . import context_manifest as cm
from . import research_store as rs
from . import resume_artifacts as files
from .model_gateway import ModelGateway
from .resume_pdf import render_pdf
from . import outbound_policy as outbound
from .resume_ai_context import resume_document_context, research_context
from .resume_career_retrieval import read_selected_context, search_candidates
from .wiki import sources as wiki_sources


def strict(body, fields):
    if not isinstance(body,dict) or set(body)-set(fields):raise Invalid('包含不允许的字段')


def revision(value):
    if type(value) is not int or value<0:raise Invalid('expected_revision必须是非负整数')
    return value


def get_document(store,c,did):
    row=c.execute("SELECT revision,body FROM current WHERE id=? AND kind='resume_document'",(did,)).fetchone()
    if not row:raise Missing('简历工作稿不存在，请先明确选择来源')
    d=json.loads(row[1]);op.writable(store,c,d['opportunity_id'])
    return dict(d,document_id=d['id'],revision=row[0])


def for_opportunity(c,oid):
    row=c.execute("SELECT id FROM current WHERE kind='resume_document' AND json_extract(body,'$.opportunity_id')=?",(oid,)).fetchone()
    return row[0] if row else None


def save_document(c,store,document,expected,did):
    old=get_document(store,c,did)
    if revision(expected)!=old['revision']:raise Conflict('工作稿已更新，请保留输入并比较')
    obj={k:v for k,v in old.items() if k not in ('revision','document_id')}
    obj.update(document=validate_document(document),savedAt=now())
    c.execute('UPDATE current SET revision=?,body=? WHERE id=? AND revision=?',(expected+1,dump(obj),did,expected))
    return dict(obj,document_id=did,revision=expected+1)


def copy_source(store,c,source):
    if not isinstance(source,dict):raise Invalid('请明确选择简历来源')
    kind=source.get('kind')
    if kind=='blank':
        strict(source,{'kind'})
        document=blank_document()
        document['sections']=[
            dict(id='section-skills',type='skills',title='专业技能',items=[]),
            dict(id='section-experience',type='experience',title='工作经历',items=[]),
            dict(id='section-projects',type='projects',title='项目经历',items=[]),
            dict(id='section-education',type='education',title='教育背景',items=[]),
        ]
        return document,dict(kind='blank')
    if kind=='legacy_draft':
        strict(source,{'kind','source_revision','source_hash'})
        row=c.execute("SELECT revision,body FROM current WHERE id='editor-main' AND kind='editor_draft'").fetchone()
        if not row:raise Missing('历史工作稿不存在')
        doc=json.loads(row[1])['document']
        if revision(source.get('source_revision'))!=row[0] or source.get('source_hash')!=digest(doc):raise Conflict('历史来源已变化，请重新选择')
        provenance=dict(kind=kind,source_id='editor-main',source_revision=row[0],source_hash=digest(doc))
    elif kind=='version':
        strict(source,{'kind','source_version_id','source_document_hash'})
        v=store._get(c,source.get('source_version_id'),'editor_version',True);doc=v['document']
        if source.get('source_document_hash')!=digest(doc):raise Conflict('版本来源hash不一致')
        provenance=dict(kind=kind,source_version_id=v['id'],source_hash=digest(doc))
    else:raise Invalid('仅支持blank/version/明确选择legacy_draft，不支持外部JSON导入')
    doc=deepcopy(validate_document(doc))
    # Copy expression, never confer target-scope fact authorization on foreign refs.
    provenance['source_refs']=doc['meta'].pop('source_refs',[])
    return doc,provenance


def create_document(store,c,oid,doc,provenance):
    if for_opportunity(c,oid):raise Conflict('该机会已有工作稿，请打开原稿')
    obj=dict(id=uid(),opportunity_id=oid,document=doc,provenance=provenance,savedAt=now())
    c.execute('INSERT INTO current VALUES(?,?,?,?)',(obj['id'],'resume_document',0,dump(obj)))
    return dict(obj,document_id=obj['id'],revision=0)


@contextmanager
def material_transaction(store):
    try:
        with store.connect() as c:
            files.recover(c,store.data_dir)
            yield c
            files.fault('before_commit')
        files.fault('after_commit')
    except Exception:
        # DB is authoritative, including an ambiguous response after COMMIT.
        with store.connect() as c:files.recover(c,store.data_dir)
        raise


def version_summary(v):
    return {k:v.get(k) for k in ('id','name','createdAt','artifact_id','document_id','opportunity_id','version_kind','submission_id','document_hash','renderer_version')}


def insert_version(store,c,d,doc,raw,kind,name,key,submission_id=None,source_version_id=None,rendered=None):
    aid,vid,stamp=uid(),uid(),now()
    render_metadata = {}
    if rendered:
        render_metadata = {
            'renderer_version': rendered.renderer_version,
        }
    artifact_metadata = dict(render_metadata)
    if rendered:
        artifact_metadata['document_hash'] = rendered.document_hash
    artifact=files.stage_pdf(store.data_dir,aid,vid,raw,stamp,artifact_metadata)
    v=dict(id=vid,name=name,createdAt=stamp,document=deepcopy(doc),document_hash=digest(doc),
           document_id=d['id'],opportunity_id=d['opportunity_id'],artifact_id=aid,
           version_kind=kind,idempotency_key=key,**render_metadata)
    if submission_id:v['submission_id']=submission_id
    if source_version_id:v['source_version_id']=source_version_id
    c.execute('INSERT INTO records VALUES(?,?,?)',(aid,'artifact',dump(artifact)))
    c.execute('INSERT INTO records VALUES(?,?,?)',(vid,'editor_version',dump(v)))
    files.fault('after_version')
    return v,artifact


def owns_version(store,c,did,vid):
    get_document(store,c,did)
    v=store._get(c,vid,'editor_version',True)
    if v.get('document_id')!=did:raise Conflict('版本不属于此工作稿；跨来源请明确复制')
    return v


def _resume_ai_packet(store, c, d, instruction, selected_context=(), evidence_context=()):
    opportunity = op.resolve(store, c, d['opportunity_id'])
    sources = [
        {"id": opportunity["id"], "revision": opportunity["revision"], "purpose": "opportunity", "selected_content": {
            "company": opportunity["company"], "title": opportunity["title"], "jd": opportunity.get("jd", ""),
        }},
        {"id": d["id"], "revision": d["revision"], "purpose": "current_resume_document", "selected_content": resume_document_context(d["document"])},
    ]
    company, company_exists = rs.lookup(store, c, "company_research", opportunity["company_id"])
    research, research_exists = rs.lookup(store, c, "opportunity_research", opportunity["id"])
    if company["items"]: sources.append({"id": company["id"], "revision": company["revision"], "purpose": "company_research", "selected_content": research_context(company["items"])})
    if research["items"]: sources.append({"id": research["id"], "revision": research["revision"], "purpose": "opportunity_research", "selected_content": research_context(research["items"])})
    dependencies = [
        cm.dependency("opportunity", opportunity["id"], opportunity["revision"],
                      cm.selected_opportunity(opportunity), "current_jd"),
        cm.dependency("resume_document", d["id"], d["revision"], d["document"], "current_resume_document"),
    ]
    for kind, document, exists, purpose, owner in (
        ("company_research", company, company_exists, "company_research", opportunity["company_id"]),
        ("opportunity_research", research, research_exists, "opportunity_research", opportunity["id"]),
    ):
        dependencies.append(cm.dependency(
            kind, document["id"], document["revision"],
            rs.content_hash(document) if exists else None, purpose,
            content_hash=rs.content_hash(document) if exists else None,
            expected_absent=not exists, owner_id=owner,
        ))
    for item in selected_context:
        sources.append({key: item[key] for key in ("id", "revision", "purpose", "selected_content")})
        if item['kind'] == 'employment':
            from .work import _employment
            current = _employment(store, c, item['id'])
        else:
            current = store._get(c, item['id'], item['kind'])
        dependencies.append(cm.dependency(item['kind'], item['id'], item['revision'], current, item['purpose']))
    for item in evidence_context:
        sources.append({key: item[key] for key in ('id', 'revision', 'purpose', 'selected_content')})
        dependencies.append(cm.dependency(item['kind'], item['id'], item['revision'], None,
                                          'career_evidence', content_hash=item['hash']))
    return {"schemaVersion": 1, "task_type": "resume_optimization", "instruction": instruction,
            "required_context": ["opportunity", "current_resume_document"],
            "optional_context": ["company_research", "opportunity_research", "career_project", "career_employment", "career_wiki", "career_evidence"],
            "forbidden_context": ["other_opportunities", "other_resume_documents", "feedback", "full_raw_archive"],
            "target": {"opportunity_id": opportunity["id"], "resume_document_id": d["id"]},
            "sources": sources, "allowed_patch_targets": ["current_resume_document"],
            "confirmation_required": True, "output_schema_version": 2,
            "manifest": cm.manifest(
                "resume_optimization",
                {"kind": "resume_document", "id": d["id"], "opportunity_id": opportunity["id"]},
                d["revision"], dependencies,
            )}


def _resume_prepare(store, document_id, body):
    with store.connect(False) as c:
        document = get_document(store, c, document_id)
        selected = []
        evidence = []
        plan_id = body.get('retrieval_plan_id')
        evidence_plan_id = body.get('evidence_plan_id')
        if plan_id is not None and evidence_plan_id is not None:
            raise Invalid('一次只能继续一种检索计划')
        if evidence_plan_id is not None:
            if not isinstance(evidence_plan_id, str): raise Invalid('来源核验计划标识不合法')
            evidence_plan = store._get(c, evidence_plan_id, 'resume_evidence_plan', True)
            if evidence_plan.get('document_id') != document_id or evidence_plan.get('opportunity_id') != document['opportunity_id']:
                raise Invalid('来源核验计划不属于当前简历')
            if evidence_plan.get('status') != 'needs_evidence' or evidence_plan['expected_revision'] != document['revision']:
                raise Conflict('来源核验计划已处理或工作稿已变化')
            cm.validate(store, c, evidence_plan['manifest'])
            ids = body.get('selected_evidence_ids')
            available = {item['source_id']: item for item in evidence_plan['requests']}
            if not isinstance(ids, list) or not 1 <= len(ids) <= 2 or any(not isinstance(identifier, str) for identifier in ids) or len(set(ids)) != len(ids) or any(identifier not in available for identifier in ids):
                raise Invalid('只能选择本轮明确请求的来源')
            origin = store._get(c, evidence_plan['retrieval_plan_id'], 'resume_retrieval_plan', True)
            selected = read_selected_context(store, c, document['opportunity_id'], origin['candidates'],
                                             evidence_plan['selected_candidate_ids'],
                                             [item['query'] for item in origin['requests']])
            for identifier in ids:
                request = available[identifier]
                ref = request['source_ref']
                source = wiki_sources.resolve_source(store, c, ref['kind'], ref['id'])
                if wiki_sources.source_ref(source) != ref:
                    raise Conflict('Raw 来源已变化，请重新检索')
                if len(source['content']) > 3000:
                    raise Invalid('原文超过单条核验预算，请先在 Wiki 中整理具体摘录')
                evidence.append({
                    'kind': source['kind'], 'id': source['id'], 'revision': source['revision'],
                    'hash': source['hash'], 'purpose': 'career_evidence',
                    'selected_content': {'source_kind': source['source_kind'],
                                         'title': source['title'][:200], 'content': source['content']},
                })
        elif plan_id is not None:
            if not isinstance(plan_id, str): raise Invalid('检索计划标识不合法')
            plan = store._get(c, plan_id, 'resume_retrieval_plan', True)
            if plan.get('document_id') != document_id or plan.get('opportunity_id') != document['opportunity_id']:
                raise Invalid('检索计划不属于当前简历')
            if plan.get('status') != 'needs_retrieval':
                raise Conflict('此检索计划已处理，请重新发起')
            if plan.get('expected_revision') != document['revision']:
                raise Conflict('检索计划已过期：当前工作稿已变化')
            cm.validate(store, c, plan['manifest'])
            ids = body.get('selected_candidate_ids')
            if not isinstance(ids, list) or not ids:
                raise Invalid('请明确选中本轮相关 Career 候选')
            selected = read_selected_context(store, c, document['opportunity_id'], plan['candidates'], ids,
                                             [item['query'] for item in plan['requests']])
        elif 'selected_candidate_ids' in body or 'selected_evidence_ids' in body:
            raise Invalid('选中 Career 候选必须带有本轮检索计划')
        packet = _resume_ai_packet(store, c, document, body.get('instruction', ''), selected, evidence)
    return {"document": document, "packet": packet, "body": body,
            "request_fingerprint": digest(_resume_client_intent(document_id, body))}


def _resume_client_intent(document_id, body):
    return {
        "document_id": document_id,
        "instruction": body.get("instruction", ""),
        "idempotency_key": body.get("idempotency_key"),
        "model_config_id": body.get("model_config_id"),
        "retrieval_plan_id": body.get("retrieval_plan_id"),
        "selected_candidate_ids": body.get("selected_candidate_ids"),
        "evidence_plan_id": body.get("evidence_plan_id"),
        "selected_evidence_ids": body.get("selected_evidence_ids"),
    }


def _resume_output_schema():
    return {
        "version": 2,
        "type": "object",
        "additionalProperties": False,
        "required": ["changes", "suggestions", "claims"],
        "properties": {
            "changes": {
                "type": "array",
                "maxItems": _MAX_RESUME_CHANGES,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "change_id", "source_refs", "reason", "requires_fact_check",
                    ],
                    "properties": {
                        "change_id": {"type": "string", "minLength": 1, "maxLength": 160},
                        "operation": {"type": "string", "enum": ["rewrite", "add", "delete"]},
                        "section_type": {"type": "string", "enum": ["skills", "experience", "projects", "education"]},
                        "item_id": {"type": "string", "minLength": 1, "maxLength": 160},
                        "field": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 240,
                            "description": "只能是 content 或 bullets.<bullet_id>.content；只能引用当前简历已有条目。",
                        },
                        "before_hash": {
                            "type": "string",
                            "pattern": "^[0-9a-f]{64}$",
                        },
                        "proposed_text": {"type": "string", "maxLength": _MAX_CHANGE_TEXT},
                        "source_refs": {
                            "type": "array",
                            "maxItems": 20,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["id", "revision"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "revision": {"type": "integer"},
                                },
                            },
                            "description": "只能引用本次资料 manifest 中已有的来源。",
                        },
                        "reason": {"type": "string", "minLength": 1, "maxLength": 2000},
                        "requires_fact_check": {"type": "boolean"},
                    },
                },
            },
            "suggestions": {"type": "array", "items": {}},
            "claims": {"type": "array", "items": {}},
            "retrieval_requests": {
                "type": "array", "maxItems": 3,
                "description": "现有材料不足时先说明缺失证据及本地 Career 检索词；有检索请求时 changes 必须为空。",
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["need", "query"],
                    "properties": {
                        "need": {"type": "string", "minLength": 1, "maxLength": 300},
                        "query": {"type": "string", "minLength": 1, "maxLength": 200},
                    },
                },
            },
            "evidence_requests": {
                "type": "array", "maxItems": 2,
                "description": "仅在已选 Wiki 的来源指针不足以核对具体事实时请求对应 Raw；不得请求其它原文。",
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["source_kind", "source_id", "reason"],
                    "properties": {
                        "source_kind": {"type": "string", "enum": ["raw_material", "work_evidence"]},
                        "source_id": {"type": "string", "minLength": 1},
                        "reason": {"type": "string", "minLength": 1, "maxLength": 300},
                    },
                },
            },
        },
        "description": (
            "只允许 rewrite 已有技能/要点表述，或依据本轮 Career Wiki 来源 add 新技能/经历表达；"
            "delete 只能指向已有条目。不得返回整份 document 或修改身份字段。"
        ),
        "example": {
            "changes": [], "retrieval_requests": [], "evidence_requests": [],
            "suggestions": ["虚构示例：把技能表述改得更清楚。"],
            "claims": [],
        },
    }


_MAX_RESUME_CHANGES = 50
_MAX_CHANGE_TEXT = 20000
_FACT_MARKERS = re.compile(r"\d|%|％|年|月|日|万元|万|千|百|小时|天|人|次|倍|kg|GB|SLA", re.I)


def _resume_item(document, item_id):
    if document.get("profile", {}).get("id") == item_id:
        raise ao.AIValidationError("item_id 指向身份字段，AI 不得修改")
    for section in document.get("sections", []):
        for item in section.get("items", []):
            if item.get("id") == item_id:
                return section, item
    raise ao.AIValidationError("未知 item_id，不能跨文档或新增条目")


def _change_target(document, item_id, field):
    section, item = _resume_item(document, item_id)
    section_type = section.get("type")
    if section_type == "skills":
        if field != "content":
            raise ao.AIValidationError("field 不在技能表述字段白名单中")
        return item["content"]
    if not isinstance(field, str) or not field.startswith("bullets.") or not field.endswith(".content"):
        raise ao.AIValidationError("field 不在条目表述字段白名单中；身份、组织、职位、日期和结构不可改")
    bullet_id = field[len("bullets."):-len(".content")]
    if not bullet_id:
        raise ao.AIValidationError("field 缺少稳定 bullet_id")
    for bullet in item.get("bullets", []):
        if bullet.get("id") == bullet_id:
            return bullet["content"]
    raise ao.AIValidationError("field 指向未知 bullet，不能改变数组结构")


def _set_change_target(document, item_id, field, value):
    section, item = _resume_item(document, item_id)
    if section.get("type") == "skills":
        if field != "content":
            raise Conflict("AI 建议字段已过期或不在白名单中")
        item["content"] = value
        return
    bullet_id = field[len("bullets."):-len(".content")]
    for bullet in item.get("bullets", []):
        if bullet.get("id") == bullet_id:
            bullet["content"] = value
            return
    raise Conflict("AI 建议字段已过期或不在白名单中")


def _allowed_source_refs(packet):
    return {
        (str(source.get("id")), source.get("revision"))
        for source in packet.get("sources", [])
        if isinstance(source, dict) and source.get("id") is not None
    }


def _normalize_resume_change(document, packet, value):
    if not isinstance(value, dict):
        raise ao.AIValidationError("unsupported_proposal_format: change 必须是对象")
    allowed = {"change_id", "operation", "section_type", "item_id", "field", "before_hash", "proposed_text", "source_refs", "reason", "requires_fact_check"}
    if set(value) - allowed:
        raise ao.AIValidationError("unsupported_proposal_format: change 含有未支持字段")
    operation = value.get('operation', 'rewrite')
    if operation not in {'rewrite', 'add', 'delete'}:
        raise ao.AIValidationError('change.operation 不合法')
    required = {
        'add': ('change_id', 'proposed_text', 'reason'),
        'rewrite': ('change_id', 'item_id', 'field', 'before_hash', 'proposed_text', 'reason'),
        'delete': ('change_id', 'item_id', 'before_hash', 'reason'),
    }[operation]
    for key in required:
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ao.AIValidationError(f"change.{key} 必须是非空字符串")
    if len(value["change_id"]) > 160 or len(value.get("item_id", "")) > 160 or len(value.get("field", "")) > 240:
        raise ao.AIValidationError("change 标识或字段路径过长")
    if len(value["reason"]) > 2000 or len(value.get("proposed_text", "")) > _MAX_CHANGE_TEXT:
        raise ao.AIValidationError("AI 建议文本或理由过长")
    if operation != 'add' and not re.fullmatch(r"[0-9a-f]{64}", value["before_hash"]):
        raise ao.AIValidationError("before_hash 必须是当前字段的 sha256")
    if "requires_fact_check" in value and type(value["requires_fact_check"]) is not bool:
        raise ao.AIValidationError("requires_fact_check 必须是布尔值")
    source_refs = value.get("source_refs", [])
    if not isinstance(source_refs, list) or len(source_refs) > 20:
        raise ao.AIValidationError("source_refs 数量不合法")
    permitted = _allowed_source_refs(packet)
    normalized_refs = []
    for ref in source_refs:
        if not isinstance(ref, dict) or set(ref) != {"id", "revision"} or not isinstance(ref["id"], str) or type(ref["revision"]) is not int:
            raise ao.AIValidationError("source_refs 格式不合法")
        if (ref["id"], ref["revision"]) not in permitted:
            raise ao.AIValidationError("source_refs 不能引用本次 manifest 之外的资料")
        normalized_refs.append({"id": ref["id"], "revision": ref["revision"]})
    requires_fact_check = bool(value.get("requires_fact_check", False)) or bool(_FACT_MARKERS.search(value.get("proposed_text", "")))
    if operation == 'add':
        if set(value) - {'change_id', 'operation', 'section_type', 'proposed_text', 'source_refs', 'reason', 'requires_fact_check'}:
            raise ao.AIValidationError('add 不得指定已有条目或字段')
        if value.get('section_type') not in {'skills', 'experience', 'projects', 'education'}:
            raise ao.AIValidationError('add.section_type 不合法')
        career_ids = {source['id'] for source in packet['sources'] if source.get('purpose') == 'career_wiki'}
        if not normalized_refs or any(ref['id'] not in career_ids for ref in normalized_refs):
            raise ao.AIValidationError('add 必须引用本轮选中的 Career Wiki')
        return {
            'change_id': value['change_id'], 'operation': 'add',
            'section_type': value['section_type'], 'proposed_text': value['proposed_text'],
            'source_refs': normalized_refs, 'reason': value['reason'],
            'requires_fact_check': requires_fact_check,
        }
    if operation == 'delete':
        if set(value) - {'change_id', 'operation', 'item_id', 'before_hash', 'source_refs', 'reason', 'requires_fact_check'}:
            raise ao.AIValidationError('delete 只能指向已有完整条目')
        section, item = _resume_item(document, value['item_id'])
        if digest(item) != value['before_hash']:
            raise ao.AIValidationError('delete.before_hash 与当前条目不一致')
        return {
            'change_id': value['change_id'], 'operation': 'delete',
            'item_id': value['item_id'], 'section_type': section['type'],
            'before_hash': value['before_hash'], 'before_text': json.dumps(item, ensure_ascii=False),
            'source_refs': normalized_refs, 'reason': value['reason'],
            'requires_fact_check': False,
        }
    current = _change_target(document, value["item_id"], value["field"])
    if digest(current) != value["before_hash"]:
        raise ao.AIValidationError("AI 建议的 before_hash 与当前字段不一致")
    return {
        "change_id": value["change_id"], "operation": operation,
        "item_id": value["item_id"], "field": value["field"],
        "before_hash": value["before_hash"], "before_text": current,
        "proposed_text": value["proposed_text"], "source_refs": normalized_refs,
        "reason": value["reason"], "requires_fact_check": requires_fact_check,
    }


def _normalize_resume_result(document, packet, result):
    if not isinstance(result, dict) or "changes" not in result or "document" in result:
        raise ao.AIValidationError("unsupported_proposal_format: 简历 AI 只能返回 changes，不能返回整份 document")
    changes = result.get("changes")
    if not isinstance(changes, list) or len(changes) > _MAX_RESUME_CHANGES:
        raise ao.AIValidationError("unsupported_proposal_format: changes 数量不合法")
    normalized = []
    seen = set()
    for change in changes:
        item = _normalize_resume_change(document, packet, change)
        if item["change_id"] in seen:
            raise ao.AIValidationError("change_id 不能重复")
        seen.add(item["change_id"])
        normalized.append(item)
    suggestions = result.get("suggestions", [])
    claims = result.get("claims", [])
    if not isinstance(suggestions, list) or not isinstance(claims, list):
        raise ao.AIValidationError("suggestions 和 claims 必须是数组")
    return normalized, suggestions, claims


def _resume_prepare_record(store, document_id, body):
    prepared = _resume_prepare(store, document_id, body)
    payload, diagnostics, _, clean_packet, budget_info = ModelGateway(store).prepare_payload(
        "resume_optimization", prepared["packet"], _resume_output_schema(), body.get("model_config_id")
    )
    prepared.update(packet=clean_packet, payload=payload, diagnostics=diagnostics, budget=budget_info)
    return prepared


def _resume_create_preparation(store, document_id, body):
    prepared = _resume_prepare_record(store, document_id, body)
    return outbound.create_preparation(
        store, task_type="resume_optimization",
        target={"kind": "resume_document", "id": document_id},
        client_intent=_resume_client_intent(document_id, body),
        packet=prepared["packet"], payload=prepared["payload"],
        manifest=prepared["packet"].get("manifest"), diagnostics=prepared["diagnostics"],
        budget_info=prepared["budget"],
    )


def _resume_prepare_for_execution(store, document_id, body):
    prepared = _resume_prepare_record(store, document_id, body)
    outbound.validate_preparation(
        store, body["prepared_id"], task_type="resume_optimization",
        target={"kind": "resume_document", "id": document_id},
        client_intent=_resume_client_intent(document_id, body),
        payload_hash=body.get("payload_hash"), packet=prepared["packet"],
        payload=prepared["payload"], manifest=prepared["packet"].get("manifest"),
    )
    return prepared


def _resume_dispatch(store, prepared, binder):
    body, packet = prepared["body"], prepared["packet"]
    return ModelGateway(store).generate(
        'resume_optimization', packet, _resume_output_schema(),
        body.get('model_config_id'), before_call=lambda payload_hash: binder(payload_hash, packet['manifest']),
        operation_id=prepared.get("_operation_id"),
        target={"kind": "resume_document", "id": prepared["document"]["document_id"]},
    )


def _resume_persist(store, prepared, result, diagnostics):
    document, body, packet = prepared["document"], prepared["body"], prepared["packet"]
    evidence_requests = result.get('evidence_requests', []) if isinstance(result, dict) else []
    if not isinstance(evidence_requests, list) or len(evidence_requests) > 2:
        raise ao.AIValidationError('evidence_requests 数量不合法')
    if evidence_requests:
        if body.get('evidence_plan_id') or result.get('changes') or result.get('retrieval_requests'):
            raise ao.AIValidationError('来源核验请求不能与建议或另一检索同时出现')
        _normalize_resume_result(document['document'], packet, result)
        available = {
            (ref['kind'], ref['id']): ref
            for source in packet['sources'] if source['purpose'] == 'career_wiki'
            for ref in source['selected_content']['source_refs']
            if ref['kind'] in {'raw_material', 'work_evidence'}
        }
        requests = []
        seen = set()
        for request in evidence_requests:
            if not isinstance(request, dict) or set(request) != {'source_kind', 'source_id', 'reason'}:
                raise ao.AIValidationError('来源核验请求结构不合法')
            if not isinstance(request['source_kind'], str) or not isinstance(request['source_id'], str):
                raise ao.AIValidationError('来源核验标识不合法')
            key = (request['source_kind'], request['source_id'])
            reason = request['reason']
            if key in seen or key not in available or not isinstance(reason, str) or not reason.strip() or len(reason) > 300:
                raise ao.AIValidationError('只能核对本轮所选 Wiki 的明确来源')
            seen.add(key)
            requests.append({'source_kind': key[0], 'source_id': key[1],
                             'source_ref': available[key], 'reason': reason.strip()})
        plan = {
            'id': 'resume-evidence-plan:' + uid(), 'document_id': document['document_id'],
            'opportunity_id': document['opportunity_id'], 'expected_revision': document['revision'],
            'retrieval_plan_id': body['retrieval_plan_id'],
            'selected_candidate_ids': body['selected_candidate_ids'],
            'requests': requests, 'status': 'needs_evidence', 'created_at': now(),
            'manifest': packet['manifest'],
        }
        with store.connect() as c:
            store._record(c, 'resume_evidence_plan', plan)
            origin = store._get(c, body['retrieval_plan_id'], 'resume_retrieval_plan', True)
            origin['status'] = 'used'
            origin['used_at'] = now()
            store._record(c, 'resume_retrieval_plan', origin)
        return plan
    requests = result.get('retrieval_requests', []) if isinstance(result, dict) else []
    if not isinstance(requests, list) or len(requests) > 3:
        raise ao.AIValidationError('retrieval_requests 数量不合法')
    if requests:
        if result.get('changes'):
            raise ao.AIValidationError('检索请求不能同时包含待应用建议')
        normalized = []
        for request in requests:
            if not isinstance(request, dict) or set(request) != {'need', 'query'}:
                raise ao.AIValidationError('检索请求结构不合法')
            need, query = request['need'], request['query']
            if not isinstance(need, str) or not need.strip() or len(need) > 300:
                raise ao.AIValidationError('缺失证据说明不合法')
            if not isinstance(query, str) or not query.strip() or len(query) > 200:
                raise ao.AIValidationError('Career 检索词不合法')
            normalized.append({'need': need.strip(), 'query': query.strip()})
        _normalize_resume_result(document['document'], packet, result)
        candidates = []
        seen = set()
        with store.connect(False) as c:
            for request in normalized:
                for item in search_candidates(store, c, document['opportunity_id'], request['query'], limit=8):
                    if item['id'] not in seen and len(candidates) < 12:
                        candidates.append(item)
                        seen.add(item['id'])
        plan = {
            'id': 'resume-retrieval-plan:' + uid(), 'document_id': document['document_id'],
            'opportunity_id': document['opportunity_id'], 'expected_revision': document['revision'],
            'requests': normalized, 'candidates': candidates,
            'status': 'needs_retrieval', 'created_at': now(),
            'manifest': packet['manifest'],
        }
        with store.connect() as c:
            store._record(c, 'resume_retrieval_plan', plan)
        return plan
    changes, suggestions, claims = _normalize_resume_result(document["document"], packet, result)
    proposal = {'id': 'resume-ai-proposal:' + uid(), 'document_id': document['document_id'],
                'opportunity_id': document['opportunity_id'], 'expected_revision': document['revision'],
                'before_document': document['document'], 'changes': changes,
                'suggestions': suggestions, 'claims': claims, 'status': 'pending',
                'request_key': body['idempotency_key'], 'request_fingerprint': prepared['request_fingerprint'],
                'manifest': packet['manifest'],
                'context': {'policy_version': packet['output_schema_version'], 'source_ids': [x['id'] for x in packet['sources']]},
                'model': diagnostics, 'created_at': now()}
    if any('operation' in change for change in result.get('changes', [])):
        proposal['resolution_mode'] = 'per_change'
        for change in proposal['changes']:
            change['status'] = 'pending'
    with store.connect() as c:
        store._record(c, 'resume_ai_proposal', proposal)
        if body.get('retrieval_plan_id'):
            plan = store._get(c, body['retrieval_plan_id'], 'resume_retrieval_plan', True)
            plan['status'] = 'used'
            plan['used_at'] = now()
            store._record(c, 'resume_retrieval_plan', plan)
        if body.get('evidence_plan_id'):
            evidence_plan = store._get(c, body['evidence_plan_id'], 'resume_evidence_plan', True)
            evidence_plan['status'] = 'used'
            evidence_plan['used_at'] = now()
            store._record(c, 'resume_evidence_plan', evidence_plan)
    return proposal


def generate_ai_suggestion(store, document_id, body):
    strict(body, {'instruction', 'idempotency_key', 'model_config_id', 'prepared_id', 'payload_hash', 'confirm_outbound',
                  'retrieval_plan_id', 'selected_candidate_ids', 'evidence_plan_id', 'selected_evidence_ids'})
    instruction = body.get('instruction', '')
    if not isinstance(instruction, str) or len(instruction) > 10000: raise Invalid('AI 简历指令过长')
    key = body.get('idempotency_key')
    if not isinstance(key, str) or not key: raise Invalid('idempotency_key 不能为空')
    if not body.get('prepared_id') or body.get('confirm_outbound') is not True:
        return JSONResponse(_resume_create_preparation(store, document_id, body), status_code=409)
    request_fingerprint = digest(_resume_client_intent(document_id, body))
    with store.connect(False) as c:
        for previous in store._records(c, 'resume_ai_proposal'):
            if previous.get('request_key') == key:
                if previous.get('request_fingerprint') != request_fingerprint:
                    raise Conflict('请求标识已用于不同简历提案')
                if not ao.find(store, 'resume_optimization', 'resume_document', document_id, key):
                    return previous
    execution = ao.execute(
        store, task_type='resume_optimization', target_kind='resume_document', target_id=document_id,
        idempotency_key=key, client_intent={'document_id': document_id, 'body': body},
        prepare=lambda: _resume_prepare_for_execution(store, document_id, body),
        dispatch=lambda prepared, binder: _resume_dispatch(store, prepared, binder),
        persist=lambda prepared, result, diagnostics: _resume_persist(store, prepared, result, diagnostics),
    )
    return ao.unwrap(execution)


def resolve_ai_suggestion(store, document_id, proposal_id, body):
    strict(body, {'decision', 'changes'})
    if body.get('decision') not in {'accept', 'reject'}: raise Invalid('decision 只能是 accept 或 reject')
    with store.connect() as c:
        proposal = store._get(c, proposal_id, 'resume_ai_proposal', True)
        if proposal['document_id'] != document_id: raise Missing('AI 简历建议不存在')
        if proposal['status'] != 'pending': return proposal
        if proposal.get('resolution_mode') == 'per_change' and body['decision'] == 'accept':
            raise Conflict('此提案必须逐条处理，不能批量接受')
        if body['decision'] == 'reject':
            proposal.update(status='rejected', resolved_at=now())
            store._record(c, 'resume_ai_proposal', proposal)
            return {'proposal': proposal, 'document': get_document(store, c, document_id)}
        if not isinstance(proposal.get('changes'), list):
            raise Conflict('unsupported_proposal_format: 旧整稿建议不能直接应用，请拒绝后重新生成')
        current = get_document(store, c, document_id)
        cm.validate(store, c, proposal.get('manifest'))
        if current['revision'] != proposal.get('expected_revision'):
            raise Conflict('AI 建议已过期：工作稿 revision 已变化，请保留输入并重新生成')
        selected = body.get('changes')
        if selected is None:
            selected = [{"change_id": change["change_id"], "selected": True, "proposed_text": change["proposed_text"]}
                        for change in proposal.get("changes", [])]
        if not isinstance(selected, list) or len(selected) > len(proposal.get("changes", [])):
            raise Invalid('changes 选择列表不合法')
        by_id = {change["change_id"]: change for change in proposal.get("changes", [])}
        seen = set()
        selected_changes = []
        for choice in selected:
            if not isinstance(choice, dict) or set(choice) - {"change_id", "selected", "proposed_text"}:
                raise Invalid('changes 选择项不合法')
            change_id = choice.get("change_id")
            if not isinstance(change_id, str) or change_id in seen or change_id not in by_id:
                raise Invalid('changes 包含未知或重复 change_id')
            if type(choice.get("selected")) is not bool:
                raise Invalid('changes.selected 必须是布尔值')
            seen.add(change_id)
            change = by_id[change_id]
            text = choice.get("proposed_text", change["proposed_text"])
            if not isinstance(text, str) or len(text) > _MAX_CHANGE_TEXT:
                raise Invalid('用户编辑后的建议文本过长')
            if choice["selected"]:
                if digest(_change_target(current["document"], change["item_id"], change["field"])) != change["before_hash"]:
                    raise Conflict('AI 建议已过期：条目或字段内容已变化，请重新生成')
                selected_changes.append((change, text))
        updated = deepcopy(current["document"])
        old_refs = deepcopy(updated.get("meta", {}).get("source_refs", []))
        for change, text in selected_changes:
            _set_change_target(updated, change["item_id"], change["field"], text)
        validate_document(updated)
        if updated.get("meta", {}).get("source_refs", []) != old_refs:
            raise Conflict('AI 建议不能修改来源引用')
        saved = save_document(c, store, updated, current['revision'], document_id) if selected_changes else current
        proposal['applied_revision'] = saved['revision']
        proposal['applied_change_ids'] = [change["change_id"] for change, _ in selected_changes]
        proposal.update(status='accepted', resolved_at=now())
        store._record(c, 'resume_ai_proposal', proposal)
        return {'proposal': proposal, 'document': saved}


def resolve_ai_change(store, document_id, proposal_id, change_id, body):
    strict(body, {'decision', 'proposed_text'})
    decision = body.get('decision')
    if decision not in {'accept', 'reject'}: raise Invalid('decision 只能是 accept 或 reject')
    with store.connect() as c:
        proposal = store._get(c, proposal_id, 'resume_ai_proposal', True)
        if proposal.get('document_id') != document_id: raise Missing('AI 简历建议不存在')
        if proposal.get('resolution_mode') != 'per_change':
            raise Conflict('历史建议请使用原处理入口')
        change = next((item for item in proposal['changes'] if item['change_id'] == change_id), None)
        if change is None: raise Missing('AI 简历单条建议不存在')
        if change.get('status') != 'pending' or proposal['status'] != 'pending':
            return {'proposal': proposal, 'document': get_document(store, c, document_id)}
        current = get_document(store, c, document_id)
        if decision == 'accept':
            cm.validate(store, c, proposal['manifest'])
            if current['revision'] != proposal['expected_revision']:
                raise Conflict('AI 建议已过期：工作稿已变化')
            text = body.get('proposed_text', change.get('proposed_text'))
            if change['operation'] != 'delete' and (not isinstance(text, str) or not text.strip() or len(text) > _MAX_CHANGE_TEXT):
                raise Invalid('用户编辑后的建议文本不合法')
            if change['operation'] == 'delete' and 'proposed_text' in body:
                raise Invalid('删除建议不能提交新文本')
            updated = deepcopy(current['document'])
            applied_item_id = change.get('item_id')
            if change['operation'] == 'add':
                section_type = change['section_type']
                section = next((item for item in updated['sections'] if item['type'] == section_type), None)
                if section is None:
                    section = {'id': 'section-' + section_type, 'type': section_type,
                               'title': {'skills': '专业技能', 'experience': '工作经历',
                                         'projects': '项目经历', 'education': '教育背景'}[section_type], 'items': []}
                    updated['sections'].append(section)
                item_id = uid()
                applied_item_id = item_id
                expression = html.escape(text).replace('\n', '<br>')
                if section_type == 'skills':
                    item = {'id': item_id, 'content': expression}
                else:
                    fields = {
                        'experience': {'organization': '', 'role': '', 'date': ''},
                        'projects': {'title': '', 'responsibility': '', 'date': ''},
                        'education': {'school': '', 'major': '', 'date': ''},
                    }[section_type]
                    item = {'id': item_id, **fields, 'bullets': [{'id': uid(), 'content': expression}]}
                section['items'].append(item)
                refs = updated['meta'].setdefault('source_refs', [])
                for ref in change['source_refs']:
                    source = store._get(c, ref['id'], 'wiki_knowledge')
                    if source['revision'] != ref['revision'] or source['status'] != 'current':
                        raise Conflict('Career Wiki 来源已变化，请重新生成建议')
                    refs.append({
                        'item_id': item_id, 'source_kind': 'wiki_knowledge',
                        'source_id': source['id'], 'revision': source['revision'],
                        'hash': digest(source), 'title': source['content'][:100],
                        'scope_type': source['scope_type'], 'scope_id': source['scope_id'],
                    })
            elif change['operation'] == 'rewrite':
                if digest(_change_target(updated, change['item_id'], change['field'])) != change['before_hash']:
                    raise Conflict('AI 建议的原文已变化，请重新生成')
                _set_change_target(updated, change['item_id'], change['field'], text)
            elif change['operation'] == 'delete':
                section, item = _resume_item(updated, change['item_id'])
                if digest(item) != change['before_hash']:
                    raise Conflict('待删除条目已变化，请重新生成')
                section['items'] = [candidate for candidate in section['items'] if candidate['id'] != item['id']]
            else:
                raise Conflict('AI 建议类型不合法')
            saved = save_document(c, store, validate_document(updated), current['revision'], document_id)
            proposal['expected_revision'] = saved['revision']
            manifest = proposal['manifest']
            manifest['target_revision'] = saved['revision']
            for dependency in manifest['dependencies']:
                if dependency['kind'] == 'resume_document' and dependency['id'] == document_id:
                    dependency.update(revision=saved['revision'], content_hash=digest(saved['document']))
            change['status'] = 'accepted'
            change['applied_item_id'] = applied_item_id
            if text is not None: change['accepted_text'] = text
        else:
            saved = current
            change['status'] = 'rejected'
        if all(item.get('status') != 'pending' for item in proposal['changes']):
            proposal['status'] = 'accepted' if any(item['status'] == 'accepted' for item in proposal['changes']) else 'rejected'
            proposal['resolved_at'] = now()
        store._record(c, 'resume_ai_proposal', proposal)
        return {'proposal': proposal, 'document': saved}


def router(store):
    router=APIRouter()
    @router.get('/api/resume-documents')
    def catalogue():
        with store.connect(False) as c:
            items=[]
            for d in store._current(c,'resume_document'):
                o=op.resolve(store,c,d['opportunity_id'])
                items.append(dict(document_id=d['id'],opportunity_id=o['id'],company=o['company'],title=o['title'],saved_at=d['savedAt']))
            return dict(documents=sorted(items,key=lambda x:x['saved_at'],reverse=True))
    @router.get('/api/opportunities/{oid}/resume')
    def current(oid:str):
        with store.connect(False) as c:
            o=op.resolve(store,c,oid);did=for_opportunity(c,o['id'])
            return get_document(store,c,did) if did else dict(document=None,opportunity_id=o['id'],read_only=o['read_only'])
    @router.post('/api/opportunities/{oid}/resume/start')
    def start(oid:str,body:dict):
        strict(body,{'expected_opportunity_revision','idempotency_key','source'})
        with store.connect() as c:
            o=op.writable(store,c,oid)
            replay,key,fp=op.request(store,c,'start_resume',o['id'],body)
            if replay is not None:return replay
            if revision(body.get('expected_opportunity_revision'))!=o['revision']:raise Conflict('机会已更新')
            doc,source=copy_source(store,c,body.get('source'))
            result=create_document(store,c,o['id'],doc,source)
            return op.remember(store,c,key,fp,result)
    @router.get('/api/resume-documents/{document_id}')
    def get(document_id:str):
        with store.connect(False) as c:return get_document(store,c,document_id)
    @router.put('/api/resume-documents/{document_id}')
    def put(document_id:str,body:dict):
        strict(body,{'document','expected_revision'})
        doc=validate_document(body.get('document'))
        with store.connect() as c:
            old=get_document(store,c,document_id)
            if doc['meta'].get('source_refs',[])!=old['document']['meta'].get('source_refs',[]):raise Conflict('来源不可手动改写')
            return save_document(c,store,doc,body.get('expected_revision'),document_id)
    @router.get('/api/resume-documents/{document_id}/materials')
    def materials(document_id:str):
        with store.connect(False) as c:
            d=get_document(store,c,document_id);j=op.job_view(store,c,d['opportunity_id'])
            return dict(profile=store._get(c,'profile','profile'),entries=[e for e in store._current(c,'wiki_entry') if fact_allowed(e,j['id'])])
    @router.get('/api/resume-documents/{document_id}/sources')
    def sources(document_id:str):
        with store.connect(False) as c:
            d=get_document(store,c,document_id);ids=item_ids(d['document']);result=[]
            for ref in d['document']['meta'].get('source_refs',[]):
                row=c.execute('SELECT body FROM current WHERE id=? AND kind=?',(ref['source_id'],ref['source_kind'])).fetchone()
                value=json.loads(row[0]) if row else None
                status='removed' if ref['item_id'] not in ids else 'withdrawn' if not value or value.get('status')=='withdrawn' else 'revoked' if value.get('reuse_status')=='revoked' else 'updated' if value['revision']!=ref['revision'] else 'current'
                result.append(dict(ref,status=status))
            return dict(sources=result,copied_sources=d['provenance'].get('source_refs',[]))
    @router.post('/api/resume-documents/{document_id}/select-facts')
    def select_facts(document_id: str, body: dict):
        strict(body,{'expected_revision','selections','include_profile','profile_revision','idempotency_key'})
        from .knowledge import expected as validate_expected, remember, request
        expected = validate_expected(body.get('expected_revision'))
        selections = body.get('selections', [])
        include_profile = body.get('include_profile', False)
        if type(include_profile) is not bool: raise Invalid('基础信息选择不合法')
        if not isinstance(selections, list) or len(selections) > 30 or (not selections and not include_profile):
            raise Invalid('请明确选择不超过30条已确认资料')
        with store.connect() as c:
            previous, key, fingerprint = request(store, c, body.get('idempotency_key'), 'resume_select_facts:'+document_id, body)
            if previous is not None: return previous
            target = get_document(store,c,document_id)
            job_id = op.job_view(store,c,target['opportunity_id'])['id']
            document, revision = target['document'], target['revision']
            if revision != expected: raise Conflict('工作稿已更新，请保存并重新选择材料')
            document = deepcopy(document)
            refs = document['meta'].setdefault('source_refs', [])
            present = item_ids(document)
            imported = {ref['source_id'] for ref in refs if ref['item_id'] in present}
            for selection in selections:
                if not isinstance(selection, dict) or not isinstance(selection.get('id'), str): raise Invalid('选材不合法')
                e = store._get(c, selection['id'], 'wiki_entry')
                if not fact_allowed(e, job_id): raise Invalid('只能选择个人或当前机会的有效Wiki；任职资料须先确认允许复用的个人事实')
                if type(selection.get('revision')) is not int or selection['revision'] != e['revision']: raise Conflict('所选事实已更新，请重新检查材料')
                if e['id'] in imported: raise Conflict('此事实已选入当前稿，请编辑已有表达或移除条目后重选')
                kind = selection.get('section_type')
                if kind not in {'skills','experience','projects','education'}: raise Invalid('简历分区不合法')
                section = next((x for x in document['sections'] if x['type'] == kind), None)
                if section is None:
                    section = dict(id='section-'+kind, type=kind, title={'skills':'专业技能','experience':'工作经历','projects':'项目经历','education':'教育背景'}[kind], items=[])
                    document['sections'].append(section)
                item_id = uid()
                title = html.escape(e['title']); content = html.escape(e['content']).replace('\n','<br>')
                if kind == 'skills': item = dict(id=item_id, content=title+'：'+content)
                else:
                    fields = {'experience':dict(organization='', role=title, date=''), 'projects':dict(title=title, responsibility='', date=''), 'education':dict(school=title, major='', date='')}[kind]
                    item = dict(id=item_id, bullets=[dict(id=uid(), content=content)], **fields)
                section['items'].append(item)
                ref = dict(item_id=item_id, source_kind='wiki_entry', source_id=e['id'], revision=e['revision'], hash=digest(e), title=e['title'], scope_type=e['scope_type'], scope_id=e['scope_id'])
                provenance = e.get('reuse_provenance')
                if isinstance(provenance, dict) and provenance.get('kind') == 'work_achievement_reuse':
                    ref['evidence_refs'] = deepcopy(provenance.get('evidence_refs', []))
                refs.append(ref)
                imported.add(e['id'])
            if include_profile:
                p = store._get(c, 'profile', 'profile')
                if p.get('mode') != 'structured': raise Invalid('请先在基础资料中明确整理姓名和联系方式')
                if type(body.get('profile_revision')) is not int or body['profile_revision'] != p['revision']: raise Conflict('基础资料已更新，请重新检查')
                # Explicit reselection refreshes the identity expression; old draft revisions and versions retain old refs.
                document = apply_profile(document, p)
            result = save_document(c, store, validate_document(document), expected, document_id)
            remember(store, c, key, fingerprint, result)
            return result

    @router.get('/api/resume-documents/{document_id}/versions')
    def versions(document_id:str):
        with store.connect(False) as c:
            get_document(store,c,document_id)
            return dict(versions=[version_summary(v) for v in store._records(c,'editor_version') if v.get('document_id')==document_id])
    def current_pdf(document_id, expected):
        with store.connect(False) as c:
            document = get_document(store, c, document_id)
            if document['revision'] != expected:
                raise Conflict('工作稿已变化，请先保存并重新导出')
            snapshot = deepcopy(document['document'])
        rendered = render_pdf(snapshot)
        with store.connect(False) as c:
            latest = get_document(store, c, document_id)
            if latest['revision'] != expected or digest(latest['document']) != rendered.document_hash:
                raise Conflict('导出期间工作稿已变化，请重新保存并导出')
        return Response(
            content=rendered.data,
            media_type='application/pdf',
            headers={
                'Content-Disposition': 'attachment; filename="resume.pdf"',
                'X-Resume-Document-Hash': rendered.document_hash,
                'X-Resume-Renderer-Version': rendered.renderer_version,
            },
        )
    @router.post('/api/resume-documents/{document_id}/pdf')
    def export_pdf(document_id:str, body:dict):
        strict(body, {'expected_revision'})
        return current_pdf(document_id, revision(body.get('expected_revision')))
    @router.post('/api/resume-documents/{document_id}/ai-suggest')
    def ai_suggest(document_id: str, body: dict):
        return generate_ai_suggestion(store, document_id, body)
    @router.get('/api/resume-documents/{document_id}/ai-proposals')
    def ai_proposals(document_id: str):
        with store.connect(False) as c:
            get_document(store, c, document_id)
            result = []
            for proposal in store._records(c, 'resume_ai_proposal'):
                if proposal.get('document_id') != document_id:
                    continue
                proposal = dict(proposal)
                if proposal.get('status') == 'pending':
                    try:
                        cm.validate(store, c, proposal.get('manifest'))
                    except Conflict as exc:
                        proposal.update(stale=True, stale_reason=str(exc))
                result.append(proposal)
            return result
    @router.get('/api/resume-documents/{document_id}/ai-retrieval-plans')
    def ai_retrieval_plans(document_id: str):
        with store.connect(False) as c:
            get_document(store, c, document_id)
            plans = []
            for plan in store._records(c, 'resume_retrieval_plan'):
                if plan.get('document_id') != document_id or plan.get('status') != 'needs_retrieval':
                    continue
                item = dict(plan)
                try:
                    cm.validate(store, c, plan.get('manifest'))
                except Conflict as exc:
                    item.update(stale=True, stale_reason=str(exc))
                plans.append(item)
            return plans
    @router.get('/api/resume-documents/{document_id}/ai-retrieval-plans/{plan_id}/labels')
    def ai_retrieval_labels(document_id: str, plan_id: str):
        with store.connect(False) as c:
            document = get_document(store, c, document_id)
            plan = store._get(c, plan_id, 'resume_retrieval_plan', True)
            if plan.get('document_id') != document_id or plan.get('opportunity_id') != document['opportunity_id']:
                raise Missing('检索计划不存在')
            labels = {}
            for candidate in plan.get('candidates', []):
                kind, identifier = candidate['kind'], candidate['id']
                if kind == 'wiki_knowledge':
                    item = store._get(c, identifier, kind)
                    if item['revision'] == candidate['revision'] and item.get('status') == 'current':
                        labels[identifier] = item['content'][:100]
                elif kind == 'work_project':
                    item = store._get(c, identifier, kind)
                    if item['revision'] == candidate['revision']:
                        labels[identifier] = item['name'][:100]
                elif kind == 'employment':
                    from .work import _employment
                    item = _employment(store, c, identifier)
                    if item['revision'] == candidate['revision']:
                        labels[identifier] = (item['company'] + ' · ' + item['role'])[:100]
            return {'labels': labels}
    @router.get('/api/resume-documents/{document_id}/ai-evidence-plans')
    def ai_evidence_plans(document_id: str):
        with store.connect(False) as c:
            get_document(store, c, document_id)
            plans = []
            for plan in store._records(c, 'resume_evidence_plan'):
                if plan.get('document_id') != document_id or plan.get('status') != 'needs_evidence':
                    continue
                item = dict(plan)
                try:
                    cm.validate(store, c, plan.get('manifest'))
                except Conflict as exc:
                    item.update(stale=True, stale_reason=str(exc))
                plans.append(item)
            return plans
    @router.get('/api/resume-documents/{document_id}/ai-evidence-plans/{plan_id}/labels')
    def ai_evidence_labels(document_id: str, plan_id: str):
        with store.connect(False) as c:
            document = get_document(store, c, document_id)
            plan = store._get(c, plan_id, 'resume_evidence_plan', True)
            if plan.get('document_id') != document_id or plan.get('opportunity_id') != document['opportunity_id']:
                raise Missing('来源核验计划不存在')
            labels = {}
            for request in plan['requests']:
                source = wiki_sources.resolve_source(store, c, request['source_kind'], request['source_id'])
                if wiki_sources.source_ref(source) == request['source_ref']:
                    labels[source['id']] = source['title'][:100]
            return {'labels': labels}
    @router.post('/api/resume-documents/{document_id}/ai-proposals/{proposal_id}/resolve')
    def ai_resolve(document_id: str, proposal_id: str, body: dict):
        return resolve_ai_suggestion(store, document_id, proposal_id, body)
    @router.post('/api/resume-documents/{document_id}/ai-proposals/{proposal_id}/changes/{change_id}/resolve')
    def ai_resolve_change(document_id: str, proposal_id: str, change_id: str, body: dict):
        return resolve_ai_change(store, document_id, proposal_id, change_id, body)
    @router.post('/api/resume-documents/{document_id}/versions')
    def save_version(document_id:str,body:dict):
        strict(body,{'name','expected_revision','idempotency_key'})
        name=body.get('name')
        if not isinstance(name,str) or not name.strip() or len(name)>200:raise Invalid('请输入版本名称')
        expected = revision(body.get('expected_revision'))
        with store.connect(False) as c:
            old=get_document(store,c,document_id)
            replay,key,fp=op.request(store,c,'save_resume_version',document_id,body)
            if replay is not None:return replay
            if expected != old['revision']:
                raise Conflict('稿已变化，请先保存并核对')
            snapshot=deepcopy(old['document'])
        rendered=render_pdf(snapshot)
        with material_transaction(store) as c:
            old=get_document(store,c,document_id)
            replay,key,fp=op.request(store,c,'save_resume_version',document_id,body)
            if replay is not None:return replay
            if expected!=old['revision'] or digest(old['document'])!=rendered.document_hash:raise Conflict('稿已变化，请先保存并核对')
            v,_=insert_version(store,c,old,old['document'],rendered.data,'ordinary',name.strip(),body['idempotency_key'],rendered=rendered)
            return op.remember(store,c,key,fp,v)
    @router.get('/api/resume-documents/{document_id}/versions/{vid}')
    def read_version(document_id:str,vid:str):
        with store.connect(False) as c:return owns_version(store,c,document_id,vid)
    @router.post('/api/resume-documents/{document_id}/restore')
    def restore(document_id:str,body:dict):
        strict(body,{'version_id','expected_revision','idempotency_key'})
        with store.connect() as c:
            replay,key,fp=op.request(store,c,'restore_resume',document_id,body)
            if replay is not None:return replay
            old=get_document(store,c,document_id);v=owns_version(store,c,document_id,body.get('version_id'))
            result=save_document(c,store,deepcopy(v['document']),body.get('expected_revision'),document_id)
            store._record(c,'editor_recovery',dict(id=uid(),document_id=document_id,version_id=v['id'],before=old['document'],document=result['document'],createdAt=now(),revision=result['revision'],previous_revision=old['revision']))
            return op.remember(store,c,key,fp,result)
    @router.delete('/api/resume-documents/{document_id}/versions/{vid}')
    def delete(document_id:str,vid:str):
        with material_transaction(store) as c:
            v=owns_version(store,c,document_id,vid)
            if v['version_kind']=='submission':raise Conflict('投递版本永久保留，不可删除')
            aid=v['artifact_id'];a=store._get(c,aid,'artifact',True)
            refs=[]
            for r in store._records(c,'editor_version')+store._records(c,'version')+store._records(c,'resume_use'):
                if r['id']!=vid and (r.get('version_id')==vid or r.get('artifact_id')==aid):refs.append(r['id'])
            if c.execute('SELECT 1 FROM applications WHERE version_id=? OR artifact_id=?',(vid,aid)).fetchone():refs.append('submission')
            for other in store._records(c,'artifact'):
                if other['id']!=aid and other['path']==a['path']:refs.append(other['id'])
            if refs:raise Conflict('版本或PDF已被引用，不能删除')
            # Retire DB records first. Crash leaves a recognizable orphan, never a missing referenced PDF.
            c.execute('DELETE FROM records WHERE id IN (?,?)',(vid,aid))
            files.fault('after_delete')
        with store.connect() as c:files.recover(c,store.data_dir)
        return dict(deleted=vid)
    return router
