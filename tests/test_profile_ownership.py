from batch_c_helpers import editor_client
from fastapi.testclient import TestClient
from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider

H={'X-Career-Request':'1'}
def post(c,path,b):
 if path=='/jobs':b=dict(b,idempotency_key=b.get('idempotency_key','fixture-job'))
 return c.post(c.editor_path+path[len('/editor'):] if path.startswith('/editor') else '/api'+path,json=b,headers=H)

def test_explicit_organization_archives_old_text_and_pending_is_not_context(tmp_path):
 c=editor_client(Store(tmp_path,TestProvider()))
 old=post(c,'/profile',dict(content='旧混合文本：林澄；接受出差；审批经历',expected_revision=0)).json()
 basics=dict(name='林澄',email='test@example.invalid',phone='')
 assert post(c,'/profile/basics',dict(basics=basics,expected_revision=old['revision'])).status_code==409
 b=dict(expected_revision=old['revision'],basics=basics,confirmed=True,idempotency_key='organize',entries=[dict(title='出差限制',content='不接受出差哨兵',entry_type='constraint')])
 assert post(c,'/profile/organize',dict(b,confirmed=False)).status_code==422
 r=post(c,'/profile/organize',b);assert r.status_code==200,r.text
 assert post(c,'/profile/organize',b).json()==r.json()
 p=c.get('/api/state').json()['profile']
 assert p['mode']=='structured' and p['basics']==basics
 assert '接受出差' not in p['content']
 knowledge=c.get('/api/knowledge').json()
 assert knowledge['sources'][0]['content']==old['content']
 assert knowledge['sources'][0]['origin']['revision']==old['revision']
 candidate=knowledge['candidates'][0];assert candidate['status']=='pending'
 j=post(c,'/jobs',dict(company='虚构甲',title='产品',jd='JD',idempotency_key='profile-fixture-job')).json()
 before=post(c,'/analysis',dict(job_id=j['id'],kind='job',idempotency_key='before')).json()
 assert '不接受出差哨兵' not in str(before['payload']) and '旧混合文本' not in str(before['payload'])
 post(c,'/knowledge/candidates/'+candidate['id']+'/resolve',dict(decision='confirm',expected_revision=candidate['revision'],idempotency_key='confirm'))
 after=post(c,'/analysis',dict(job_id=j['id'],kind='job',idempotency_key='after')).json()
 assert '不接受出差哨兵' in str(after['payload']) and '旧混合文本' not in str(after['payload'])
 assert post(c,'/profile',dict(content='重新混入目标',expected_revision=p['revision'])).status_code==422
 assert post(c,'/profile/basics',dict(basics=basics,expected_revision=0)).status_code==409

def test_basic_profile_explicit_resume_selection_and_provenance(tmp_path):
 c=editor_client(Store(tmp_path,TestProvider()))
 p=post(c,'/profile/basics',dict(basics=dict(name='虚构姓名',phone='虚构电话',email='a@example.invalid'),expected_revision=0))
 assert p.status_code==200,p.text
 p=p.json()
 b=dict(include_profile=True,profile_revision=p['revision'],selections=[],expected_revision=0,idempotency_key='include')
 d=post(c,'/editor/select-facts',b);assert d.status_code==200,d.text
 assert d.json()['document']['profile']['name']=='虚构姓名'
 assert d.json()['document']['meta']['source_refs'][0]['source_kind']=='profile'
 assert len(c.get('/api/knowledge').json()['entries'])==0


def test_extended_contacts_roundtrip_resume_refresh_and_old_client_preserves_fields(tmp_path):
 c=editor_client(Store(tmp_path,TestProvider()))
 basics=dict(name='虚构姓名',phone='13800000000',email='a@example.test',wechat='demo_wechat',github='https://github.com/example',links=[dict(label='作品集',url='https://example.test/work')])
 p=post(c,'/profile/basics',dict(basics=basics,expected_revision=0))
 assert p.status_code==200,p.text
 p=p.json();assert p['basics']==basics
 b=dict(include_profile=True,profile_revision=p['revision'],selections=[],expected_revision=0,idempotency_key='extended')
 d=post(c,'/editor/select-facts',b).json()
 contacts=d['document']['profile']['contacts']
 assert next(x for x in contacts if x['id']=='contact-wechat')['content']=='微信：demo_wechat'
 assert any(x['href']==basics['github'] for x in contacts)
 assert any(x['href']=='https://example.test/work' for x in contacts)
 # Older clients editing their three fields cannot erase newly supported contacts.
 p=post(c,'/profile/basics',dict(basics=dict(name='新姓名',phone=basics['phone'],email=basics['email']),expected_revision=p['revision'])).json()
 assert p['basics']['wechat']=='demo_wechat' and p['basics']['links']==basics['links']
 refreshed=post(c,'/editor/select-facts',dict(b,profile_revision=p['revision'],expected_revision=d['revision'],idempotency_key='refresh'))
 assert refreshed.status_code==200,refreshed.text
 assert refreshed.json()['document']['profile']['name']=='新姓名'
 assert len([r for r in refreshed.json()['document']['meta']['source_refs'] if r['source_kind']=='profile'])==1
 assert post(c,'/profile/basics',dict(basics=dict(basics,links=[dict(label='坏链接',url='javascript:alert(1)')]),expected_revision=p['revision'])).status_code==422
