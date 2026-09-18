"""Hash-bound explicit v2→v3 migration; only isolated copies may be mutated."""
import json
import sqlite3
from pathlib import Path
from .core import Invalid, Conflict, digest, dump, now
from .opportunity_migration import isolated_root
from .migration_baseline import inventory, _hash
from .resume_schema import APPLICATIONS, install

MIGRATION_ID='migration:resume-v3'
OLD_COLUMNS=('id','job_id','version_id','artifact_id','idempotency_key','body')


def dry_run(data_dir):
    report=inventory(data_dir)
    report.pop('observed_at',None)
    if report['snapshot']['schema_version']!=2:raise Invalid('需要schema v2源副本')
    if report['integrity']!=['ok'] or report['integrity_issues'] or report['foreign_key_violations']:raise Invalid('源完整性未通过')
    with sqlite3.connect((Path(data_dir).resolve()/'workspace.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
        canonical={r[0]:json.loads(r[1]) for r in c.execute("SELECT id,body FROM current WHERE kind='opportunity' AND json_extract(body,'$.format_version')=2")}
        mapping=[];seen={};gates=[]
        for aid,job,raw in c.execute('SELECT id,job_id,body FROM applications'):
            body=json.loads(raw);by_job='opportunity:'+job if not job.startswith('opportunity:') else job
            explicit=body.get('opportunity_id');target=by_job if by_job in canonical else None
            if explicit in canonical:
                if explicit!=by_job:gates.append(dict(code='conflicting_submission_owner',application_id=aid))
                target=explicit
            if target:
                if target in seen:gates.append(dict(code='multiple_submissions',opportunity_id=target,application_ids=[seen[target],aid]))
                seen[target]=aid
            mapping.append(dict(application_id=aid,canonical_opportunity_id=target))
    return dict(migration_id=MIGRATION_ID,source_snapshot_sha256=report['snapshot_sha256'],source_schema_version=2,
                applications=mapping,migration_gates=gates,inventory=report)


def apply_migration(data_dir,plan,fault=lambda point:None):
    root=isolated_root(data_dir)
    if (root/'artifacts').is_symlink():raise Invalid('附件目录不能是链接')
    fp=digest(plan)
    with sqlite3.connect(root/'workspace.sqlite3') as c:
        c.execute('PRAGMA foreign_keys=ON');c.execute('BEGIN IMMEDIATE')
        saved=c.execute("SELECT body FROM records WHERE id=? AND kind='resume_migration'",(MIGRATION_ID,)).fetchone()
        if saved:
            saved=json.loads(saved[0])
            if saved['fingerprint']!=fp:raise Conflict('迁移输入已变化')
            if c.execute('PRAGMA user_version').fetchone()[0]!=3:raise Invalid('迁移标记/schema不一致')
            return saved['result']
        actual=dry_run(root)
        if actual!=plan:raise Conflict('源数据/计划已变化，请重新dry-run')
        if actual['migration_gates']:raise Invalid('存在未解决的Submission关联Gate')
        columns=[r[1] for r in c.execute('PRAGMA table_info(applications)')]
        if columns!=list(OLD_COLUMNS):raise Invalid('源applications schema不是已核对的v2形状')
        rows=list(c.execute('SELECT '+','.join(OLD_COLUMNS)+' FROM applications ORDER BY rowid'))
        c.execute('ALTER TABLE applications RENAME TO applications_v2')
        c.execute(APPLICATIONS)
        mapping={x['application_id']:x['canonical_opportunity_id'] for x in actual['applications']}
        for row in rows:c.execute('INSERT INTO applications VALUES(?,?,?,?,?,?,?)',(*row,mapping[row[0]]))
        c.execute('DROP TABLE applications_v2');fault('after_table')
        install(c)
        c.execute('PRAGMA user_version=3')
        result=dict(schema_version=3,mapped=sum(v is not None for v in mapping.values()),legacy_deferred=sum(v is None for v in mapping.values()))
        record=dict(id=MIGRATION_ID,fingerprint=fp,plan=plan,result=result,created_at=now())
        c.execute('INSERT INTO records VALUES(?,?,?)',(MIGRATION_ID,'resume_migration',dump(record)))
        if c.execute('PRAGMA foreign_key_check').fetchall():raise Invalid('迁移FK检查失败')
        fault('before_commit')
    return result


def verify_migration(data_dir):
    report=inventory(data_dir);root=Path(data_dir).resolve()
    with sqlite3.connect((root/'workspace.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
        row=c.execute("SELECT body FROM records WHERE id=? AND kind='resume_migration'",(MIGRATION_ID,)).fetchone()
        if not row:raise Invalid('没有C迁移标记')
        saved=json.loads(row[0]);before=saved['plan']['inventory']['snapshot'];differences=[]
        if digest(saved['plan'])!=saved['fingerprint'] or _hash(before)!=saved['plan']['source_snapshot_sha256']:differences.append('manifest_hash')
        projected={str(r[0]):_hash(dict(zip(OLD_COLUMNS,r))) for r in c.execute('SELECT '+','.join(OLD_COLUMNS)+' FROM applications')}
        for table,hashes in before['row_hashes'].items():
            after=projected if table=='applications' else report['snapshot']['row_hashes'][table]
            for ident,value in hashes.items():
                if after.get(ident)!=value:differences.append(dict(table=table,id=ident))
        mapping={r[0]:r[1] for r in c.execute('SELECT id,canonical_opportunity_id FROM applications')}
        for item in saved['plan']['applications']:
            if mapping.get(item['application_id'])!=item['canonical_opportunity_id']:differences.append('canonical_mapping')
    if report['snapshot']['artifact_files']!=before['artifact_files']:differences.append('artifact_bytes')
    if report['snapshot']['schema_version']!=3:differences.append('schema_version')
    differences+=report['integrity_issues']+report['foreign_key_violations']
    return dict(verified=not differences and report['integrity']==['ok'],differences=differences,schema_version=3,
                table_counts=report['snapshot']['table_counts'],snapshot_sha256=report['snapshot_sha256'])
