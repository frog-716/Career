"""Submission uses the original structured version; legacy events stay readable."""
import base64
from batch_b_helpers import historical_application
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider

HEADERS = {'X-Career-Request': '1'}


def post(c, path, body):
    if path=='/editor/restore':body=dict(body,idempotency_key='restore-fixture')
    return c.post(c.editor_path+path[len('/editor'):] if path.startswith('/editor') else '/api'+path, json=body, headers=HEADERS)


def setup(tmp_path):
    s = Store(tmp_path / 'data', TestProvider())
    c = TestClient(create_app(s))
    j = post(c, '/jobs', dict(company='虚构甲', title='产品经理', jd='虚构招聘条件', idempotency_key='job1')).json()
    from batch_c_helpers import bind_editor
    bind_editor(c,s,c.get('/api/opportunities/'+j['id']).json())
    document = c.get(c.editor_path).json()['document']
    document['profile']['name'] = '冻结稿哨兵'
    saved = c.put(c.editor_path, json=dict(document=document, expected_revision=0), headers=HEADERS).json()
    v = post(c, '/editor/versions', dict(document=document, expected_revision=saved['revision'], name='正式版本一', pdf_base64=base64.b64encode(b'%PDF-1.7\nsynthetic\n%%EOF').decode(), idempotency_key='v1')).json()
    body = dict(job_id=j['id'], version_id=v['id'], artifact_id=v['artifact_id'], applied_at='2026-09-15T10:00:00+08:00', channel='招聘平台', status='applied', idempotency_key='submission-one')
    return c, s, j, v, body


def associate(c, j, v, key='use'):
    r = post(c, '/domain/resume-uses', dict(scope_type='job', scope_id=j['id'], version_id=v['id'], idempotency_key=key))
    assert r.status_code == 200, r.text


def test_structured_submission_freezes_version_job_pdf_restart_and_context(tmp_path):
    c, s, j, v, body = setup(tmp_path)
    associate(c, j, v)
    assert s.state()['applications'] == []
    historical_application(s, body)
    r = post(c, '/applications', body)
    assert r.status_code == 200, r.text
    event = r.json()
    assert event['version_kind'] == 'editor_version'
    assert event['channel'] == '招聘平台'
    assert event['resume_snapshot']['document'] == v['document']
    original_bytes = s.artifact(v['artifact_id'])[0].read_bytes()
    # Mutating current documents and restoring history must never mutate a submission.
    changed = deepcopy(v['document']); changed['profile']['name'] = '工作稿变更哨兵'
    assert c.put(c.editor_path, json=dict(document=changed, expected_revision=1), headers=HEADERS).status_code == 200
    assert post(c, '/editor/restore', dict(version_id=v['id'], expected_revision=2)).status_code == 200
    assert post(c, '/jobs/' + j['id'], dict(j, jd='新招聘条件', expected_revision=j['revision'], idempotency_key='edit')).status_code == 200
    s.save_profile('可信资料哨兵', 0)
    post(c, '/journey/notes', dict(scope_type='job', scope_id=j['id'], kind='interview', title='复盘', content='未确认面试哨兵', idempotency_key='note'))
    run = s.analyze(j['id'], 'job', idempotency_key='analysis')
    assert '未确认面试哨兵' not in str(run['payload'])
    assert '工作稿变更哨兵' not in str(run['payload'])
    assert '冻结稿哨兵' not in str(run['payload'])
    reopened = Store(s.data_dir, TestProvider())
    assert reopened.state()['applications'] == [event]
    assert reopened.artifact(v['artifact_id'])[0].read_bytes() == original_bytes
    assert event['job_snapshot']['jd'] == '虚构招聘条件'
    assert post(c, '/applications', body).json() == event
    assert reopened.state()['resumes'] == []  # no third bridge or legacy copy


def test_new_submission_is_explicitly_pending_without_partial_writes(tmp_path):
    c, s, j, v, body = setup(tmp_path)
    associate(c, j, v)
    before = s.db.read_bytes()
    for change in ({}, {'artifact_id': v['id']}, {'job_id': 'missing'}):
        response = post(c, '/applications', dict(body, **change))
        assert response.status_code == 409
        assert 'submission_action_pending' in response.text
    assert s.db.read_bytes() == before
    assert s.state()['applications'] == []


def test_submission_idempotency_concurrency_and_legacy_compatibility(tmp_path):
    c, s, j, v, body = setup(tmp_path)
    associate(c, j, v)
    historical_application(s, body)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: post(c, '/applications', body), range(4)))
    assert all(r.status_code == 200 for r in results)
    event = results[0].json()
    assert all(r.json() == event for r in results)
    for changes in ({'channel':'邮箱'}, {'status':'interviewing'}, {'applied_at':'2026-09-16T10:00:00+08:00'}):
        assert post(c, '/applications', dict(body, **changes)).status_code == 409
    assert post(c, '/applications/' + event['id'] + '/status', {'status':'interviewing'}).status_code == 409
    assert post(c, '/applications', body).status_code == 200  # retry original creation after status update
    assert len(s.state()['applications']) == 1
    # Same fixed version may be deliberately used for another opportunity.
    j2 = post(c, '/jobs', dict(company='虚构乙', title='产品', jd='JD二', idempotency_key='job2')).json()
    associate(c, j2, v, 'use2')
    assert post(c, '/applications', dict(body, job_id=j2['id'], idempotency_key='second')).status_code == 409
    # Old clients and pre-change stored records have no kind/channel/fingerprint.
    r = s.open_resume(j['id']); r = s.save_resume(r['id'], '旧正文', 0)
    old_v = s.save_version(r['id'], r['revision']); a = s.export_pdf(old_v['id'])
    old_body = dict(body, version_id=old_v['id'], artifact_id=a['id'], idempotency_key='legacy')
    old_body.pop('channel')
    historical_application(s, old_body)
    legacy = post(c, '/applications', old_body)
    assert legacy.status_code == 200, legacy.text
    import json
    old_record = legacy.json()
    for field in ('version_kind', 'channel', 'request_fingerprint'):
        old_record.pop(field, None)
    with s.connect() as db:
        # Construct an older-format fixture; normal API/SQL writes stay frozen.
        db.execute('DROP TRIGGER submission_frozen')
        db.execute('UPDATE applications SET body=? WHERE id=?', (json.dumps(old_record), old_record['id']))
        from workbench.resume_schema import install
        install(db)
    assert post(c, '/applications', old_body).json() == old_record
    assert old_record in Store(s.data_dir, TestProvider()).state()['applications']
