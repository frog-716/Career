import base64
from copy import deepcopy
from fastapi.testclient import TestClient
from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider

H={'X-Career-Request':'1'}
def post(c,path,b):return c.post('/api'+path,json=b,headers=H)
def wiki(c,scope='personal',sid='',text='可信审批经验'):
 s=post(c,'/knowledge/sources',dict(title='测试来源',content=text,source_type='text',scope_type=scope,scope_id=sid,idempotency_key='s-'+text)).json()
 x=post(c,'/knowledge/candidates',dict(title='审批项目',content=text,entry_type='project',source_ids=[s['id']],scope_type=scope,scope_id=sid,idempotency_key='c-'+text)).json()
 x=post(c,'/knowledge/candidates/'+x['id']+'/resolve',dict(expected_revision=x['revision'],decision='confirm',idempotency_key='confirm-'+text)).json()
 return next(e for e in c.get('/api/knowledge').json()['entries'] if e['id']==x['entry_id'])

def test_selected_fact_provenance_freezes_through_version_and_submission(tmp_path):
 c=TestClient(create_app(Store(tmp_path,TestProvider())))
 e=wiki(c)
 j=post(c,'/jobs',dict(company='虚构甲',title='产品',jd='招聘条件')).json()
 body=dict(expected_revision=0,idempotency_key='select',job_id=j['id'],selections=[dict(id=e['id'],revision=e['revision'],section_type='projects')],include_profile=False)
 r=post(c,'/editor/select-facts',body);assert r.status_code==200,r.text
 d=r.json();ref=d['document']['meta']['source_refs'][0]
 assert ref['source_id']==e['id'] and ref['revision']==e['revision']
 assert post(c,'/editor/select-facts',body).json()==d
 assert post(c,'/editor/select-facts',dict(body,idempotency_key='duplicate',expected_revision=d['revision'])).status_code==409
 v=post(c,'/editor/versions',dict(document=d['document'],expected_revision=d['revision'],name='事实版',pdf_base64=base64.b64encode(b'%PDF-1.7\nfixture\n%%EOF').decode(),idempotency_key='v')).json()
 post(c,'/domain/resume-uses',dict(version_id=v['id'],scope_type='job',scope_id=j['id'],idempotency_key='use'))
 a=post(c,'/applications',dict(job_id=j['id'],version_id=v['id'],artifact_id=v['artifact_id'],applied_at='2026-09-15T12:00:00+08:00',channel='虚构',idempotency_key='apply')).json()
 post(c,'/knowledge/entries/'+e['id'],dict(e,content='更正后的审批事实',expected_revision=e['revision']))
 assert c.get('/api/editor/sources').json()['sources'][0]['status']=='updated'
 assert c.get('/api/editor/versions/'+v['id']).json()['document']==d['document']
 assert c.get('/api/state').json()['applications']==[a]
 edited=deepcopy(d['document']);edited['sections'][0]['items'][0]['title']='自由表达'
 assert c.put('/api/editor',json=dict(document=edited,expected_revision=d['revision']),headers=H).status_code==200
 forged=deepcopy(edited);forged['meta']['source_refs'][0]['revision']=999
 assert c.put('/api/editor',json=dict(document=forged,expected_revision=d['revision']+1),headers=H).status_code==409
 assert c.get('/api/editor').json()['document']['meta']['source_refs']==[ref]

def test_selection_scope_and_source_revision_are_enforced(tmp_path):
 c=TestClient(create_app(Store(tmp_path,TestProvider())))
 j=post(c,'/jobs',dict(company='甲',title='岗位',jd='JD')).json()
 other=wiki(c,'job',j['id'],'仅岗位甲')
 e=wiki(c)
 r=post(c,'/journey/episodes',dict(company='任职甲',role='研发')).json()
 private=wiki(c,'episode',r['id'],'私密任职哨兵')
 materials=c.get('/api/editor/materials').json()['entries']
 assert [x['id'] for x in materials]==[e['id']]
 b=dict(expected_revision=0,idempotency_key='bad',selections=[dict(id=other['id'],revision=1,section_type='skills')])
 assert post(c,'/editor/select-facts',b).status_code==422
 assert post(c,'/editor/select-facts',dict(b,selections=[dict(id=private['id'],revision=1,section_type='skills')])).status_code==422
 assert post(c,'/editor/select-facts',dict(b,selections=[dict(id=e['id'],revision=99,section_type='skills')])).status_code==409
 assert c.get('/api/editor').json()['revision']==0


def test_removed_expression_can_be_reselected_without_rewriting_provenance(tmp_path):
 c=TestClient(create_app(Store(tmp_path,TestProvider())))
 e=wiki(c)
 body=dict(expected_revision=0,idempotency_key='first-selection',selections=[dict(id=e['id'],revision=1,section_type='projects')],include_profile=False)
 d=post(c,'/editor/select-facts',body).json()
 removed=deepcopy(d['document']);removed['sections'][0]['items']=[]
 saved=c.put('/api/editor',json=dict(document=removed,expected_revision=d['revision']),headers=H).json()
 r=post(c,'/editor/select-facts',dict(body,expected_revision=saved['revision'],idempotency_key='reselect'))
 assert r.status_code==200,r.text
 refs=c.get('/api/editor/sources').json()['sources']
 assert [x['status'] for x in refs]==['removed','current']
 assert refs[0]['item_id']!=refs[1]['item_id'] and refs[0]['hash']==refs[1]['hash']


def test_record_candidate_confirmation_controls_real_context_payload(tmp_path):
 c=TestClient(create_app(Store(tmp_path,TestProvider())))
 j=post(c,'/jobs',dict(company='虚构甲',title='运营',jd='当前JD')).json()
 n=post(c,'/journey/notes',dict(scope_type='job',scope_id=j['id'],kind='research',title='研究原件',content='内部完整原话哨兵',idempotency_key='research')).json()
 post(c,'/journey/notes/'+n['id']+'/correct',dict(expected_revision=0,title='更正',content='仅限任务的纠正原话哨兵',idempotency_key='correct'))
 cand=post(c,'/journey/notes/'+n['id']+'/candidate',dict(expected_revision=1,title='本人研究能力',content='可以复用的查证经验',entry_type='capability',scope_type='personal',scope_id='',promote_to_personal=True,idempotency_key='candidate')).json()
 pending=post(c,'/context',dict(job_id=j['id'],kind='job',wiki_ids=[])).json()
 assert '查证经验' not in str(pending)
 confirmed=post(c,'/knowledge/candidates/'+cand['id']+'/resolve',dict(expected_revision=1,decision='confirm',idempotency_key='confirm')).json()
 packet=post(c,'/context',dict(job_id=j['id'],kind='job',wiki_ids=[confirmed['entry_id']])).json()
 run=post(c,'/analysis',dict(job_id=j['id'],kind='job',wiki_ids=[confirmed['entry_id']],expected_epoch=packet['epoch'],idempotency_key='run')).json()
 assert run['status']=='succeeded'
 payload=str(c.get('/api/state').json()['runs'][0]['payload'])
 assert '可以复用的查证经验' in payload
 assert '内部完整原话哨兵' not in payload and '仅限任务的纠正原话哨兵' not in payload
