import pytest
from fastapi.testclient import TestClient
from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


def client(tmp_path):
    return TestClient(create_app(Store(tmp_path/'data', TestProvider())))


def post(c,path,body):
    return c.post('/api/domain'+path,json=body,headers={'X-Career-Request':'1'})


def obj(c,kind,name,**kw):
    r=post(c,'/objects',dict(kind=kind,name=name,idempotency_key=name,**kw))
    assert r.status_code==200,r.text
    return r.json()


def test_org_parent_cannot_cycle_or_cross_company(tmp_path):
    c=client(tmp_path)
    a=obj(c,'company','虚构公司甲'); b=obj(c,'company','虚构公司乙')
    x=obj(c,'org_unit','部门',company_id=a['id']); y=obj(c,'org_unit','团队',company_id=a['id'],parent_id=x['id'])
    assert post(c,'/objects/'+x['id'],{**x,'parent_id':y['id'],'expected_revision':x['revision']}).status_code==422
    assert post(c,'/objects/'+y['id'],{**y,'company_id':b['id'],'expected_revision':y['revision']}).status_code==422
    assert post(c,'/objects/'+x['id'],{**x,'name':'改名','expected_revision':0}).status_code==409


def test_opportunity_assignment_is_canonical_cas_and_rejects_mixed_context(tmp_path):
    c=client(tmp_path)
    job=c.post('/api/jobs',json={'company':'虚构甲','title':'分析师','jd':'JD','idempotency_key':'job'},headers={'X-Career-Request':'1'}).json()
    a=obj(c,'company','虚构甲'); b=obj(c,'company','虚构乙')
    body=dict(company_id=b['id'],expected_revision=job['revision'],idempotency_key='assign')
    r=post(c,'/opportunities/'+job['id'],body); assert r.status_code==200,r.text
    assert r.json()['company_id']==b['id']
    assert post(c,'/opportunities/'+job['id'],body).json()==r.json()
    assert post(c,'/opportunities/'+job['id'],dict(body,idempotency_key='stale')).status_code==409
    assert post(c,'/opportunities/'+job['id'],dict(body,target_role_id='anything')).status_code==409
    assert c.get('/api/domain').json()['opportunities']==[]
    assert c.get('/api/state').json()['applications']==[]


def test_resume_reference_is_frozen_and_not_submission(tmp_path):
    c=client(tmp_path); s=c.app.state.store
    role=obj(c,'target_role','通用分析方向')
    # Synthetic immutable PDF metadata is sufficient here; renderer tests own PDF bytes.
    with s.connect() as db:
        s._record(db,'editor_version',{'id':'v1','name':'虚构简历','artifact_id':'pdf1','createdAt':'2026-01-01'})
        s._record(db,'artifact',{'id':'pdf1','sha256':'synthetic','version_id':'v1'})
    body={'version_id':'v1','scope_type':'role','scope_id':role['id'],'idempotency_key':'use1'}
    r=post(c,'/resume-uses',body);assert r.status_code==200,r.text
    first=r.json();assert post(c,'/resume-uses',body).json()==first
    assert post(c,'/resume-uses',{**body,'version_id':'v2'}).status_code==409
    assert first['artifact_id']=='pdf1' and first['scope_id']==role['id']
    assert c.get('/api/state').json()['applications']==[]
