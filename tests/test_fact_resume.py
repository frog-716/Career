import json
from uuid import uuid4
from batch_c_helpers import editor_client
from copy import deepcopy
from fastapi.testclient import TestClient
from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider

H={'X-Career-Request':'1'}
def make_client(tmp_path):
 store=Store(tmp_path,TestProvider())
 c=editor_client(store)
 c.fixture_store=store
 return c
def post(c,path,b):
 if path=='/jobs':b=dict(b,idempotency_key=b.get('idempotency_key','fixture-job'))
 return c.post(c.editor_path+path[len('/editor'):] if path.startswith('/editor') else '/api'+path,json=b,headers=H)
def wiki(c,scope='personal',sid='',text='可信审批经验'):
 # Plant a confirmed synthetic pre-D1 fact; the old intake route is retired.
 source_id=str(uuid4());entry_id=str(uuid4())
 with c.fixture_store.connect() as connection:
  c.fixture_store._record(connection,'knowledge_source',dict(
   id=source_id,title='测试来源',content=text,source_type='text',locator='',
   scope_type=scope,scope_id=sid,created_at='2026-01-01T00:00:00Z'))
  entry=c.fixture_store._save(connection,'wiki_entry',dict(
   id=entry_id,title='审批项目',content=text,entry_type='project',
   source_ids=[source_id],scope_type=scope,scope_id=sid,status='active',
   verification='user_asserted',created_at='2026-01-01T00:00:00Z'),0)
 return entry

def test_selected_fact_provenance_freezes_through_version_and_submission(tmp_path):
 c=make_client(tmp_path)
 e=wiki(c)
 j=post(c,'/jobs',dict(company='虚构甲',title='产品',jd='招聘条件')).json()
 body=dict(expected_revision=0,idempotency_key='select',selections=[dict(id=e['id'],revision=e['revision'],section_type='projects')],include_profile=False)
 r=post(c,'/editor/select-facts',body);assert r.status_code==200,r.text
 d=r.json();ref=d['document']['meta']['source_refs'][0]
 assert ref['source_id']==e['id'] and ref['revision']==e['revision']
 assert post(c,'/editor/select-facts',body).json()==d
 assert post(c,'/editor/select-facts',dict(body,idempotency_key='duplicate',expected_revision=d['revision'])).status_code==409
 v=post(c,'/editor/versions',dict(expected_revision=d['revision'],name='事实版',idempotency_key='v')).json()
 post(c,'/domain/resume-uses',dict(version_id=v['id'],scope_type='job',scope_id=j['id'],idempotency_key='use'))
 a=post(c,'/opportunities/'+c.editor_op['id']+'/submitted',dict(expected_revision=c.editor_op['revision'],idempotency_key='apply',resume=dict(mode='draft',document_id=c.editor_id,expected_document_revision=d['revision']))).json()['submission']
 post(c,'/knowledge/entries/'+e['id'],dict(e,content='更正后的审批事实',expected_revision=e['revision']))
 assert c.get(c.editor_path+'/sources').json()['sources'][0]['status']=='updated'
 assert c.get(c.editor_path+'/versions/'+v['id']).json()['document']==d['document']
 assert c.get('/api/state').json()['applications']==[a]
 edited=deepcopy(d['document']);edited['sections'][0]['items'][0]['title']='自由表达'
 assert c.put(c.editor_path,json=dict(document=edited,expected_revision=d['revision']),headers=H).status_code==200
 forged=deepcopy(edited);forged['meta']['source_refs'][0]['revision']=999
 assert c.put(c.editor_path,json=dict(document=forged,expected_revision=d['revision']+1),headers=H).status_code==409
 assert c.get(c.editor_path).json()['document']['meta']['source_refs']==[ref]

def test_selection_scope_and_source_revision_are_enforced(tmp_path):
 c=make_client(tmp_path)
 j=post(c,'/jobs',dict(company='甲',title='岗位',jd='JD')).json()
 other=wiki(c,'job',j['id'],'仅岗位甲')
 e=wiki(c)
 r=post(c,'/journey/episodes',dict(company='任职甲',role='研发')).json()
 private=wiki(c,'episode',r['id'],'私密任职哨兵')
 materials=c.get(c.editor_path+'/materials').json()['entries']
 assert [x['id'] for x in materials]==[e['id']]
 b=dict(expected_revision=0,idempotency_key='bad',selections=[dict(id=other['id'],revision=1,section_type='skills')])
 assert post(c,'/editor/select-facts',b).status_code==422
 assert post(c,'/editor/select-facts',dict(b,selections=[dict(id=private['id'],revision=1,section_type='skills')])).status_code==422
 assert post(c,'/editor/select-facts',dict(b,selections=[dict(id=e['id'],revision=99,section_type='skills')])).status_code==409
 assert c.get(c.editor_path).json()['revision']==0


def test_removed_expression_can_be_reselected_without_rewriting_provenance(tmp_path):
 c=make_client(tmp_path)
 e=wiki(c)
 body=dict(expected_revision=0,idempotency_key='first-selection',selections=[dict(id=e['id'],revision=1,section_type='projects')],include_profile=False)
 d=post(c,'/editor/select-facts',body).json()
 removed=deepcopy(d['document']);removed['sections'][0]['items']=[]
 saved=c.put(c.editor_path,json=dict(document=removed,expected_revision=d['revision']),headers=H).json()
 r=post(c,'/editor/select-facts',dict(body,expected_revision=saved['revision'],idempotency_key='reselect'))
 assert r.status_code==200,r.text
 refs=c.get(c.editor_path+'/sources').json()['sources']
 assert [x['status'] for x in refs]==['removed','current']
 assert refs[0]['item_id']!=refs[1]['item_id'] and refs[0]['hash']==refs[1]['hash']


def test_historical_candidate_not_in_context_until_confirmed_fact_exists(tmp_path):
 c=make_client(tmp_path)
 j=post(c,'/jobs',dict(company='虚构甲',title='运营',jd='当前JD')).json()
 n=post(c,'/journey/notes',dict(scope_type='job',scope_id=j['id'],kind='research',title='研究原件',content='内部完整原话哨兵',idempotency_key='research')).json()
 post(c,'/journey/notes/'+n['id']+'/correct',dict(expected_revision=0,title='更正',content='仅限任务的纠正原话哨兵',idempotency_key='correct'))
 with c.fixture_store.connect() as connection:
  c.fixture_store._save(connection,'knowledge_candidate',dict(
   id='historical-pending-research',status='pending',entry_id=None,
   source_ids=[],entry_type='capability',title='本人研究能力',
   content='可以复用的查证经验',scope_type='personal',scope_id='',
   created_at='2026-01-01T00:00:00Z'),0)
 pending=post(c,'/context',dict(job_id=j['id'],kind='job',wiki_ids=[])).json()
 assert '查证经验' not in str(pending)
 confirmed=wiki(c,text='可以复用的查证经验')
 packet=post(c,'/context',dict(job_id=j['id'],kind='job',wiki_ids=[confirmed['id']])).json()
 prepared=post(c,'/analysis',dict(job_id=j['id'],kind='job',wiki_ids=[confirmed['id']],expected_epoch=packet['epoch'],idempotency_key='run')).json()
 run=post(c,'/analysis',dict(job_id=j['id'],kind='job',wiki_ids=[confirmed['id']],expected_epoch=packet['epoch'],idempotency_key='run',prepared_id=prepared['prepared_id'],payload_hash=prepared['payload_hash'],confirm_outbound=True)).json()
 assert run['status']=='succeeded'
 saved_run=c.get('/api/state').json()['runs'][0]
 assert 'payload' not in saved_run
 assert saved_run['payload_meta']['payload_hash']
 assert '内部完整原话哨兵' not in json.dumps(saved_run['payload_meta'],ensure_ascii=False)
 assert '仅限任务的纠正原话哨兵' not in json.dumps(saved_run['payload_meta'],ensure_ascii=False)
