"""Opportunity-owned current resumes; immutable versions reuse the paper editor."""
from contextlib import contextmanager
from copy import deepcopy
import json
import html
from fastapi import APIRouter

from .core import Conflict, Invalid, Missing, digest, dump, now, uid
from .editor import _blank, _document, _pdf, _apply_profile, _fact_allowed, _item_ids
from . import opportunity as op
from . import resume_artifacts as files
from .model_gateway import ModelGateway


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
    obj.update(document=_document(document),savedAt=now())
    c.execute('UPDATE current SET revision=?,body=? WHERE id=? AND revision=?',(expected+1,dump(obj),did,expected))
    return dict(obj,document_id=did,revision=expected+1)


def copy_source(store,c,source):
    if not isinstance(source,dict):raise Invalid('请明确选择简历来源')
    kind=source.get('kind')
    if kind=='blank':
        strict(source,{'kind'});return _blank(),dict(kind='blank')
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
    doc=deepcopy(_document(doc))
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
    return {k:v.get(k) for k in ('id','name','createdAt','artifact_id','document_id','opportunity_id','version_kind','submission_id','document_hash')}


def insert_version(store,c,d,doc,raw,kind,name,key,submission_id=None,source_version_id=None):
    aid,vid,stamp=uid(),uid(),now()
    artifact=files.stage_pdf(store.data_dir,aid,vid,raw,stamp)
    v=dict(id=vid,name=name,createdAt=stamp,document=deepcopy(doc),document_hash=digest(doc),
           document_id=d['id'],opportunity_id=d['opportunity_id'],artifact_id=aid,
           version_kind=kind,idempotency_key=key)
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
    from .research import _get
    company = _get(store, c, "company_research", opportunity["company_id"])
    research = _get(store, c, "opportunity_research", opportunity["id"])
    if company["items"]: sources.append({"id": company["id"], "revision": company["revision"], "purpose": "company_research", "selected_content": company["items"]})
    if research["items"]: sources.append({"id": research["id"], "revision": research["revision"], "purpose": "opportunity_research", "selected_content": research["items"]})
    return {"schemaVersion": 1, "task_type": "resume_optimization", "instruction": instruction,
            "required_context": ["opportunity", "current_resume_document"],
            "optional_context": ["company_research", "opportunity_research"],
            "forbidden_context": ["other_opportunities", "other_resume_documents", "feedback", "full_raw_archive"],
            "target": {"opportunity_id": opportunity["id"], "resume_document_id": d["id"]},
            "sources": sources, "allowed_patch_targets": ["current_resume_document"],
            "confirmation_required": True, "output_schema_version": 1}


def generate_ai_suggestion(store, document_id, body):
    strict(body, {'instruction', 'idempotency_key', 'model_config_id'})
    instruction = body.get('instruction', '')
    if not isinstance(instruction, str) or len(instruction) > 10000: raise Invalid('AI 简历指令过长')
    key = body.get('idempotency_key')
    if not isinstance(key, str) or not key: raise Invalid('idempotency_key 不能为空')
    with store.connect(False) as c:
        d = get_document(store, c, document_id)
        packet = _resume_ai_packet(store, c, d, instruction)
    result, diagnostics = ModelGateway(store).generate('resume_optimization', packet, {'version': 1, 'required': ['document', 'suggestions']}, body.get('model_config_id'))
    proposed = _document(result.get('document'))
    proposed['meta']['source_refs'] = d['document'].get('meta', {}).get('source_refs', [])
    proposal = {'id': 'resume-ai-proposal:' + uid(), 'document_id': document_id, 'opportunity_id': d['opportunity_id'],
                'expected_revision': d['revision'], 'before_document': d['document'], 'proposed_document': proposed,
                'suggestions': result.get('suggestions', []), 'claims': result.get('claims', []), 'status': 'pending',
                'request_key': key, 'context': {'policy_version': packet['output_schema_version'], 'source_ids': [x['id'] for x in packet['sources']]},
                'model': diagnostics, 'created_at': now()}
    with store.connect() as c:
        store._record(c, 'resume_ai_proposal', proposal)
    return proposal


def resolve_ai_suggestion(store, document_id, proposal_id, body):
    strict(body, {'decision'})
    if body.get('decision') not in {'accept', 'reject'}: raise Invalid('decision 只能是 accept 或 reject')
    with store.connect() as c:
        proposal = store._get(c, proposal_id, 'resume_ai_proposal', True)
        if proposal['document_id'] != document_id: raise Missing('AI 简历建议不存在')
        if proposal['status'] != 'pending': return proposal
        current = get_document(store, c, document_id)
        if current['revision'] != proposal['expected_revision']: raise Conflict('当前简历已变化，请重新生成建议')
        if body['decision'] == 'accept':
            saved = save_document(c, store, proposal['proposed_document'], current['revision'], document_id)
            proposal['applied_revision'] = saved['revision']
        proposal.update(status='accepted' if body['decision'] == 'accept' else 'rejected', resolved_at=now())
        store._record(c, 'resume_ai_proposal', proposal)
        return {'proposal': proposal, 'document': saved if body['decision'] == 'accept' else current}


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
        doc=_document(body.get('document'))
        with store.connect() as c:
            old=get_document(store,c,document_id)
            if doc['meta'].get('source_refs',[])!=old['document']['meta'].get('source_refs',[]):raise Conflict('来源不可手动改写')
            return save_document(c,store,doc,body.get('expected_revision'),document_id)
    @router.get('/api/resume-documents/{document_id}/materials')
    def materials(document_id:str):
        with store.connect(False) as c:
            d=get_document(store,c,document_id);j=op.job_view(store,c,d['opportunity_id'])
            return dict(profile=store._get(c,'profile','profile'),entries=[e for e in store._current(c,'wiki_entry') if _fact_allowed(e,j['id'])])
    @router.get('/api/resume-documents/{document_id}/sources')
    def sources(document_id:str):
        with store.connect(False) as c:
            d=get_document(store,c,document_id);ids=_item_ids(d['document']);result=[]
            for ref in d['document']['meta'].get('source_refs',[]):
                row=c.execute('SELECT body FROM current WHERE id=? AND kind=?',(ref['source_id'],ref['source_kind'])).fetchone()
                value=json.loads(row[0]) if row else None
                status='removed' if ref['item_id'] not in ids else 'withdrawn' if not value or value.get('status')=='withdrawn' else 'updated' if value['revision']!=ref['revision'] else 'current'
                result.append(dict(ref,status=status))
            return dict(sources=result,copied_sources=d['provenance'].get('source_refs',[]))
    @router.post('/api/resume-documents/{document_id}/select-facts')
    def select_facts(document_id: str, body: dict):
        strict(body,{'expected_revision','selections','include_profile','profile_revision','idempotency_key'})
        from .knowledge import _request, _remember, _expected
        expected = _expected(body.get('expected_revision'))
        selections = body.get('selections', [])
        include_profile = body.get('include_profile', False)
        if type(include_profile) is not bool: raise Invalid('基础信息选择不合法')
        if not isinstance(selections, list) or len(selections) > 30 or (not selections and not include_profile):
            raise Invalid('请明确选择不超过30条已确认资料')
        with store.connect() as c:
            previous, key, fingerprint = _request(store, c, body.get('idempotency_key'), 'resume_select_facts:'+document_id, body)
            if previous is not None: return previous
            target = get_document(store,c,document_id)
            job_id = op.job_view(store,c,target['opportunity_id'])['id']
            document, revision = target['document'], target['revision']
            if revision != expected: raise Conflict('工作稿已更新，请保存并重新选择材料')
            document = deepcopy(document)
            refs = document['meta'].setdefault('source_refs', [])
            present = _item_ids(document)
            imported = {ref['source_id'] for ref in refs if ref['item_id'] in present}
            for selection in selections:
                if not isinstance(selection, dict) or not isinstance(selection.get('id'), str): raise Invalid('选材不合法')
                e = store._get(c, selection['id'], 'wiki_entry')
                if not _fact_allowed(e, job_id): raise Invalid('只能选择个人或当前机会的有效Wiki；任职资料须先确认允许复用的个人事实')
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
                document = _apply_profile(document, p)
            result = save_document(c, store, _document(document), expected, document_id)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.get('/api/resume-documents/{document_id}/versions')
    def versions(document_id:str):
        with store.connect(False) as c:
            get_document(store,c,document_id)
            return dict(versions=[version_summary(v) for v in store._records(c,'editor_version') if v.get('document_id')==document_id])
    @router.post('/api/resume-documents/{document_id}/ai-suggest')
    def ai_suggest(document_id: str, body: dict):
        return generate_ai_suggestion(store, document_id, body)
    @router.get('/api/resume-documents/{document_id}/ai-proposals')
    def ai_proposals(document_id: str):
        with store.connect(False) as c:
            get_document(store, c, document_id)
            return [x for x in store._records(c, 'resume_ai_proposal') if x.get('document_id') == document_id]
    @router.post('/api/resume-documents/{document_id}/ai-proposals/{proposal_id}/resolve')
    def ai_resolve(document_id: str, proposal_id: str, body: dict):
        return resolve_ai_suggestion(store, document_id, proposal_id, body)
    @router.post('/api/resume-documents/{document_id}/versions')
    def save_version(document_id:str,body:dict):
        strict(body,{'name','document','expected_revision','pdf_base64','idempotency_key'})
        name=body.get('name')
        if not isinstance(name,str) or not name.strip() or len(name)>200:raise Invalid('请输入版本名称')
        doc=_document(body.get('document'));raw=_pdf(body.get('pdf_base64'))
        with material_transaction(store) as c:
            old=get_document(store,c,document_id)
            replay,key,fp=op.request(store,c,'save_resume_version',document_id,body)
            if replay is not None:return replay
            if revision(body.get('expected_revision'))!=old['revision'] or doc!=old['document']:raise Conflict('稿已变化，请先保存并核对')
            v,_=insert_version(store,c,old,doc,raw,'ordinary',name.strip(),body['idempotency_key'])
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
