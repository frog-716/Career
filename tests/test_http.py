import json
from pathlib import Path
from fastapi.testclient import TestClient
from workbench.core import Store
from workbench.providers import TestProvider
from workbench.app import create_app
F=json.loads((Path(__file__).parents[1]/'fixtures/scenarios.json').read_text())

def test_http_security_and_feedback(tmp_path):
    client=TestClient(create_app(Store(tmp_path,TestProvider())))
    b={'content':F['candidate']['experience']['revision2'],'expected_revision':0}
    assert client.post('/api/profile',json=b).status_code==403
    assert client.post('/api/profile',json=b,headers={'X-Career-Request':'1','Origin':'https://malicious.example'}).status_code==403
    assert client.get('/api/state',headers={'Host':'malicious.example'}).status_code==403
    assert client.post('/api/profile',json=b,headers={'X-Career-Request':'1'}).status_code==200
    assert client.post('/api/profile',json=b,headers={'X-Career-Request':'1'}).status_code==409
    feedback={'text':F['workEpisode']['workItem'],'current_page':'profile'}
    assert client.post('/api/feedback',json=feedback,headers={'X-Career-Request':'1'}).status_code==200
    exported=client.get('/api/feedback/export?format=json').json()
    assert exported['feedback'][0]['text']==feedback['text']
    assert feedback['text'] in client.get('/api/feedback/export?format=md').text

def test_unconfigured_real_mode_still_supports_manual_chain(tmp_path,monkeypatch):
    for name in ('CAREER_AI_PROVIDER','CAREER_AI_MODEL','CAREER_AI_API_KEY','OPENAI_API_KEY'):
        monkeypatch.delenv(name,raising=False)
    client=TestClient(create_app(Store(tmp_path)))
    headers={'X-Career-Request':'1'}
    assert client.get('/api/state').json()['diagnostics']['provider']['configured'] is False
    assert client.post('/api/profile',json={'content':F['candidate']['experience']['revision2'],'expected_revision':0},headers=headers).status_code==200
    j=client.post('/api/jobs',json={k:F['job'][k] for k in ('company','title','jd')},headers=headers).json()
    response=client.post('/api/analysis',json={'job_id':j['id'],'kind':'job','idempotency_key':'fixture-unconfigured'},headers=headers)
    assert response.status_code==503
    assert '未配置' in response.json()['detail']
    assert client.get('/api/state').json()['runs'][0]['status']=='failed'
