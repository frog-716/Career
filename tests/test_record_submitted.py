"""Batch C public HTTP contract, isolated synthetic data only."""
import base64
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from fastapi.testclient import TestClient
from workbench.app import create_app
from workbench.core import Store, digest
from workbench.providers import TestProvider

PDF = base64.b64encode(b'%PDF-1.7\nsynthetic-resume\n%%EOF').decode()
H = {'X-Career-Request':'1','Content-Type':'application/json'}

def client_at(path):
    store = Store(path, TestProvider())
    return TestClient(create_app(store), headers=H), store

def post(c, path, body):
    response = c.post('/api'+path, json=body)
    assert response.status_code == 200, response.text
    return response.json()

def opportunity(c, key):
    return post(c, '/opportunities', dict(company_name='虚构公司', title=key, jd='虚构 JD', idempotency_key=key))

def start(c, o, source=None):
    return post(c, '/opportunities/'+o['id']+'/resume/start', dict(expected_opportunity_revision=o['revision'], idempotency_key='start', source=source or {'kind':'blank'}))

def save(c, d, name):
    doc=deepcopy(d['document']);doc['profile']['name']=name
    r=c.put('/api/resume-documents/'+d['document_id'],json=dict(document=doc,expected_revision=d['revision']))
    assert r.status_code==200,r.text
    return r.json()

def version(c,d):
    return post(c,'/resume-documents/'+d['document_id']+'/versions',dict(document=d['document'],expected_revision=d['revision'],name='普通版',pdf_base64=PDF,idempotency_key='version'))

def submit(c,o,resume,key='submit'):
    return c.post('/api/opportunities/'+o['id']+'/submitted',json=dict(expected_revision=o['revision'],idempotency_key=key,resume=resume))

def test_isolation_profile_and_explicit_versions(tmp_path):
    c,s=client_at(tmp_path);a=opportunity(c,'A');b=opportunity(c,'B')
    assert c.get('/api/resume-documents').json()['documents']==[]
    assert c.get('/api/opportunities/'+a['id']+'/resume').json()['document'] is None
    da=start(c,a);db=start(c,b);da=save(c,da,'A姓名');db=save(c,db,'B姓名')
    catalogue=c.get('/api/resume-documents').json()['documents']
    assert {x['document_id'] for x in catalogue}=={da['document_id'],db['document_id']}
    assert all('document' not in x and x['company']=='虚构公司' for x in catalogue)
    p=post(c,'/profile/basics',dict(basics=dict(name='基础新姓名',phone='',email=''),expected_revision=0))
    assert c.get('/api/resume-documents/'+da['document_id']).json()==da
    assert c.get('/api/resume-documents/'+db['document_id']).json()==db
    with s.connect(False) as con:
        assert con.execute("SELECT count(*) FROM records WHERE kind='editor_version'").fetchone()[0]==0
        assert con.execute('SELECT count(*) FROM revisions WHERE id=?',(da['document_id'],)).fetchone()[0]==0
        assert con.execute("SELECT count(*) FROM current WHERE id='editor-main'").fetchone()[0]==0
    refreshed=post(c,'/resume-documents/'+da['document_id']+'/select-facts',dict(expected_revision=da['revision'],include_profile=True,profile_revision=p['revision'],selections=[],idempotency_key='refresh'))
    assert refreshed['document']['profile']['name']=='基础新姓名'
    assert c.get('/api/resume-documents/'+db['document_id']).json()==db
    v=version(c,refreshed);assert v['version_kind']=='ordinary' and v['document_id']==da['document_id']
    assert c.put('/api/editor',json=dict(document=da['document'],expected_revision=0)).status_code==409
    assert c.post('/api/opportunities/'+a['id']+'/resume/start',json=dict(expected_opportunity_revision=a['revision'],idempotency_key='other',source={'kind':'blank'})).status_code==409


def test_draft_submit_freezes_greeting_and_none_needs_no_material(tmp_path):
    c,s=client_at(tmp_path);o=opportunity(c,'A');d=save(c,start(c,o),'已投递姓名')
    o=post(c,'/opportunities/'+o['id']+'/greeting',dict(content='投递时 Greeting',expected_revision=o['revision'],idempotency_key='greeting'))
    body=dict(mode='draft',document_id=d['document_id'],expected_document_revision=d['revision'],document=d['document'],pdf_base64=PDF)
    r=submit(c,o,body);assert r.status_code==200,r.text
    result=r.json();event=result['submission'];v=result['submission_version']
    assert v['version_kind']=='submission' and event['version_id']==v['id']
    assert event['submitted_on']==result['opportunity']['phase_changed_on']
    assert result['opportunity']['phase']=='submitted'
    assert submit(c,o,body).json()==result
    assert submit(c,o,body,'different').status_code==409
    post(c,'/opportunities/'+o['id']+'/greeting',dict(content='投递后当前 Greeting',expected_revision=result['opportunity']['revision'],idempotency_key='later'))
    save(c,d,'投递后姓名')
    state=c.get('/api/state').json();assert state['applications'][0]==event
    assert event['submitted_greeting_snapshot']=={'state':'captured','content':'投递时 Greeting'}
    assert c.delete('/api/resume-documents/'+d['document_id']+'/versions/'+v['id']).status_code==409
    other=opportunity(c,'无简历');none=submit(c,other,{'mode':'none'});assert none.status_code==200,none.text
    no=none.json()['submission'];assert no['version_id'] is None and no['artifact_id'] is None and no['resume_snapshot'] is None
    assert c.get('/api/opportunities/'+other['id']+'/resume').json()['document'] is None
    assert no['submitted_greeting_snapshot']=={'state':'not_used'}
    with s.connect(False) as con:
        assert con.execute("SELECT count(*) FROM records WHERE kind='editor_version'").fetchone()[0]==1


def test_copy_old_bytes_delete_source_and_concurrent_unique(tmp_path):
    c,s=client_at(tmp_path);a=opportunity(c,'来源');d=save(c,start(c,a),'旧版姓名');v=version(c,d)
    b=opportunity(c,'投递旧版');raw=c.get('/api/artifacts/'+v['artifact_id']).content
    a_meta=next(x for x in s.state()['artifacts'] if x['id']==v['artifact_id'])
    req=dict(mode='version',source_version_id=v['id'],source_document_hash=digest(v['document']),source_artifact_hash=a_meta['sha256'])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda i:submit(c,b,req,'parallel-'+str(i)),range(4)))
    assert sorted(r.status_code for r in results)==[200,409,409,409]
    result=next(r.json() for r in results if r.status_code==200);sent=result['submission_version']
    assert sent['id']!=v['id'] and sent['artifact_id']!=v['artifact_id']
    assert c.delete('/api/resume-documents/'+d['document_id']+'/versions/'+v['id']).status_code==200
    assert c.get('/api/artifacts/'+sent['artifact_id']).content==raw
    assert result['resume_document']['opportunity_id']==b['id']
    with s.connect(False) as con:
        assert con.execute('SELECT count(*) FROM applications').fetchone()[0]==1


def test_invalid_sources_cross_owner_stale_and_old_bypass(tmp_path):
    c,s=client_at(tmp_path);a=opportunity(c,'A');b=opportunity(c,'B');d=start(c,a)
    bad=c.post('/api/opportunities/'+b['id']+'/resume/start',json=dict(expected_opportunity_revision=b['revision'],idempotency_key='import',source={'kind':'structured_json','document':d['document']}))
    assert bad.status_code==422
    req=dict(mode='draft',document_id=d['document_id'],expected_document_revision=d['revision'],document=d['document'],pdf_base64=PDF)
    assert submit(c,b,req).status_code in (409,422)
    save(c,d,'changed');assert submit(c,a,req).status_code==409
    assert s.state()['applications']==[]
    with s.connect(False) as con:assert con.execute("SELECT count(*) FROM records WHERE kind='editor_version'").fetchone()[0]==0


def test_same_key_replay_none_existing_document_and_business_day(tmp_path, monkeypatch):
    from workbench import opportunity as op
    c,s=client_at(tmp_path);o=opportunity(c,'重放');d=save(c,start(c,o),'保留工作稿')
    o=post(c,'/opportunities/'+o['id']+'/greeting',dict(content='',expected_revision=o['revision'],idempotency_key='empty'))
    monkeypatch.setattr(op,'business_day',lambda timestamp:'2026-09-17')
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses=list(pool.map(lambda _:submit(c,o,{'mode':'none'},'one-key'),range(3)))
    assert all(r.status_code==200 for r in responses)
    assert all(r.json()==responses[0].json() for r in responses)
    event=responses[0].json()['submission']
    monkeypatch.setattr(op,'business_day',lambda timestamp:'2026-09-18')
    assert submit(c,o,{'mode':'none'},'one-key').json()==responses[0].json()
    assert event['submitted_greeting_snapshot']==dict(state='captured',content='')
    assert c.get('/api/resume-documents/'+d['document_id']).json()==d
    assert not s.state()['artifacts'] and len(s.state()['applications'])==1
    assert submit(c,o,{'mode':'version','source_version_id':'other'},'one-key').status_code==409


def test_start_and_end_races_are_serialized(tmp_path):
    c,s=client_at(tmp_path);o=opportunity(c,'并发创建')
    with ThreadPoolExecutor(max_workers=2) as pool:
        docs=list(pool.map(lambda _:start(c,o),range(2)))
    assert docs[0]==docs[1]
    def action(which):
        if which=='submit':return submit(c,o,{'mode':'none'})
        return c.post('/api/opportunities/'+o['id']+'/end',json=dict(result='withdrawn',expected_revision=o['revision'],idempotency_key='end'))
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(action,['submit','end']))
    assert sorted(r.status_code for r in results)==[200,409]
    current=c.get('/api/opportunities/'+o['id']).json()
    assert (current['phase']=='submitted') != (current['result']=='withdrawn')
