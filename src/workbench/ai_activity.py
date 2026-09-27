"""Read-only UX projection of existing operations and proposal lifecycles.

No provider, prepare, recovery mutation, career body, or second task store.
"""
import json
from urllib.parse import quote

from fastapi import APIRouter
from .core import Missing

TASKS = {
    'wiki_compiler': '整理 Wiki', 'wiki_cognition_compiler': '整理长期认知',
    'research_update': '整理岗位研究', 'research_search': '查找岗位资料',
    'resume_optimization': '简历优化', 'interview_final_review': '整理面试复盘',
    'interview_research_patch': '整理面试信息', 'legacy_analysis': '分析机会', 'connection_test':'模型连接检查',
}
STATES = {'preparing':'准备中', 'processing':'处理中', 'pending':'待处理',
          'completed':'完成', 'failed':'失败', 'unknown':'结果未知'}


def _field(c, table, kind, identifier, field):
    # Identifiers and JSON paths are module constants, never request input.
    row = c.execute(f"SELECT json_extract(body,'$.{field}') FROM {table} WHERE kind=? AND id=?", (kind, identifier)).fetchone()
    return row[0] if row else None


def _owner(c, kind, identifier):
    if kind == 'raw_material':
        scope = _field(c, 'records', kind, identifier, 'scope_type')
        target = _field(c, 'records', kind, identifier, 'scope_id')
        return _owner(c, scope, target) if scope else None
    if kind == 'resume_document':
        target = _field(c, 'current', kind, identifier, 'opportunity_id')
        return _owner(c, 'opportunity', target) if target else None
    if kind in ('interview', 'interview_session'):
        target = _field(c, 'records', 'interview', identifier, 'opportunity_id')
        return _owner(c, 'opportunity', target) if target else None
    kind = {'work_project':'project', 'work_person':'person'}.get(kind, kind)
    stored = {'project':'work_project','person':'work_person'}.get(kind, kind)
    if kind == 'project':
        label = _field(c,'current',stored,identifier,'name'); href='#projects/'+quote(identifier, safe='')
    elif kind == 'employment':
        label = _field(c,'current',stored,identifier,'company')
        role = _field(c,'current',stored,identifier,'role')
        if role: label = (label or '任职')+' · '+role
        alias = _field(c,'current',stored,identifier,'legacy_episode_id') or identifier
        href='#work/'+quote(alias, safe='')
    elif kind == 'person':
        label = _field(c,'current',stored,identifier,'name')
        employment = _field(c,'current',stored,identifier,'employment_id')
        parent = _owner(c,'employment',employment) if employment else None
        href=parent['href'] if parent else '#work'
    elif kind == 'opportunity':
        label = _field(c,'current',stored,identifier,'company')
        company_id = _field(c,'current',stored,identifier,'company_id')
        if not label and company_id: label = _field(c,'current','domain_company',company_id,'name')
        title = _field(c,'current',stored,identifier,'title')
        label = ' · '.join(x for x in (label,title) if x)
        href='#opportunities/'+quote(identifier, safe='')
    elif kind in ('cognition','personal'):
        label='长期认知' if kind=='cognition' else '个人职业资料';href='#wiki'
    else:
        return None
    return {'type':kind,'id':identifier,'label':label or '原对象已不可用','href':href}


def _proposal(c, op):
    # Select only status and references. Never load proposed text or before snapshots.
    row=c.execute("""SELECT id,kind,json_extract(body,'$.status') FROM records
        WHERE kind IN ('wiki_compiler_proposal','research_proposal','resume_ai_proposal','patch_proposal')
          AND (json_extract(body,'$.operation_id')=? OR
            (json_extract(body,'$.request_key')=? AND
             ((kind='resume_ai_proposal' AND json_extract(body,'$.document_id')=?) OR
              (kind='research_proposal' AND json_extract(body,'$.opportunity_id')=?))))
        ORDER BY rowid DESC LIMIT 1""",(op['id'],op['key'],op['target_id'],op['target_id'])).fetchone()
    if not row and op['result_ref']:
        ref=json.loads(op['result_ref'])
        pid=_field(c,'records','ai_operation_result',ref.get('id'),'value.proposal_id') or _field(c,'records','ai_operation_result',ref.get('id'),'value.id')
        if pid:
            row=c.execute("SELECT id,kind,json_extract(body,'$.status') FROM records WHERE id=? AND kind IN ('wiki_compiler_proposal','research_proposal','resume_ai_proposal','patch_proposal')",(pid,)).fetchone()
    if not row:return None
    identifier,kind,status=row
    if kind=='wiki_compiler_proposal':
        statuses=[r[0] for r in c.execute("SELECT json_extract(p.value,'$.status') FROM records r,json_each(r.body,'$.patches') p WHERE r.id=? AND r.kind=?",(identifier,kind))]
        pending=statuses.count('pending') if status=='pending' else 0
        return {'id':identifier,'kind':kind,'status':status,'total':len(statuses),'pending':pending,'reviewed':len(statuses)-pending}
    return {'id':identifier,'kind':kind,'status':status,'total':1,'pending':int(status=='pending'),'reviewed':int(status!='pending')}


def _project(c, row):
    keys=('id','task','target_kind','target_id','key','backend_state','code','created_at','finished_at','manifest','result_ref','stale','expired')
    op=dict(zip(keys,row));proposal=_proposal(c,op)
    backend=op['backend_state']
    if backend in ('reserved','dispatching','confirmed'):
        state='processing';message='AI 正在整理，可以关闭窗口，不影响处理。'
    elif backend=='prepared':
        state='preparing';message='请确认本次发送的资料。'
    elif backend=='outcome_unknown':
        state='unknown';message='请求已经发送，但 Career 无法确认是否成功。为了避免重复调用，不会自动重试。'
    elif op['expired']:
        state='preparing';message='预览已过期，尚未发送。请重新预览。'
    elif op['stale'] or op['code']=='prepared_request_stale':
        state='preparing';message='资料在预览后发生了变化，请重新确认发送内容。'
    elif backend=='failed':
        state='failed';message='没有修改资料。'
    elif backend=='succeeded':
        if proposal and proposal['pending']:
            state='pending';message=f"有 {proposal['pending']} 条建议待处理。"
        elif proposal and proposal['status'] in ('invalid','failed'):
            state='failed';message='AI 返回的结果无法安全使用，本次没有修改资料。'
        else:
            state='completed';message='建议已处理完成。' if proposal else '本次处理已完成，当前没有待处理建议。'
            if not proposal and op['result_ref']:
                reference=json.loads(op['result_ref'])
                if _field(c,'records','ai_operation_result',reference.get('id'),'value.status')=='no_changes':
                    message='已整理，没有发现值得更新的长期信息。'
            if proposal and proposal['status']=='superseded':message='这组建议已被替代，不需要处理。'
            if not proposal and op['task'] not in ('wiki_compiler','wiki_cognition_compiler'):message='本次处理已完成。'
    else:
        state='unknown';message='暂时无法确认这次操作的状态，不会自动重试。'
    owners=[]
    if op['task']=='wiki_cognition_compiler':
        manifest=json.loads(op['manifest'] or '{}')
        if not manifest:
            prepared=c.execute("SELECT json_extract(body,'$.manifest') FROM records WHERE kind='ai_preparation' AND json_extract(body,'$.task_type')=? AND json_extract(body,'$.idempotency_key')=? ORDER BY rowid DESC LIMIT 1",(op['task'],op['key'])).fetchone()
            if prepared and prepared[0]:manifest=json.loads(prepared[0])
        for dep in manifest.get('dependencies',[]):
            if dep.get('purpose')=='selected_experience':
                owner=_owner(c,dep.get('kind'),dep.get('id'))
                if owner:owners.append(owner)
    else:
        owner=_owner(c,op['target_kind'],op['target_id'])
        if owner:owners.append(owner)
    if not owners:owners=[{'type':'cognition' if op['task']=='wiki_cognition_compiler' else 'unknown','id':'','label':'长期认知' if op['task']=='wiki_cognition_compiler' else '原对象已不可用','href':'#wiki'}]
    return {'operation_id':op['id'],'task':op['task'],'title':TASKS.get(op['task'],'AI 操作'),
            'state':state,'state_label':STATES[state],'message':message,'owners':owners,
            'created_at':op['created_at'],'finished_at':op['finished_at'],
            'proposal_id':proposal['id'] if proposal else None,
            'proposal_kind':proposal['kind'] if proposal else None,
            'review':{k:proposal[k] for k in ('total','reviewed','pending')} if proposal else None}


def read_activity(store, identifier=None):
    with store.connect(False) as c:
        query="""SELECT op_id,task_type,target_kind,target_id,idempotency_key,state,error_code,
            created_at,finished_at,manifest,result_ref,
            CASE WHEN error_message LIKE 'prepared_request_stale:%' THEN 1 ELSE 0 END,
            CASE WHEN dispatched_at IS NULL AND (error_code='prepared_request_expired'
                OR (error_code='Missing' AND error_message='准备对象已过期，请重新预览')) THEN 1 ELSE 0 END
            FROM ai_operations"""
        if identifier:
            rows=c.execute(query+' WHERE op_id=?',(identifier,)).fetchall()
            if not rows:raise Missing('AI 操作不存在')
        else:
            # All attention-worthy operations remain discoverable, even after many completed calls.
            rows=c.execute(query+' ORDER BY rowid DESC').fetchall()
        return [_project(c,row) for row in rows if row[1] in TASKS]


def router(store):
    api=APIRouter()
    @api.get('/api/ai/activity')
    def activity():return {'items':read_activity(store)}
    @api.get('/api/ai/activity/{operation_id}')
    def detail(operation_id: str):
        values=read_activity(store,operation_id)
        if not values:raise Missing('AI 操作不存在')
        return values[0]
    return api
