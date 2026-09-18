"""Batch B safety contracts. All fixture data is synthetic and temporary."""
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from workbench.app import create_app
from workbench.core import Store, Invalid, Conflict
from workbench.providers import TestProvider
from workbench.backup import backup, restore
from workbench.migration_baseline import inventory, verify_restore
from workbench.opportunity_migration import dry_run, apply_migration, verify_migration

HEADERS = {'X-Career-Request': '1'}


def client_at(path):
    from workbench.resume_migration import dry_run as c_plan, apply_migration as c_migrate
    from workbench.communication_migration import dry_run as d_plan, apply_migration as d_migrate
    from workbench.interview_migration import dry_run as e_plan, apply_migration as e_migrate
    from workbench.offer_migration import dry_run as f_plan, apply_migration as f_migrate
    if (path/'workspace.sqlite3').exists():
        with sqlite3.connect(path/'workspace.sqlite3') as db:version=db.execute('PRAGMA user_version').fetchone()[0]
        if version==2:c_migrate(path,c_plan(path))
        with sqlite3.connect(path/'workspace.sqlite3') as db:version=db.execute('PRAGMA user_version').fetchone()[0]
        if version==3:d_migrate(path,d_plan(path))
        with sqlite3.connect(path/'workspace.sqlite3') as db:version=db.execute('PRAGMA user_version').fetchone()[0]
        if version==4:e_migrate(path,e_plan(path))
        with sqlite3.connect(path/'workspace.sqlite3') as db:version=db.execute('PRAGMA user_version').fetchone()[0]
        if version==5:f_migrate(path,f_plan(path))
    return TestClient(create_app(Store(path, TestProvider())))


def post(client, path, body):
    return client.post('/api' + path, json=body, headers=HEADERS)


def create(client, name='Acme', key='create'):
    response = post(client, '/opportunities', dict(company_name=name, title='Engineer', jd='Synthetic JD', idempotency_key=key))
    assert response.status_code == 200, response.text
    return response.json()


def legacy(path):
    store = Store(path, TestProvider())
    from batch_c_helpers import legacy_storage
    legacy_storage(store)
    job = dict(id='legacy-job', company='Synthetic Company', title='Engineer', jd='Original JD', url='', status='active', revision=1, created_at='2026-09-01T08:00:00+00:00')
    with sqlite3.connect(store.db) as c:
        c.execute('PRAGMA user_version=1')
        c.execute('INSERT INTO current VALUES(?,?,?,?)', ('legacy-job','job',1,json.dumps(job)))
        plan=dict(id='nonstandard-plan-id', job_id='legacy-job',stage='closed',next_action='Synthetic reminder',due_date='2026-10-01',revision=1)
        c.execute('INSERT INTO current VALUES(?,?,?,?)', (plan['id'],'journey_plan',1,json.dumps(plan)))
    return store.db


def confirmed(plan, phase='resume', result='active'):
    plan['decisions'][0].update(action='migrate', confirmed=True, company_name='Synthetic Company', phase=phase, result=result, phase_changed_on=None, reason='Synthetic user confirmation')
    return plan


def test_unicode_company_identity_and_cas(tmp_path):
    c=client_at(tmp_path/'v2')
    a=create(c,'  ＡＣＭＥ  ')
    b=create(c,'acme','other-attempt')
    assert a['company_id']==b['company_id']
    assert a['company']=='ＡＣＭＥ' and a['id']!=b['id']
    assert a['phase']=='resume' and a['result']=='active'
    assert a['created_on']==a['phase_changed_on']
    assert create(c,'acme','other-attempt')['id']==b['id']
    assert create(c,'Straße','strasse')['company_id']==create(c,'STRASSE','strasse2')['company_id']
    assert create(c,'Café','accent')['company_id']==create(c,'Cafe\u0301','accent2')['company_id']
    assert create(c,'Acme Holdings','different')['company_id']!=a['company_id']
    update=dict(title='Updated',expected_revision=a['revision'],idempotency_key='edit')
    changed=post(c,'/opportunities/'+a['id'],update)
    assert changed.status_code==200,changed.text
    assert changed.json()['phase_changed_on']==a['phase_changed_on']
    assert post(c,'/opportunities/'+a['id'],dict(update,idempotency_key='stale')).status_code==409
    assert post(c,'/opportunities/'+a['id'],dict(update,expected_revision=changed.json()['revision'],phase='offer',idempotency_key='attack')).status_code==422
    with sqlite3.connect(tmp_path/'v2/workspace.sqlite3') as db:
        assert db.execute("SELECT count(*) FROM current WHERE kind='job'").fetchone()[0]==0
        assert db.execute('PRAGMA user_version').fetchone()[0]==6


def test_company_concurrency_ambiguity_and_end(tmp_path):
    path=tmp_path/'v2';Store(path,TestProvider())
    def operation(pair):
        with client_at(path) as c:return create(c,pair[1],pair[0])
    with ThreadPoolExecutor(max_workers=2) as pool:
        a,b=list(pool.map(operation,[('one','Ａcme'),('two','acme')]))
    assert a['company_id']==b['company_id']
    c=client_at(path)
    end=dict(result='withdrawn',expected_revision=a['revision'],idempotency_key='end')
    closed=post(c,'/opportunities/'+a['id']+'/end',end)
    assert closed.status_code==200,closed.text
    assert closed.json()['phase']==a['phase']
    assert post(c,'/opportunities/'+a['id']+'/end',end).json()==closed.json()
    assert [x['id'] for x in c.get('/api/opportunities?view=ended').json()]==[a['id']]
    assert post(c,'/opportunities/'+b['id']+'/end',dict(end,result='accepted',idempotency_key='bad')).status_code==422
    with sqlite3.connect(path/'workspace.sqlite3') as db:
        duplicate=dict(id='duplicate',name='ACME',revision=1)
        db.execute('INSERT INTO current VALUES(?,?,?,?)',('duplicate','domain_company',1,json.dumps(duplicate)))
    assert post(c,'/opportunities',dict(company_name='acme',title='X',jd='J',idempotency_key='ambiguous')).status_code==409


def test_legacy_readonly_and_no_lifecycle_backdoor(tmp_path):
    path=tmp_path/'old';db=legacy(path);before=db.read_bytes()
    plan=dry_run(path)
    assert db.read_bytes()==before
    with pytest.raises(Invalid):Store(path,TestProvider())
    assert db.read_bytes()==before
    apply_migration(path,plan)
    assert verify_migration(path)['verified']
    c=client_at(path)
    old=c.get('/api/opportunities/opportunity:legacy-job').json()
    assert old['read_only'] and old['phase'] is None and old['result'] is None
    assert c.get('/api/opportunities?view=ended').json()==[]
    assert c.get('/api/opportunities/unknown').status_code==404
    for endpoint,body in [
        ('/jobs/legacy-job',dict(company='Changed',title='X',jd='X',status='deleted',expected_revision=1,idempotency_key='old-write')),
        ('/journey/plans/legacy-job',dict(stage='closed',expected_revision=1)),
        ('/opportunity-activity/interview',dict(opportunity_id='opportunity:legacy-job',content='Synthetic',idempotency_key='round')),
        ('/journey/notes',dict(scope_type='job',scope_id='legacy-job',kind='offer',content='Synthetic',idempotency_key='note')),
        ('/demo/load',{}),('/demo/remove',{})]:
        before=db.read_bytes()
        response=post(c,endpoint,body)
        assert response.status_code in (409,422), (endpoint,response.text)
        assert db.read_bytes()==before
    from workbench.offer_migration import verify_migration as verify_f
    assert verify_f(path)['verified']


def test_confirmed_migration_preserves_old_rows_and_repeats(tmp_path):
    path=tmp_path/'old';db=legacy(path)
    original=inventory(path)
    plan=confirmed(dry_run(path))
    result=apply_migration(path,plan)
    assert result['migrated']==['opportunity:legacy-job']
    assert apply_migration(path,plan)==result
    assert verify_migration(path)['verified']
    c=client_at(path);o=c.get('/api/opportunities/legacy-job').json()
    assert not o['read_only'] and o['phase_changed_on'] is None
    response=post(c,'/jobs/legacy-job',dict(title='New JD title',jd='Current JD',company='Synthetic Company',expected_revision=o['revision'],idempotency_key='compat'))
    assert response.status_code==200,response.text
    assert c.get('/api/opportunities/legacy-job').json()['jd']=='Current JD'
    with sqlite3.connect(db) as conn:
        assert json.loads(conn.execute("SELECT body FROM current WHERE id='legacy-job'").fetchone()[0])['jd']=='Original JD'
    assert inventory(path)['snapshot']['row_hashes']['current']['legacy-job']==original['snapshot']['row_hashes']['current']['legacy-job']


def test_migration_atomic_failure_changed_input_and_recovery(tmp_path):
    path=tmp_path/'old';db=legacy(path);plan=confirmed(dry_run(path));before=db.read_bytes()
    def fail(point):
        if point=='before_commit':raise RuntimeError('synthetic failure')
    with pytest.raises(RuntimeError):apply_migration(path,plan,fault=fail)
    assert inventory(path)['snapshot']['schema_version']==1
    assert db.read_bytes()==before
    bundle=backup(path,tmp_path/'backup','v1')
    apply_migration(path,plan)
    restored=tmp_path/'rollback';restore(bundle,restored)
    assert verify_restore(bundle,restored)['verified']
    assert inventory(restored)['snapshot']['schema_version']==1
    c=client_at(path);new=create(c,'New after migration','new-write')
    v2bundle=backup(path,tmp_path/'backup','v2')
    recovered=tmp_path/'forward';restore(v2bundle,recovered)
    assert verify_restore(v2bundle,recovered)['verified']
    assert client_at(recovered).get('/api/opportunities/'+new['id']).status_code==200
    with pytest.raises(Conflict):apply_migration(path,dict(plan,decisions=[]))

@pytest.mark.parametrize('phase',['resume','submitted','interview','offer'])
@pytest.mark.parametrize('result',['rejected','withdrawn'])
def test_all_phases_end_without_date_change(tmp_path,phase,result):
    path=tmp_path/'data';legacy(path);apply_migration(path,confirmed(dry_run(path),phase))
    c=client_at(path);o=c.get('/api/opportunities/legacy-job').json()
    assert c.get('/api/opportunities?view='+phase).json()==[o]
    end=post(c,'/opportunities/'+o['id']+'/end',dict(result=result,expected_revision=o['revision'],idempotency_key='end'))
    assert end.status_code==200,end.text
    assert end.json()['phase']==phase and end.json()['phase_changed_on'] is None
    assert c.get('/api/opportunities?view='+phase).json()==[]
    assert c.get('/api/opportunities?view=ended').json()==[end.json()]


def test_company_failure_and_business_day(tmp_path,monkeypatch):
    from workbench.opportunity import business_day
    assert business_day('2026-09-17T20:00:00Z')=='2026-09-18'
    c=client_at(tmp_path/'data');s=c.app.state.store;before=s.db.read_bytes();save=s._save
    def fail(conn,kind,body,revision):
        if kind=='opportunity':raise RuntimeError('synthetic failure after company')
        return save(conn,kind,body,revision)
    monkeypatch.setattr(s,'_save',fail)
    with pytest.raises(RuntimeError):create(c)
    assert s.db.read_bytes()==before


def test_before_image_and_changed_source(tmp_path):
    path=tmp_path/'data';db=legacy(path)
    with sqlite3.connect(db) as c:
        old=dict(id='opportunity:legacy-job',legacy_job_id='legacy-job',title='Engineer',jd='Original JD',company='Synthetic Company',revision=1)
        c.execute('INSERT INTO current VALUES(?,?,?,?)',(old['id'],'opportunity',1,json.dumps(old)))
    plan=confirmed(dry_run(path));apply_migration(path,plan)
    assert verify_migration(path)['verified']
    with sqlite3.connect(db) as c:
        row=json.loads(c.execute("SELECT body FROM records WHERE kind='opportunity_migration'").fetchone()[0]);row['before_images'][0]['body']='{}'
        c.execute("UPDATE records SET body=? WHERE kind='opportunity_migration'",(json.dumps(row),))
    assert not verify_migration(path)['verified']
    other=tmp_path/'changed';db=legacy(other);plan=dry_run(other)
    with sqlite3.connect(db) as c:c.execute('UPDATE meta SET epoch=epoch+1')
    with pytest.raises(Conflict):apply_migration(other,plan)


def test_confirmed_legacy_offer_requires_batch_f_review_before_acceptance(tmp_path):
    path=tmp_path/'data';db=legacy(path)
    with sqlite3.connect(db) as c:
        c.execute('INSERT INTO records VALUES(?,?,?)',('offer','offer',json.dumps(dict(id='offer',opportunity_id='opportunity:legacy-job'))))
    plan=confirmed(dry_run(path),'offer');plan['decisions'][0]['confirmed_offer_id']='offer'
    apply_migration(path,plan);c=client_at(path);o=c.get('/api/opportunities/legacy-job').json()
    body=dict(result='accepted',offer_id='foreign',expected_revision=o['revision'],idempotency_key='bad')
    assert post(c,'/opportunities/'+o['id']+'/end',body).status_code==422
    body.update(offer_id='offer',expected_offer_revision=0,idempotency_key='accept')
    result=post(c,'/opportunities/'+o['id']+'/end',body)
    assert result.status_code==409,result.text
    assert result.json()['detail'].startswith('legacy_offer_requires_review:')
    current=c.get('/api/opportunities/'+o['id']).json()
    assert current['phase']=='offer' and current['result']=='active'


def test_hardlink_and_report_collision_fail_before_migration(tmp_path):
    import os,subprocess,sys
    from pathlib import Path
    source=tmp_path/'original';db=legacy(source);before=db.read_bytes()
    linked=tmp_path/'linked';linked.mkdir();os.link(db,linked/'workspace.sqlite3')
    with pytest.raises(Invalid):apply_migration(linked,dry_run(source))
    assert db.read_bytes()==before
    output=tmp_path/'existing-report.json';output.write_text('keep')
    plan=tmp_path/'plan.json';plan.write_text(json.dumps(dry_run(source)))
    script=Path(__file__).resolve().parents[1]/'scripts/migrate_opportunity.py'
    result=subprocess.run([sys.executable,'-B',str(script),'apply',str(source),'--plan',str(plan),'--output',str(output)],capture_output=True)
    assert result.returncode==2 and output.read_text()=='keep'
    assert db.read_bytes()==before
