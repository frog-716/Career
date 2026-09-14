import json
from pathlib import Path
from workbench.core import Store
from workbench.providers import TestProvider
from workbench.backup import backup, restore

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
