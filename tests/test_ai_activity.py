"""UX-1 status projection is read-only, owner-specific and never dispatches."""
import json
import threading
from fastapi.testclient import TestClient
from workbench.app import create_app
from workbench.core import Store, now
from workbench.providers import TestProvider


def harness(tmp_path):
    store = Store(tmp_path / 'data', TestProvider())
    return store, TestClient(create_app(store), base_url='http://127.0.0.1', headers={'X-Career-Request':'1'})


def seed(store, state='succeeded', code=None, task='wiki_compiler', target_kind='raw_material', target_id='raw-x', key='one', proposal=None):
    with store.connect() as c:
        c.execute("INSERT INTO ai_operations(op_id,task_type,target_kind,target_id,idempotency_key,client_intent_hash,state,error_code,created_at,reserved_at,dispatched_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(key,task,target_kind,target_id,key,'hash',state,code,now(),now(),now() if state!='reserved' else None,now() if state not in ('reserved','dispatching') else None))
        if proposal:
            store._record(c,'wiki_compiler_proposal',{'id':'proposal-'+key,'operation_id':key,'status':'pending','context_kind':'cognition' if task=='wiki_cognition_compiler' else 'wiki','patches':[{'status':x,'content':'MODEL_BODY_CANARY'} for x in proposal]})


def test_all_states_and_partial_review_are_read_only(tmp_path):
    s,c=harness(tmp_path)
    for key,state,code,patches in [('running','dispatching',None,None),('confirmed','reserved',None,None),('waiting','succeeded',None,['accepted','pending','pending']),('zero','succeeded',None,None),('fail','failed','invalid_result',None),('unknown','outcome_unknown','timeout',None),('stale','failed','prepared_request_stale',None)]:
        seed(s,state,code,key=key,proposal=patches)
    with s.connect(False) as db: before=db.execute('select * from ai_operations order by op_id').fetchall()
    response=c.get('/api/ai/activity');assert response.status_code==200
    items={x['operation_id']:x for x in response.json()['items']}
    assert {k:v['state'] for k,v in items.items()}=={'running':'processing','confirmed':'processing','waiting':'pending','zero':'completed','fail':'failed','unknown':'unknown','stale':'preparing'}
    assert items['waiting']['review']=={'total':3,'reviewed':1,'pending':2}
    assert items['waiting']['proposal_id']=='proposal-waiting'
    assert items['stale']['message']=='资料在预览后发生了变化，请重新确认发送内容。'
    assert 'MODEL_BODY_CANARY' not in response.text
    for _ in range(3): assert c.get('/api/ai/activity/waiting').status_code==200
    with s.connect() as db:
        assert db.execute('select * from ai_operations order by op_id').fetchall()==before
        proposal=s._get(db,'proposal-waiting','wiki_compiler_proposal',True)
        proposal['status']='resolved'
        for patch in proposal['patches']:patch['status']='rejected'
        s._record(db,'wiki_compiler_proposal',proposal)
    assert c.get('/api/ai/activity/waiting').json()['state']=='completed'
    s.shutdown()


def test_owners_and_module_compatibility_do_not_read_career_bodies(tmp_path):
    s,c=harness(tmp_path)
    project=c.post('/api/work/projects',json={'name':'虚构项目甲','idempotency_key':'p'}).json()
    raw=c.post('/api/raw',json={'scope_type':'project','scope_id':project['id'],'title':'虚构资料','content':'RAW_BODY_CANARY','source_kind':'manual_text','idempotency_key':'r'}).json()
    op=c.post('/api/opportunities',json={'company_name':'虚构公司乙','title':'虚构岗位','jd':'JD_BODY_CANARY','idempotency_key':'o'}).json()
    seed(s,key='wiki',target_id=raw['id'],proposal=['pending'])
    seed(s,key='research',task='research_update',target_kind='opportunity',target_id=op['id'],state='failed')
    with s.connect() as db:
        s._record(db,'resume_ai_proposal',{'id':'rp','request_key':'resume','document_id':'doc','status':'pending','patches':[{'status':'pending','content':'RESUME_CANARY'}]})
        db.execute('insert into current values(?,?,?,?)',('doc','resume_document',1,json.dumps({'id':'doc','opportunity_id':op['id'],'document':'RESUME_CANARY'})))
    seed(s,key='resume',task='resume_optimization',target_kind='resume_document',target_id='doc')
    result=c.get('/api/ai/activity');assert result.status_code==200
    items={x['operation_id']:x for x in result.json()['items']}
    assert items['wiki']['owners'][0]['label']=='虚构项目甲'
    assert items['wiki']['owners'][0]['id']==project['id']
    assert '虚构公司乙' in items['research']['owners'][0]['label']
    assert items['resume']['owners'][0]['id']==op['id']
    assert items['resume']['state']=='pending'
    assert all(x not in result.text for x in ('RAW_BODY_CANARY','JD_BODY_CANARY','RESUME_CANARY','MODEL_BODY_CANARY'))
    assert c.get('/api/ai/activity/missing').status_code==404
    s.shutdown()


def test_active_request_survives_reader_recreation_without_redispatch(tmp_path):
    from workbench import ai_operations as ao
    s,c=harness(tmp_path);entered=threading.Event();release=threading.Event();calls=[]
    def dispatch(_prepared,_binder):
        calls.append(1);entered.set();assert release.wait(10);return {},{}
    def execute():
        ao.execute(s,task_type='wiki_compiler',target_kind='raw_material',target_id='fake',idempotency_key='key',client_intent={},prepare=lambda:{},dispatch=dispatch,persist=lambda *_:{'status':'no_changes'})
    thread=threading.Thread(target=execute);thread.start();assert entered.wait(5)
    try:
        for _ in range(3):
            reader=TestClient(create_app(s),base_url='http://127.0.0.1')
            r=reader.get('/api/ai/activity');assert r.status_code==200
            assert r.json()['items'][0]['state']=='processing'
    finally:release.set();thread.join(5)
    assert c.get('/api/ai/activity').json()['items'][0]['state']=='completed'
    assert calls==[1]
    s.shutdown()


def test_cognition_owners_terminal_proposals_and_failed_validation(tmp_path):
    s,c=harness(tmp_path)
    projects=[c.post('/api/work/projects',json={'name':f'虚构经历{x}','idempotency_key':str(x)}).json() for x in range(2)]
    seed(s,key='cog',task='wiki_cognition_compiler',target_kind='wiki_scope',target_id='cognition',proposal=['pending','pending'])
    with s.connect() as db:
        db.execute('update ai_operations set manifest=? where op_id=?',(json.dumps({'dependencies':[{'purpose':'selected_experience','kind':'work_project','id':p['id']} for p in projects]}),'cog'))
        before=db.execute('select count(*) from current').fetchone()[0]
    item=c.get('/api/ai/activity/cog').json()
    assert [x['label'] for x in item['owners']]==['虚构经历0','虚构经历1']
    for state,expected in [('superseded','completed'),('invalid','failed'),('resolved','completed')]:
        with s.connect() as db:
            proposal=s._get(db,'proposal-cog','wiki_compiler_proposal',True);proposal['status']=state;s._record(db,'wiki_compiler_proposal',proposal)
        assert c.get('/api/ai/activity/cog').json()['state']==expected
    with s.connect(False) as db:assert db.execute('select count(*) from current').fetchone()[0]==before
    s.shutdown()


def test_status_mapping_does_not_mislabel_stale_as_provider_failure(tmp_path):
    s,c=harness(tmp_path);seed(s,'failed','Conflict',key='stale-real')
    with s.connect() as db:db.execute("update ai_operations set error_message='prepared_request_stale: internal detail' where op_id='stale-real'")
    item=c.get('/api/ai/activity/stale-real').json()
    assert item['state']=='preparing'
    assert 'internal detail' not in json.dumps(item)
    assert '没有成功' not in item['message']
    s.shutdown()


def test_api_restores_original_partial_proposal_without_prepare_or_dispatch(tmp_path):
    s,c=harness(tmp_path);calls=[]
    p=c.post('/api/work/projects',json={'name':'虚构四条建议项目','idempotency_key':'p'}).json()
    raw=c.post('/api/raw',json={'scope_type':'project','scope_id':p['id'],'source_kind':'manual_text','title':'虚构原文','content':'虚构计划甲乙丙丁。','idempotency_key':'r'}).json()
    def complete(payload):
        calls.append(1)
        return {'patches':[{'operation':'add','scope_type':'project','scope_id':p['id'],'knowledge_type':'fact','content':f'虚构计划{x}','tags':[],'reason':'虚构原文','source_refs':[{'kind':'raw_material','id':raw['id'],'revision':raw['revision']}]} for x in '甲乙丙丁']}
    s.provider.complete=complete
    intent={'raw_id':raw['id'],'idempotency_key':'send-once'}
    preview=c.post('/api/wiki/compiler/prepare',json=intent).json()
    response=c.post('/api/wiki/compiler/execute',json={**intent,'prepared_id':preview['prepared_id'],'payload_hash':preview['payload_hash'],'confirm_outbound':True})
    assert response.status_code==200,response.text
    proposal=response.json()['proposal']
    assert proposal['scopes'][0]['minimal_identity']['name']=='虚构四条建议项目'
    op=c.get('/api/ai/activity').json()['items'][0]
    for index in range(2):
        r=c.post(f"/api/wiki/compiler/proposals/{proposal['id']}/patches/{proposal['patches'][index]['id']}/resolve",json={'decision':'reject','idempotency_key':f'reject-{index}'})
        assert r.status_code==200,r.text
    reopened=TestClient(create_app(s),base_url='http://127.0.0.1')
    restored=reopened.get('/api/ai/activity/'+op['operation_id']).json()
    assert restored['review']=={'total':4,'reviewed':2,'pending':2}
    assert restored['proposal_id']==proposal['id']
    assert reopened.get('/api/wiki/compiler/proposals/'+restored['proposal_id']).json()['patches'][2]['status']=='pending'
    with s.connect(False) as db:
        assert db.execute("select count(*) from records where kind='ai_preparation'").fetchone()[0]==1
        assert db.execute("select count(*) from current where kind='wiki_knowledge'").fetchone()[0]==0
    assert calls==[1]
    s.shutdown()


def test_expired_preview_is_not_provider_failure_and_never_dispatches(tmp_path):
    s,c=harness(tmp_path);calls=[]
    s.provider.complete=lambda payload:calls.append(payload)
    p=c.post('/api/work/projects',json={'name':'虚构过期预览','idempotency_key':'p'}).json()
    raw=c.post('/api/raw',json={'scope_type':'project','scope_id':p['id'],'source_kind':'manual_text','title':'虚构','content':'虚构计划','idempotency_key':'r'}).json()
    intent={'raw_id':raw['id'],'idempotency_key':'expired'}
    preview=c.post('/api/wiki/compiler/prepare',json=intent).json()
    with s.connect() as db:
        item=s._get(db,preview['prepared_id'],'ai_preparation',True)
        item['expires_at']='2000-01-01T00:00:00+00:00';s._record(db,'ai_preparation',item)
    response=c.post('/api/wiki/compiler/execute',json={**intent,'prepared_id':preview['prepared_id'],'payload_hash':preview['payload_hash'],'confirm_outbound':True})
    assert response.status_code==404
    assert response.json()['code']=='prepared_request_expired'
    item=c.get('/api/ai/activity').json()['items'][0]
    assert item['state']=='preparing'
    assert item['message']=='预览已过期，尚未发送。请重新预览。'
    assert calls==[]
    with s.connect(False) as db:
        assert db.execute('select dispatched_at from ai_operations').fetchone()[0] is None
        assert db.execute("select count(*) from records where kind='wiki_compiler_proposal'").fetchone()[0]==0
    # Old audit remains untouched but receives the same correct read-only mapping.
    with s.connect() as db:
        db.execute("update ai_operations set error_code='Missing',error_message='准备对象已过期，请重新预览'")
    assert c.get('/api/ai/activity').json()['items'][0]['state']=='preparing'
    s.shutdown()


def test_real_http_disconnect_before_provider_completion_restores_original_proposal(tmp_path):
    import socket
    import time
    import urllib.request
    import uvicorn
    s,c=harness(tmp_path);entered=threading.Event();release=threading.Event();calls=[]
    p=c.post('/api/work/projects',json={'name':'虚构断连项目','idempotency_key':'p'}).json()
    raw=c.post('/api/raw',json={'scope_type':'project','scope_id':p['id'],'source_kind':'manual_text','title':'虚构原文','content':'虚构计划甲乙。','idempotency_key':'r'}).json()
    def complete(payload):
        calls.append(1);entered.set();assert release.wait(10)
        return {'patches':[{'operation':'add','scope_type':'project','scope_id':p['id'],'knowledge_type':'fact','content':f'虚构计划{x}','tags':[],'reason':'虚构原文','source_refs':[{'kind':'raw_material','id':raw['id'],'revision':raw['revision']}]} for x in '甲乙']}
    s.provider.complete=complete
    listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(create_app(s),log_level='error',lifespan='off'))
    thread=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True);thread.start()
    base=f'http://127.0.0.1:{port}'
    def request(path,body=None):
        req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Career-Request':'1'})
        with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
    try:
        deadline=time.monotonic()+5
        while not server.started and time.monotonic()<deadline:time.sleep(.01)
        assert server.started
        intent={'raw_id':raw['id'],'idempotency_key':'once'}
        preview=request('/api/wiki/compiler/prepare',intent)
        body=json.dumps({**intent,'prepared_id':preview['prepared_id'],'payload_hash':preview['payload_hash'],'confirm_outbound':True}).encode()
        original=socket.create_connection(('127.0.0.1',port))
        original.sendall((f'POST /api/wiki/compiler/execute HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\nX-Career-Request: 1\r\nContent-Length: {len(body)}\r\n\r\n').encode()+body)
        assert entered.wait(5)
        # The browser connection disappears while Provider is still blocked.
        original.shutdown(socket.SHUT_RDWR);original.close()
        assert original.fileno()==-1
        running=request('/api/ai/activity')['items'][0];assert running['state']=='processing'
        with s.connect(False) as db:assert db.execute("select count(*) from records where kind='wiki_compiler_proposal'").fetchone()[0]==0
        release.set()  # Provider completes only after the client no longer exists.
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            restored=request('/api/ai/activity')['items'][0]
            if restored['state']=='pending':break
            time.sleep(.01)
        assert restored['state']=='pending'
        assert restored['operation_id']==running['operation_id']
        pid=restored['proposal_id'];proposal=request('/api/wiki/compiler/proposals/'+pid)
        for _ in range(3):assert request('/api/ai/activity')['items'][0]['proposal_id']==pid
        patch=proposal['patches'][0]
        request(f"/api/wiki/compiler/proposals/{pid}/patches/{patch['id']}/resolve",{'decision':'accept','idempotency_key':'accept'})
        progress=request('/api/ai/activity')['items'][0]
        assert progress['review']=={'total':2,'pending':1,'reviewed':1}
        assert progress['proposal_id']==pid
        assert request('/api/wiki/compiler/proposals/'+pid)['patches'][0]['status']=='accepted'
        with s.connect(False) as db:
            assert db.execute('select count(*) from ai_operations where dispatched_at is not null').fetchone()[0]==1
            assert db.execute("select count(*) from records where kind='ai_preparation'").fetchone()[0]==1
            assert db.execute("select count(*) from records where kind='wiki_compiler_proposal'").fetchone()[0]==1
        assert calls==[1]
    finally:
        release.set();server.should_exit=True;thread.join(5);listener.close();s.shutdown()
