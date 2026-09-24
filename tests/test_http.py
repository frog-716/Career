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

def test_delete_feedback_removes_only_selected_record_and_its_screenshot(tmp_path):
    store=Store(tmp_path,TestProvider())
    client=TestClient(create_app(store))
    headers={'X-Career-Request':'1'}
    first=client.post('/api/feedback',json={
        'text':'虚构反馈一',
        'current_page':'feedback',
        'screenshot':{
            'media_type':'image/png',
            'data_base64':'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
        },
    },headers=headers).json()
    second=client.post('/api/feedback',json={'text':'虚构反馈二','current_page':'feedback'},headers=headers).json()
    client.post(f"/api/feedback/{first['id']}/notes",json={'text':'虚构补充'},headers=headers)
    with store.connect(False) as connection:
        artifact=store._get(connection,first['screenshot_id'],'artifact',True)
    artifact_path=tmp_path/artifact['path']
    assert artifact_path.is_file()
    assert client.get(f"/api/artifacts/{first['screenshot_id']}").status_code==200

    refused=client.request('DELETE',f"/api/feedback/{first['id']}",json={},headers=headers)
    assert refused.status_code==409
    assert artifact_path.is_file()
    assert len(client.get('/api/state?view=feedback').json()['feedback'])==2

    deleted=client.request('DELETE',f"/api/feedback/{first['id']}",json={'confirm':True},headers=headers)

    assert deleted.status_code==200
    assert deleted.json()=={
        'deleted':first['id'],
        'screenshot_retained':False,
        'screenshot_cleanup_pending':False,
    }
    remaining=client.get('/api/state?view=feedback').json()
    assert [item['id'] for item in remaining['feedback']]==[second['id']]
    assert not artifact_path.exists()
    assert client.get(f"/api/artifacts/{first['screenshot_id']}").status_code==404
    with store.connect(False) as connection:
        assert connection.execute("SELECT 1 FROM records WHERE id=?",(first['screenshot_id'],)).fetchone() is None
    exported=client.get('/api/feedback/export?format=json').json()['feedback']
    assert [item['id'] for item in exported]==[second['id']]
    assert client.request('DELETE',f"/api/feedback/{first['id']}",json={'confirm':True},headers=headers).status_code==404

def test_unconfigured_real_mode_still_supports_manual_chain(tmp_path,monkeypatch):
    for name in ('CAREER_AI_PROVIDER','CAREER_AI_MODEL','CAREER_AI_API_KEY','OPENAI_API_KEY'):
        monkeypatch.delenv(name,raising=False)
    client=TestClient(create_app(Store(tmp_path)))
    headers={'X-Career-Request':'1'}
    assert client.get('/api/state').json()['diagnostics']['provider']['configured'] is False
    assert client.post('/api/profile',json={'content':F['candidate']['experience']['revision2'],'expected_revision':0},headers=headers).status_code==200
    j=client.post('/api/jobs',json=dict({k:F['job'][k] for k in ('company','title','jd')},idempotency_key='create'),headers=headers).json()
    seed={'job_id':j['id'],'kind':'job','idempotency_key':'fixture-unconfigured'}
    response=client.post('/api/analysis',json=seed,headers=headers)
    assert response.status_code==503
    assert '未配置' in response.json()['detail']
    assert client.get('/api/state').json()['runs']==[]
