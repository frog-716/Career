import json
from uuid import uuid4
from fastapi.testclient import TestClient
from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


def test_latest_confirmed_selection_in_actual_payload_and_staleness(tmp_path):
    store=Store(tmp_path/'data',TestProvider()); c=TestClient(create_app(store)); h={'X-Career-Request':'1'}
    calls=[];original=store.provider.complete
    store.provider.complete=lambda payload:(calls.append(payload) or original(payload))
    def post(p,b):
        r=c.post('/api'+p,json=b,headers=h)
        if p == '/analysis' and r.status_code == 409 and r.json().get('status') == 'context_confirmation_required':
            preview=r.json()
            r=c.post('/api'+p,json={**b,'prepared_id':preview['prepared_id'],
                                    'payload_hash':preview['payload_hash'],'confirm_outbound':True},headers=h)
        assert r.status_code==200,r.text;return r.json()
    job=post('/jobs',dict(company='虚构甲',title='分析',jd='虚构JD',idempotency_key='job'))
    def entry(title,content,kind='project',scope_type='personal',scope_id=''):
        # Synthetic confirmed legacy fact, kept to verify old Context selection.
        source_id=str(uuid4());entry_id=str(uuid4())
        with store.connect() as connection:
            store._record(connection,'knowledge_source',dict(
                id=source_id,title=title,content=content,source_type='text',locator='',
                scope_type=scope_type,scope_id=scope_id,created_at='2026-01-01T00:00:00Z'))
            return store._save(connection,'wiki_entry',dict(
                id=entry_id,title=title,content=content,entry_type=kind,
                scope_type=scope_type,scope_id=scope_id,source_ids=[source_id],
                status='active',verification='user_asserted',
                created_at='2026-01-01T00:00:00Z'),0)
    goal=entry('目标','必须保留的约束','constraint')
    project=entry('项目甲','旧事实XYZ')
    private=entry('别的机会','跨机会机密',scope_type='job',scope_id=post('/jobs',dict(company='虚构乙',title='经理',jd='B',idempotency_key='job2'))['id'])
    packet=post('/context',dict(job_id=job['id'],kind='job',wiki_ids=[project['id']]))
    assert {x['id'] for x in packet['sources']}=={goal['id'],project['id'],job['opportunity_id'],c.get('/api/opportunities/'+job['id']).json()['company_id']}
    post('/knowledge/entries/'+project['id'],{**project,'content':'最新事实ABC','expected_revision':project['revision']})
    stale=c.post('/api/analysis',json=dict(job_id=job['id'],kind='job',wiki_ids=[project['id']],expected_epoch=packet['epoch'],idempotency_key='stale'),headers=h)
    assert stale.status_code==409
    packet=post('/context',dict(job_id=job['id'],kind='job',wiki_ids=[project['id']]))
    result=post('/analysis',dict(job_id=job['id'],kind='job',wiki_ids=[project['id']],expected_epoch=packet['epoch'],idempotency_key='actual'))
    payload=json.dumps(calls[-1],ensure_ascii=False)
    assert '最新事实ABC' in payload and '旧事实XYZ' not in payload and '跨机会机密' not in payload
    assert c.post('/api/context',json=dict(job_id=job['id'],kind='job',wiki_ids=[private['id']]),headers=h).status_code==422
    assert c.post('/api/analysis',json=dict(job_id=job['id'],kind='job',wiki_ids=[],expected_epoch=packet['epoch'],idempotency_key='actual'),headers=h).status_code==409
    post('/knowledge/entries/'+project['id'],{**project,'content':'已撤回','status':'withdrawn','expected_revision':2})
    assert c.get('/api/state').json()['runs'][0]['status']=='stale'
    assert c.post('/api/context',json=dict(job_id=job['id'],kind='job',wiki_ids=[project['id']]),headers=h).status_code==422
