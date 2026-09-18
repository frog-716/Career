from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


def test_editor_route_guard_and_conflict_preserve_current(tmp_path):
    client = TestClient(create_app(Store(tmp_path, TestProvider())))
    from batch_c_helpers import bind_editor
    bind_editor(client,client.app.state.store)
    draft = client.get(client.editor_path).json()
    draft['document']['profile']['name'] = '虚构候选人甲'
    body = {'document': draft['document'], 'expected_revision': draft['revision']}
    assert client.put(client.editor_path, json=body).status_code == 403
    headers = {'X-Career-Request': '1'}
    assert client.put(client.editor_path, json=body, headers={
        **headers, 'Origin': 'https://untrusted.example'
    }).status_code == 403
    saved = client.put(client.editor_path, json=body, headers=headers)
    assert saved.status_code == 200
    body['document']['profile']['name'] = '过期窗口候选人乙'
    assert client.put(client.editor_path, json=body, headers=headers).status_code == 409
    assert client.get(client.editor_path).json()['document']['profile']['name'] == '虚构候选人甲'
    # A structural editor draft must never leak into the legacy fact/profile store.
    state = client.get('/api/state').json()
    assert state['profile']['content'] == ''
    assert state['resumes'] == []
    assert state['versions'] == []
