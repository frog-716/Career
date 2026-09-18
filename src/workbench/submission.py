"""One real submission, one domain transaction, optional frozen resume."""
from fastapi import APIRouter
from .core import Conflict, Invalid, digest, dump, now, uid
from . import opportunity as op
from . import resume_artifacts as files
from .resume_documents import (strict,revision,get_document,for_opportunity,create_document,
                               copy_source,material_transaction,insert_version)
from .editor import _pdf, _document


def record_submitted(store,oid,body):
    strict(body,{'expected_revision','idempotency_key','resume'})
    selected=body.get('resume')
    if not isinstance(selected,dict):raise Invalid('请选择当前稿/固定版本/本次无简历')
    mode=selected.get('mode')
    fields={'none':{'mode'},'draft':{'mode','document_id','expected_document_revision','document','pdf_base64'},'version':{'mode','source_version_id','source_document_hash','source_artifact_hash'}}
    if mode not in fields:raise Invalid('投递材料模式不合法')
    strict(selected,fields[mode])
    raw=_pdf(selected.get('pdf_base64')) if mode=='draft' else None
    with material_transaction(store) as c:
        o=op.writable(store,c,oid)
        replay,key,fp=op.request(store,c,'record_submitted',o['id'],body)
        if replay is not None:return replay
        if c.execute('SELECT 1 FROM applications WHERE canonical_opportunity_id=? OR job_id=? OR json_extract(body,\'$.opportunity_id\')=?',(o['id'],o.get('legacy_job_id') or o['id'].split(':',1)[1],o['id'])).fetchone():raise Conflict('该机会已记录投递，不能重复登记')
        if revision(body.get('expected_revision'))!=o['revision']:raise Conflict('机会/Greeting已更新，请核对后重试')
        if o['result']!='active' or o['phase']!='resume':raise Conflict('此阶段须明确历史补录，普通投递动作不能回退阶段')
        sid=uid();stamp=now();day=op.business_day(stamp);v=a=d=None;source=None
        if mode=='draft':
            d=get_document(store,c,selected.get('document_id'))
            if d['opportunity_id']!=o['id']:raise Conflict('不能投递另一个机会的当前稿')
            if revision(selected.get('expected_document_revision'))!=d['revision'] or _document(selected.get('document'))!=d['document']:raise Conflict('当前稿已变化，请重新核对')
            doc=d['document']
        elif mode=='version':
            source=store._get(c,selected.get('source_version_id'),'editor_version',True)
            a=store._get(c,source['artifact_id'],'artifact',True)
            if selected.get('source_document_hash')!=digest(source['document']) or selected.get('source_artifact_hash')!=a['sha256']:raise Conflict('来源版本/PDF hash不一致')
            raw=files.checked_bytes(store.data_dir,a);doc=source['document']
            did=for_opportunity(c,o['id'])
            if did:d=get_document(store,c,did)
            else:
                copied,provenance=copy_source(store,c,dict(kind='version',source_version_id=source['id'],source_document_hash=digest(doc)))
                d=create_document(store,c,o['id'],copied,provenance)
        if mode!='none':
            v,a=insert_version(store,c,d,doc,raw,'submission',o['company']+' · '+o['title']+' · 投递版本 · '+day,body['idempotency_key'],sid,source['id'] if source else None)
        greeting=dict(state='not_used') if o.get('greeting') is None else dict(state='captured',content=o['greeting'])
        event=dict(id=sid,submission_format=3,opportunity_id=o['id'],job_id=o.get('legacy_job_id') or o['id'].split(':',1)[1],submitted_on=day,recorded_at=stamp,applied_at=stamp,
                   submitted_greeting_snapshot=greeting,version_id=v['id'] if v else None,artifact_id=a['id'] if a else None,
                   artifact_hash=a['sha256'] if a else None,resume_snapshot=v,artifact_snapshot=a,job_snapshot=op.job_view(store,c,o['id']),opportunity_snapshot=o,request_fingerprint=fp)
        c.execute('INSERT INTO applications(id,job_id,version_id,artifact_id,idempotency_key,body,canonical_opportunity_id) VALUES(?,?,?,?,?,?,?)',
                  (sid,event['job_id'],event['version_id'],event['artifact_id'],key,dump(event),o['id']))
        files.fault('after_submission')
        row=store._get(c,o['id'],'opportunity');row.update(phase='submitted',phase_changed_on=day,phase_source=dict(action='RecordSubmitted',occurred_at=stamp,submission_id=sid))
        store._save(c,'opportunity',row,o['revision']);store._bump(c)
        result=dict(submission=event,opportunity=op.resolve(store,c,o['id']),submission_version=v,resume_document=d)
        return op.remember(store,c,key,fp,result)


def router(store):
    r=APIRouter()
    @r.post('/api/opportunities/{oid}/submitted')
    def submit(oid:str,body:dict):return record_submitted(store,oid,body)
    @r.post('/api/opportunities/{oid}/greeting')
    def greeting(oid:str,body:dict):
        strict(body,{'content','expected_revision','idempotency_key'})
        content=body.get('content')
        if content is not None and (not isinstance(content,str) or len(content)>20000):raise Invalid('Greeting最多20000字符')
        with store.connect() as c:
            o=op.writable(store,c,oid)
            replay,key,fp=op.request(store,c,'greeting',o['id'],body)
            if replay is not None:return replay
            if revision(body.get('expected_revision'))!=o['revision']:raise Conflict('机会已更新，请保留Greeting并比较')
            row=store._get(c,o['id'],'opportunity');row['greeting']=content
            store._save(c,'opportunity',row,o['revision']);store._bump(c)
            return op.remember(store,c,key,fp,op.resolve(store,c,o['id']))
    return r
