import json
import sqlite3
import hashlib
import pytest
from workbench.core import Store, Invalid, Conflict
from workbench.providers import TestProvider
from workbench.resume_migration import dry_run, apply_migration, verify_migration
from workbench.backup import backup, restore
from workbench.migration_baseline import inventory, verify_restore


def v2(path):
    """Exact old SQL shape; no calling new Store to manufacture a fake old schema."""
    path.mkdir()
    with sqlite3.connect(path/'workspace.sqlite3') as c:
        c.executescript('''CREATE TABLE meta(id INTEGER PRIMARY KEY CHECK(id=1),epoch INTEGER NOT NULL);
        INSERT INTO meta VALUES(1,0);
        CREATE TABLE current(id TEXT PRIMARY KEY,kind TEXT NOT NULL,revision INTEGER NOT NULL,body TEXT NOT NULL);
        CREATE TABLE revisions(id TEXT NOT NULL,revision INTEGER NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(id,revision));
        CREATE TABLE records(id TEXT PRIMARY KEY,kind TEXT NOT NULL,body TEXT NOT NULL);
        CREATE UNIQUE INDEX version_pdf ON records(json_extract(body,'$.version_id')) WHERE kind='artifact';
        CREATE TABLE applications(id TEXT PRIMARY KEY,job_id TEXT NOT NULL,version_id TEXT NOT NULL REFERENCES records(id),artifact_id TEXT NOT NULL REFERENCES records(id),idempotency_key TEXT NOT NULL UNIQUE,body TEXT NOT NULL);
        PRAGMA user_version=2;''')
        c.execute('INSERT INTO current VALUES(?,?,?,?)',('profile','profile',0,json.dumps(dict(id='profile',content='',revision=0,verified=False))))
    return path


def test_explicit_v3_migration_rollback_and_source_guard(tmp_path):
    source=v2(tmp_path/'v2');before=inventory(source);plan=dry_run(source)
    assert inventory(source)['snapshot_sha256']==before['snapshot_sha256']
    with pytest.raises(Invalid):Store(source,TestProvider())
    bundle=backup(source,tmp_path/'backups','pre-c')
    def fail(point):raise RuntimeError('synthetic DDL failure')
    with pytest.raises(RuntimeError):apply_migration(source,plan,fault=fail)
    assert inventory(source)['snapshot_sha256']==before['snapshot_sha256']
    result=apply_migration(source,plan);assert result['schema_version']==3
    assert verify_migration(source)['verified']
    assert apply_migration(source,plan)==result
    with pytest.raises(Conflict):apply_migration(source,dict(plan,source_snapshot_sha256='wrong'))
    from workbench.communication_migration import dry_run as d_plan, apply_migration as d_migrate, verify_migration as verify_d
    from workbench.interview_migration import dry_run as e_plan, apply_migration as e_migrate, verify_migration as verify_e
    from workbench.offer_migration import dry_run as f_plan, apply_migration as f_migrate, verify_migration as verify_f
    d_migrate(source,d_plan(source));assert verify_d(source)['verified']
    e_migrate(source,e_plan(source));assert verify_e(source)['verified']
    f_migrate(source,f_plan(source));assert verify_f(source)['verified'];Store(source,TestProvider())
    restore(bundle,tmp_path/'rollback');assert verify_restore(bundle,tmp_path/'rollback')['verified']
    assert inventory(tmp_path/'rollback')['snapshot']['schema_version']==2
    fresh=backup(source,tmp_path/'backups','v6');restore(fresh,tmp_path/'forward')
    assert verify_restore(fresh,tmp_path/'forward')['verified']
    Store(tmp_path/'forward',TestProvider())


@pytest.mark.parametrize('case',['mapped','multiple','conflict','missing_pdf'])
def test_legacy_application_mapping_is_preserved_or_gated(tmp_path,case):
    source=v2(tmp_path/'v2');(source/'artifacts').mkdir()
    raw=b'%PDF-1.7\nlegacy synthetic bytes\n%%EOF';(source/'artifacts'/'old.pdf').write_bytes(raw)
    with sqlite3.connect(source/'workspace.sqlite3') as c:
        for ident,kind,body in [
            ('company','domain_company',dict(name='虚构公司')),
            ('opportunity:j','opportunity',dict(format_version=2,company_id='company')),
            ('opportunity:other','opportunity',dict(format_version=2,company_id='company'))]:
            c.execute('INSERT INTO current VALUES(?,?,?,?)',(ident,kind,1,json.dumps(dict(id=ident,**body))))
        c.execute('INSERT INTO records VALUES(?,?,?)',('v','editor_version',json.dumps(dict(id='v',artifact_id='a',document=dict(meta=dict(source_refs=[]))))))
        c.execute('INSERT INTO records VALUES(?,?,?)',('a','artifact',json.dumps(dict(id='a',version_id='v',path='artifacts/old.pdf',sha256=hashlib.sha256(raw).hexdigest()))))
        for n in range(2 if case=='multiple' else 1):
            body=dict(id='app'+str(n),job_id='j',version_id='v',artifact_id='a',greeting_legacy='保留原字节')
            if case=='conflict':body['opportunity_id']='opportunity:other'
            c.execute('INSERT INTO applications VALUES(?,?,?,?,?,?)',(body['id'],'j','v','a','old'+str(n),json.dumps(body,indent=2)))
    if case=='missing_pdf':
        (source/'artifacts'/'old.pdf').unlink()
        with pytest.raises(Invalid):dry_run(source)
        return
    before=inventory(source);plan=dry_run(source)
    if case in ('multiple','conflict'):
        assert plan['migration_gates']
        with pytest.raises(Invalid):apply_migration(source,plan)
        assert inventory(source)['snapshot_sha256']==before['snapshot_sha256']
    else:
        assert apply_migration(source,plan)['mapped']==1
        assert verify_migration(source)['verified']
        with sqlite3.connect(source/'workspace.sqlite3') as c:
            assert c.execute('SELECT canonical_opportunity_id FROM applications').fetchone()[0]=='opportunity:j'
