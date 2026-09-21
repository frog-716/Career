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
        strict(source,{'kind'});return blank_document(),dict(kind='blank')
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


def _resume_ai_packet(store, c, d, instruction):
    opportunity = op.resolve(store, c, d['opportunity_id'])
    sources = [
        {"id": opportunity["id"], "revision": opportunity["revision"], "purpose": "opportunity", "selected_content": {
            "company": opportunity["company"], "title": opportunity["title"], "jd": opportunity.get("jd", ""),
        }},
        {"id": d["id"], "revision": d["revision"], "purpose": "current_resume_document", "selected_content": d["document"]},
    ]
    company, company_exists = rs.lookup(store, c, "company_research", opportunity["company_id"])
    research, research_exists = rs.lookup(store, c, "opportunity_research", opportunity["id"])
    if company["items"]: sources.append({"id": company["id"], "revision": company["revision"], "purpose": "company_research", "selected_content": company["items"]})
    if research["items"]: sources.append({"id": research["id"], "revision": research["revision"], "purpose": "opportunity_research", "selected_content": research["items"]})
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
    return {"schemaVersion": 1, "task_type": "resume_optimization", "instruction": instruction,
            "required_context": ["opportunity", "current_resume_document"],
            "optional_context": ["company_research", "opportunity_research"],
            "forbidden_context": ["other_opportunities", "other_resume_documents", "feedback", "full_raw_archive"],
            "target": {"opportunity_id": opportunity["id"], "resume_document_id": d["id"]},
            "sources": sources, "allowed_patch_targets": ["current_resume_document"],
            "confirmation_required": True, "output_schema_version": 1,
            "manifest": cm.manifest(
                "resume_optimization",
                {"kind": "resume_document", "id": d["id"], "opportunity_id": opportunity["id"]},
                d["revision"], dependencies,
            )}


def _resume_prepare(store, document_id, body):
    with store.connect(False) as c:
        document = get_document(store, c, document_id)
        packet = _resume_ai_packet(store, c, document, body.get('instruction', ''))
    return {"document": document, "packet": packet, "body": body,
            "request_fingerprint": digest(_resume_client_intent(document_id, body))}


def _resume_client_intent(document_id, body):
    return {
        "document_id": document_id,
        "instruction": body.get("instruction", ""),
        "idempotency_key": body.get("idempotency_key"),
        "model_config_id": body.get("model_config_id"),
    }


def _resume_output_schema():
    return {"version": 2, "required": ["changes"]}


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
    allowed = {"change_id", "item_id", "field", "before_hash", "proposed_text", "source_refs", "reason", "requires_fact_check"}
    if set(value) - allowed:
        raise ao.AIValidationError("unsupported_proposal_format: change 含有未支持字段")
    for key in ("change_id", "item_id", "field", "before_hash", "proposed_text", "reason"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ao.AIValidationError(f"change.{key} 必须是非空字符串")
    if len(value["change_id"]) > 160 or len(value["item_id"]) > 160 or len(value["field"]) > 240:
        raise ao.AIValidationError("change 标识或字段路径过长")
    if len(value["reason"]) > 2000 or len(value["proposed_text"]) > _MAX_CHANGE_TEXT:
        raise ao.AIValidationError("AI 建议文本或理由过长")
    if not re.fullmatch(r"[0-9a-f]{64}", value["before_hash"]):
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
    current = _change_target(document, value["item_id"], value["field"])
    if digest(current) != value["before_hash"]:
        raise ao.AIValidationError("AI 建议的 before_hash 与当前字段不一致")
    requires_fact_check = bool(value.get("requires_fact_check", False)) or bool(_FACT_MARKERS.search(value["proposed_text"]))
    return {
        "change_id": value["change_id"], "item_id": value["item_id"], "field": value["field"],
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
    changes, suggestions, claims = _normalize_resume_result(document["document"], packet, result)
    proposal = {'id': 'resume-ai-proposal:' + uid(), 'document_id': document['document_id'],
                'opportunity_id': document['opportunity_id'], 'expected_revision': document['revision'],
                'before_document': document['document'], 'changes': changes,
                'suggestions': suggestions, 'claims': claims, 'status': 'pending',
                'request_key': body['idempotency_key'], 'request_fingerprint': prepared['request_fingerprint'],
                'manifest': packet['manifest'],
                'context': {'policy_version': packet['output_schema_version'], 'source_ids': [x['id'] for x in packet['sources']]},
                'model': diagnostics, 'created_at': now()}
    with store.connect() as c:
        store._record(c, 'resume_ai_proposal', proposal)
    return proposal


def generate_ai_suggestion(store, document_id, body):
    strict(body, {'instruction', 'idempotency_key', 'model_config_id', 'prepared_id', 'payload_hash', 'confirm_outbound'})
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
                status='removed' if ref['item_id'] not in ids else 'withdrawn' if not value or value.get('status')=='withdrawn' else 'updated' if value['revision']!=ref['revision'] else 'current'
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
                refs.append(dict(item_id=item_id, source_kind='wiki_entry', source_id=e['id'], revision=e['revision'], hash=digest(e), title=e['title'], scope_type=e['scope_type'], scope_id=e['scope_id']))
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
    @router.post('/api/resume-documents/{document_id}/pdf')
    def export_pdf(document_id:str, body:dict):
        strict(body, {'expected_revision'})
        expected = revision(body.get('expected_revision'))
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
    @router.post('/api/resume-documents/{document_id}/ai-proposals/{proposal_id}/resolve')
    def ai_resolve(document_id: str, proposal_id: str, body: dict):
        return resolve_ai_suggestion(store, document_id, proposal_id, body)
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
