"""HTTP contracts fixed for Batch B: one writable owner, no inferred phase."""
from fastapi.testclient import TestClient
from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider
from batch_b_helpers import historical_application

HEADERS={'X-Career-Request':'1'}
def post(c,path,body):return c.post('/api'+path,json=body,headers=HEADERS)

def test_canonical_http_flow_and_frozen_history(tmp_path):
    s=Store(tmp_path/'data',TestProvider());c=TestClient(create_app(s))
    body=dict(company_name='虚构公司',title='工程师',jd='原始JD',idempotency_key='create')
    r=post(c,'/opportunities',body);assert r.status_code==200,r.text
    o=r.json();alias=o['id'].removeprefix('opportunity:')
    assert o['legacy_job_id'] is None
    resume=s.open_resume(alias);resume=s.save_resume(resume['id'],'冻结原文',0)
    v=s.save_version(resume['id'],resume['revision']);pdf=s.export_pdf(v['id'])
    event=historical_application(s,dict(job_id=alias,version_id=v['id'],artifact_id=pdf['id'],applied_at='2026-09-01T00:00:00Z',idempotency_key='historical'))
    edit=dict(jd='新JD',expected_revision=o['revision'],idempotency_key='edit')
    changed=post(c,'/opportunities/'+o['id'],edit);assert changed.status_code==200,changed.text
    assert changed.json()['phase_changed_on']==o['phase_changed_on']
    assert s.state()['applications']==[event]
    assert event['opportunity_snapshot']['job_posting']['jd']=='原始JD'
    assert c.get('/api/opportunities/'+alias).json()['id']==o['id']
    revision=changed.json()['revision']
    for payload in (dict(status='deleted'),dict(phase='offer'),dict(result='accepted')):
        before=s.db.read_bytes()
        response=post(c,'/jobs/'+alias,dict(payload,expected_revision=revision,idempotency_key='bypass'))
        assert response.status_code in (409,422)
        assert s.db.read_bytes()==before
    assert post(c,'/applications/'+event['id']+'/status',dict(status='interviewing')).status_code==409
    ended=post(c,'/opportunities/'+o['id']+'/end',dict(result='rejected',expected_revision=revision,idempotency_key='end'))
    assert ended.status_code==200,ended.text
    assert ended.json()['phase']=='resume'
    assert c.get('/api/opportunities?view=resume').json()==[]
    assert c.get('/api/opportunities?view=ended').json()==[ended.json()]
    assert Store(s.data_dir,TestProvider()).state()['applications']==[event]
