"""Migration safety contracts, exclusively synthetic stores and temporary files."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.backup import backup, restore
from workbench.core import Store, Invalid
from workbench.providers import TestProvider
from workbench.migration_baseline import inventory, verify_restore, write_report


@pytest.fixture
def source(tmp_path):
    store = Store(tmp_path / 'source', TestProvider())
    job = store.save_job(dict(company='Synthetic Company', title='Role', jd='Synthetic JD'))
    resume = store.open_resume(job['id'])
    resume = store.save_resume(resume['id'], 'Synthetic resume sentinel', 0)
    version = store.save_version(resume['id'], resume['revision'])
    artifact = store.export_pdf(version['id'])
    store.record_application(dict(job_id=job['id'], version_id=version['id'],
        artifact_id=artifact['id'], applied_at='2026-09-17T10:00:00+00:00',
        status='applied', idempotency_key='first'))
    return store, job, version, artifact


def test_read_only_repeatable_inventory_and_real_restore(source, tmp_path):
    store, job, version, artifact = source
    original = store.db.read_bytes()
    first = inventory(store.data_dir)
    second = inventory(store.data_dir)
    assert first['snapshot'] == second['snapshot']
    assert store.db.read_bytes() == original
    assert first['integrity'] == ['ok'] and first['foreign_key_violations'] == []
    assert first['canonical_opportunities'][0]['canonical_id'] == 'opportunity:' + job['id']
    assert version['id'] in first['snapshot']['row_hashes']['records']
    assert first['artifacts'][0]['id'] == artifact['id']
    bundle = backup(store.data_dir, tmp_path / 'backups')
    destination = tmp_path / 'restored'
    restore(bundle, destination)
    verified = verify_restore(bundle, destination)
    assert verified['verified'], verified
    assert inventory(destination)['snapshot'] == first['snapshot']
    assert store.db.read_bytes() == original
    assert 'Synthetic resume sentinel' not in json.dumps(first)


def test_inventory_reports_ambiguity_without_deciding(source):
    store, job, version, artifact = source
    store.record_application(dict(job_id=job['id'], version_id=version['id'],
        artifact_id=artifact['id'], applied_at='2026-09-18T10:00:00+00:00',
        status='applied', idempotency_key='second'))
    with store.connect() as c:
        store._save(c, 'domain_company', dict(id='company', name='Different Company'), 0)
        store._save(c, 'opportunity_context', dict(id='context', job_id=job['id'], company_id='company'), 0)
        for n in range(2):
            store._record(c, 'offer', dict(id='offer' + str(n), opportunity_id='opportunity:' + job['id']))
        store._record(c, 'interview', dict(id='unknown-round', opportunity_id='opportunity:' + job['id'], demo_dataset_id='case'))
        store._save(c, 'wiki_entry', dict(id='wiki', source_ids=['missing', job['id']], scope_type='personal', scope_id=''), 0)
    before = store.db.read_bytes()
    report = inventory(store.data_dir)
    assert report['multiple_submissions'] and report['multiple_offers']
    assert report['company_conflicts']
    assert report['interview_unknowns'][0]['classification'] == 'demo_legacy'
    assert any(x['code'] == 'missing_or_wrong_kind_reference' for x in report['integrity_issues'])
    assert {x['target'] for x in report['integrity_issues'] if x['code'] == 'missing_or_wrong_kind_reference'} == {'missing', job['id']}
    assert store.db.read_bytes() == before


def test_verify_detects_modified_frozen_snapshot_and_artifact(source, tmp_path):
    store, _, _, artifact = source
    bundle = backup(store.data_dir, tmp_path / 'backups')
    destination = tmp_path / 'restored'
    restore(bundle, destination)
    with sqlite3.connect(str(destination / 'workspace.sqlite3')) as c:
        body = json.loads(c.execute('SELECT body FROM applications').fetchone()[0])
        body['resume_snapshot'] = {'content': 'tampered frozen content'}
        c.execute('UPDATE applications SET body=?', (json.dumps(body),))
    result = verify_restore(bundle, destination)
    assert not result['verified'] and 'snapshot' in result['differences']
    artifact_only = tmp_path / 'artifact-only'
    restore(bundle, artifact_only)
    (artifact_only / artifact['path']).write_bytes(b'corrupted')
    result = verify_restore(bundle, artifact_only)
    assert not result['verified'] and 'restored_integrity' in result['differences']
    missing_row = tmp_path / 'missing-row'
    restore(bundle, missing_row)
    with sqlite3.connect(str(missing_row / 'workspace.sqlite3')) as c:
        c.execute('DELETE FROM applications')
    result = verify_restore(bundle, missing_row)
    assert not result['verified'] and 'snapshot' in result['differences']


def test_missing_source_wrong_schema_and_outputs_are_safe(source, tmp_path):
    store, _, _, _ = source
    missing = tmp_path / 'missing'
    with pytest.raises(ValueError):
        inventory(missing)
    assert not missing.exists()
    with pytest.raises(ValueError):
        write_report(store.data_dir / 'report.json', {}, [store.data_dir])
    output = tmp_path / 'report.json'
    write_report(output, {'ok': True}, [store.data_dir])
    with pytest.raises(FileExistsError):
        write_report(output, {}, [store.data_dir])
    with store.connect() as c:
        c.execute('PRAGMA user_version=99')
    with pytest.raises(ValueError):
        inventory(store.data_dir)


def test_backup_restore_destinations_cannot_overlap_or_overwrite(source, tmp_path):
    store, _, _, _ = source
    with pytest.raises(Invalid):
        backup(store.data_dir, store.data_dir / 'backups')
    assert not (store.data_dir / 'backups').exists()
    output = tmp_path / 'backups'
    bundle = backup(store.data_dir, output, 'fixed')
    with pytest.raises(Invalid):
        backup(store.data_dir, output, 'fixed')
    with pytest.raises(Invalid):
        restore(bundle, store.data_dir)
    with pytest.raises(Invalid):
        restore(bundle, bundle / 'nested')


def test_artifact_escape_and_corruption_are_not_followed(source, tmp_path):
    store, _, _, artifact = source
    file = store.data_dir / artifact['path']
    file.unlink()
    external = tmp_path / 'private.txt'
    external.write_text('not an artifact')
    file.symlink_to(external)
    report = inventory(store.data_dir)
    assert any(i['code'] == 'unsafe_artifact_path' for i in report['integrity_issues'])
    assert report['artifacts'][0]['actual_sha256'] is None


def test_profile_revision_contract_explains_old_failures(tmp_path):
    client = TestClient(create_app(Store(tmp_path / 'profile', TestProvider())))
    headers = {'X-Career-Request': '1'}
    def post(path, body):
        return client.post('/api' + path, json=body, headers=headers)
    basics = dict(name='Synthetic', phone='123', email='a@example.invalid',
        wechat='fake', github='https://github.com/example',
        links=[dict(label='Work', url='https://example.invalid')])
    original = client.get('/api/editor').json()
    profile = post('/profile/basics', dict(basics=basics, expected_revision=0)).json()
    draft = client.get('/api/editor').json()
    assert draft['revision'] > original['revision']
    body = dict(include_profile=True, profile_revision=profile['revision'], selections=[],
        expected_revision=original['revision'], idempotency_key='stale')
    assert post('/editor/select-facts', body).status_code == 409
    result = post('/editor/select-facts', dict(body, expected_revision=draft['revision'], idempotency_key='fresh'))
    assert result.status_code == 200, result.text
    saved = result.json()
    assert saved['document']['profile']['name'] == 'Synthetic'
    profile = post('/profile/basics', dict(basics=dict(name='Updated', phone='123', email='a@example.invalid'),
        expected_revision=profile['revision'])).json()
    assert profile['basics']['wechat'] == 'fake' and profile['basics']['links'] == basics['links']
    assert post('/editor/select-facts', dict(body, profile_revision=profile['revision'],
        expected_revision=saved['revision'], idempotency_key='stale-again')).status_code == 409
    latest = client.get('/api/editor').json()
    result = post('/editor/select-facts', dict(body, profile_revision=profile['revision'],
        expected_revision=latest['revision'], idempotency_key='refresh'))
    assert result.status_code == 200, result.text
    assert result.json()['document']['profile']['name'] == 'Updated'
    assert any(x.get('href') == basics['github'] for x in result.json()['document']['profile']['contacts'])
