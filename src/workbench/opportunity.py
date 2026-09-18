"""Canonical opportunity actions and explicit legacy read adapters (schema v2)."""
import json
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter
from .core import Invalid, Conflict, Missing, required, uid, now, digest

PHASES = {'resume', 'submitted', 'interview', 'offer'}
RESULTS = {'active', 'accepted', 'rejected', 'withdrawn'}
BUSINESS_TZ = ZoneInfo('Asia/Shanghai')


def company_key(name):
    return unicodedata.normalize('NFKC', required(name, '公司', 500)).strip().casefold()


def business_day(timestamp):
    value = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    if value.tzinfo is None: raise Invalid('日期缺少时区')
    return value.astimezone(BUSINESS_TZ).date().isoformat()


def canonical_id(identifier):
    return identifier if identifier.startswith('opportunity:') else 'opportunity:' + identifier


def company(store, c, body):
    ident, name = body.get('company_id'), body.get('company_name')
    if bool(ident) == bool(name): raise Invalid('company_id与company_name必须且只能提供一个')
    if ident: return store._get(c, required(ident, '公司ID', 500), 'domain_company')
    display = required(name, '公司', 500)
    key = company_key(display)
    matches = [x for x in store._current(c, 'domain_company') if company_key(x['name']) == key]
    if len(matches) > 1:
        raise Conflict('company_ambiguous: 请选择具体公司；候选ID：' + ', '.join(x['id'] for x in matches))
    if matches: return matches[0]
    return store._save(c, 'domain_company', dict(id=uid(), kind='company', name=display,
                       match_key=key, description='', created_at=now()), 0)


def resolve(store, c, identifier):
    ident = required(identifier, '机会ID', 500)
    oid = canonical_id(ident)
    row = c.execute("SELECT revision,body FROM current WHERE id=? AND kind='opportunity'", (oid,)).fetchone()
    obj = json.loads(row[1]) if row else None
    if obj and obj.get('format_version') == 2:
        company_row = store._get(c, obj['company_id'], 'domain_company')
        return dict(obj, revision=row[0], company=company_row['name'], company_revision=company_row['revision'],
                    action_url=obj.get('url',''), read_only=False, legacy=False)
    alias = obj.get('legacy_job_id') if obj else oid[len('opportunity:'):]
    job_row = c.execute("SELECT revision,body FROM current WHERE id=? AND kind='job'", (alias,)).fetchone()
    if not obj and not job_row: raise Missing('机会不存在')
    job = json.loads(job_row[1]) if job_row else obj
    return dict(job, id=oid, legacy_job_id=alias, legacy=True, read_only=True,
                legacy_status=job.get('status'), phase=None, result=None, company_id=None,
                phase_changed_on=None, result_changed_at=None, created_on=None,
                action_url=job.get('url',''), unknown_fields=['company_identity','phase','result','phase_changed_on'])


def writable(store, c, identifier):
    obj = resolve(store, c, identifier)
    if obj['read_only']: raise Conflict('legacy_read_only: 历史资料尚未核对，仍可查看原件')
    return obj


def active(store, c, identifier):
    obj = writable(store, c, identifier)
    if obj['result'] != 'active': raise Conflict('opportunity_ended: 机会已结束')
    return obj


def job_view(store, c, identifier):
    obj = resolve(store, c, identifier)
    alias = obj.get('legacy_job_id') or obj['id'][len('opportunity:'):]
    result={key:obj.get(key) for key in ('company','title','jd','url','revision','created_at','updated_at')}
    result.update(id=alias,opportunity_id=obj['id'],read_only=obj['read_only'],
                  status=obj.get('legacy_status','inactive') if obj['read_only'] else ('active' if obj['result']=='active' else 'inactive'))
    if obj.get('demo_dataset_id'):result['demo_dataset_id']=obj['demo_dataset_id']
    return result


def current_opportunities(store, c, view='all'):
    if view not in {'all','ended',*PHASES}: raise Invalid('机会View不合法')
    ids = {x['id'] for x in store._current(c,'opportunity')}
    ids.update(canonical_id(x['id']) for x in store._current(c,'job'))
    items = [resolve(store,c,id) for id in sorted(ids)]
    if view=='all': return items
    return [x for x in items if not x['read_only'] and
            (x['result']!='active' if view=='ended' else x['result']=='active' and x['phase']==view)]


def current_jobs(store, c):
    return [job_view(store,c,x['id']) for x in current_opportunities(store,c)]


def _context(store, c, job_id):
    obj=resolve(store,c,job_id)
    alias=obj.get('legacy_job_id') or obj['id'][len('opportunity:'):]
    rows=c.execute("SELECT body FROM current WHERE kind='opportunity_context' AND json_extract(body,'$.job_id')=?",(alias,)).fetchall()
    old=json.loads(rows[0][0]) if len(rows)==1 else {}
    return old if obj['read_only'] else dict(old,company_id=obj['company_id'],canonical_revision=obj['revision'])


def expected(body):
    value=body.get('expected_revision')
    if type(value) is not int or value<0: raise Invalid('expected_revision必须是非负整数，请刷新客户端')
    return value


def request(store,c,action,identifier,body):
    key=required(body.get('idempotency_key'),'idempotency_key（请刷新客户端）',200)
    ident='opportunity-command:'+digest([action,identifier,key])
    fingerprint=digest(body)
    row=c.execute("SELECT body FROM records WHERE id=? AND kind='opportunity_command'",(ident,)).fetchone()
    if row:
        previous=json.loads(row[0])
        if previous['fingerprint']!=fingerprint: raise Conflict('请求标识已用于不同内容')
        return previous['result'],ident,fingerprint
    return None,ident,fingerprint


def remember(store,c,ident,fingerprint,result):
    store._record(c,'opportunity_command',dict(id=ident,fingerprint=fingerprint,result=result))
    return result


def values(body, old=None):
    allowed={'company_id','company_name','title','jd','action_url','url','expected_revision','idempotency_key'}
    if set(body)-allowed: raise Invalid('不允许修改字段：'+','.join(sorted(set(body)-allowed)))
    old=old or {}
    title=required(body.get('title',old.get('title')),'岗位',500)
    jd=required(body.get('jd',old.get('jd')),'JD')
    if 'url' in body and 'action_url' in body and body['url']!=body['action_url']:raise Invalid('链接字段不一致')
    url=body.get('action_url',body.get('url',old.get('url','')))
    if not isinstance(url,str) or len(url)>2000 or (url and not url.startswith(('https://','http://'))): raise Invalid('URL仅支持http/https')
    return dict(title=title,jd=jd,url=url)


def create_opportunity(store,body):
    info=values(body)
    with store.connect() as c:
        replay,key,fingerprint=request(store,c,'create',None,body)
        if replay is not None:return replay
        owner=company(store,c,body)
        stamp=now();day=business_day(stamp)
        obj=dict(id=canonical_id(uid()),format_version=2,legacy_job_id=None,company_id=owner['id'],**info,
                 phase='resume',result='active',created_on=day,created_at=stamp,phase_changed_on=day,
                 phase_source=dict(action='CreateOpportunity',occurred_at=stamp),result_changed_at=None)
        store._save(c,'opportunity',obj,0);store._bump(c)
        return remember(store,c,key,fingerprint,resolve(store,c,obj['id']))


def update_in_transaction(store,c,identifier,body):
    replay,key,fingerprint=request(store,c,'update',canonical_id(identifier),body)
    if replay is not None:return replay
    current=writable(store,c,identifier)
    revision=expected(body)
    if revision!=current['revision']:raise Conflict('机会已更新，请保留输入并重新载入比较')
    info=values(body,current)
    row=store._get(c,current['id'],'opportunity')
    if 'company_name' in body or 'company_id' in body:row['company_id']=company(store,c,body)['id']
    store._save(c,'opportunity',dict(row,**info),revision);store._bump(c)
    return remember(store,c,key,fingerprint,resolve(store,c,current['id']))


def update_opportunity(store,identifier,body):
    with store.connect() as c:return update_in_transaction(store,c,identifier,body)


def end_opportunity(store,identifier,body):
    if set(body)-{'result','offer_id','expected_revision','expected_offer_revision','idempotency_key'}:raise Invalid('结束动作不接受其它字段')
    result=body.get('result')
    if result not in RESULTS-{'active'}:raise Invalid('结束结果不合法')
    if result=='accepted':
        from .offer import accept_offer
        return accept_offer(store,identifier,body.get('offer_id'),dict(
            expected_opportunity_revision=body.get('expected_revision'),
            expected_offer_revision=body.get('expected_offer_revision'),
            idempotency_key=body.get('idempotency_key')),compatibility=True)
    with store.connect() as c:
        replay,key,fingerprint=request(store,c,'end',canonical_id(identifier),body)
        if replay is not None:return replay
        current=writable(store,c,identifier)
        if expected(body)!=current['revision']:raise Conflict('机会已更新，请重新载入')
        if current['result']!='active':
            if current['result']!=result:raise Conflict('机会已结束，不能通过此动作更换结果')
            return remember(store,c,key,fingerprint,current)
        transition_result_in_transaction(store,c,current,result);store._bump(c)
        return remember(store,c,key,fingerprint,resolve(store,c,current['id']))


def transition_result_in_transaction(store,c,current,result):
    """The single Opportunity result mutation used by End and AcceptOffer."""
    row=store._get(c,current['id'],'opportunity')
    row.update(result=result,result_changed_at=now())
    return store._save(c,'opportunity',row,current['revision'])


def legacy_save(store,body,identifier=None):
    request_body=dict(body)
    if identifier and any(body.get(k) and canonical_id(body[k])!=canonical_id(identifier) for k in ('id','opportunity_id')):
        raise Invalid('旧入口标识与URL不一致')
    if 'company' in request_body:request_body['company_name']=request_body.pop('company')
    if 'status' in request_body:
        status=request_body.pop('status')
        if identifier is None:
            if status!='active':raise Conflict('legacy_status_retired: 请使用机会领域动作')
        else:
            with store.connect(False) as c:
                current=job_view(store,c,identifier)
                if current['read_only'] or status!=current['status']:raise Conflict('legacy_status_retired: 请使用结束机会动作')
    for field in ('id','opportunity_id','read_only','revision','created_at','updated_at','source'):
        request_body.pop(field,None)
    # Identity and lifecycle fields cannot be reassigned by the adapter.
    result=update_opportunity(store,identifier,request_body) if identifier else create_opportunity(store,request_body)
    dto={k:result.get(k) for k in ('company','title','jd','url','revision','created_at','updated_at')}
    return dict(dto,id=result.get('legacy_job_id') or result['id'][len('opportunity:'):],opportunity_id=result['id'],read_only=False,status='active' if result['result']=='active' else 'inactive')


def router(store):
    api=APIRouter(prefix='/api/opportunities')
    @api.get('')
    def listing(view:str='all'):
        with store.connect(False) as c:return current_opportunities(store,c,view)
    @api.get('/{identifier}')
    def detail(identifier:str):
        with store.connect(False) as c:return resolve(store,c,identifier)
    @api.post('')
    def create(body:dict):return create_opportunity(store,body)
    @api.post('/{identifier}')
    def update(identifier:str,body:dict):return update_opportunity(store,identifier,body)
    @api.post('/{identifier}/end')
    def end(identifier:str,body:dict):return end_opportunity(store,identifier,body)
    return api
