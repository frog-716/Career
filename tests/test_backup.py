import json
from pathlib import Path
from workbench.core import Store
from workbench.providers import TestProvider
from workbench.backup import backup, restore
from workbench.core import Invalid

F=json.loads((Path(__file__).parents[1]/'fixtures/scenarios.json').read_text())

def test_snapshot_and_restore_pdf(tmp_path):
    s=Store(tmp_path/'source',TestProvider())
    s.save_profile(F['candidate']['experience']['revision2'],0)
    j=s.save_job({k:F['job'][k] for k in ('company','title','jd')})
    r=s.open_resume(j['id']);r=s.save_resume(r['id'],F['historicalApplication']['usedResumeText'],0)
    v=s.save_version(r['id'],1);a=s.export_pdf(v['id'])
    bundle=backup(s.data_dir,tmp_path/'backups')
    restore(bundle,tmp_path/'restored')
    dest=Store(tmp_path/'restored',TestProvider())
    assert dest.state()['profile']==s.state()['profile']
    assert dest.artifact(a['id'])[0].read_bytes()==s.artifact(a['id'])[0].read_bytes()


def test_backup_rejects_missing_hash_mismatch_and_orphan(tmp_path):
    s=Store(tmp_path/'source',TestProvider())
    s.save_profile(F['candidate']['experience']['revision2'],0)
    j=s.save_job({k:F['job'][k] for k in ('company','title','jd')})
    r=s.open_resume(j['id']);r=s.save_resume(r['id'],F['historicalApplication']['usedResumeText'],0)
    v=s.save_version(r['id'],1);a=s.export_pdf(v['id'])
    bundle=backup(s.data_dir,tmp_path/'backups')

    manifest=json.loads((bundle/'manifest.json').read_text())
    manifest['files'].pop(a['path'])
    broken=tmp_path/'broken-missing';broken.mkdir()
    (broken/'manifest.json').write_text(json.dumps(manifest))
    for path in bundle.rglob('*'):
        if path.is_file() and path.name != 'manifest.json':
            target=broken/path.relative_to(bundle);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
    try:
        restore(broken,tmp_path/'missing-restored')
    except Invalid as exc:
        assert '遗漏' in str(exc)
    else:
        raise AssertionError('missing artifact manifest entry was accepted')

    artifact_path=bundle/a['path']
    original_bytes=artifact_path.read_bytes()
    artifact_path.write_bytes(b'corrupt')
    try:
        restore(bundle,tmp_path/'hash-restored')
    except Invalid as exc:
        assert '哈希' in str(exc)
    else:
        raise AssertionError('artifact hash mismatch was accepted')
    artifact_path.write_bytes(original_bytes)
    (bundle/'artifacts'/'orphan.pdf').write_bytes(b'orphan')
    try:
        restore(bundle,tmp_path/'orphan-restored')
    except Invalid as exc:
        assert '孤儿' in str(exc)
    else:
        raise AssertionError('orphan artifact was accepted')
