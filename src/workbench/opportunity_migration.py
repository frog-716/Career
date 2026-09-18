"""Explicit, hash-bound v1 -> v2 rehearsal. Never migrate the production directory."""
import json
import sqlite3
import tempfile
from datetime import date, datetime
from pathlib import Path
from .core import Store, Invalid, Conflict, digest, now, dump
from .opportunity import company, canonical_id, business_day, PHASES, RESULTS
from .migration_baseline import inventory, _hash

MIGRATION_ID='migration:opportunity-v2'


def isolated_root(data_dir):
    root=Path(data_dir).expanduser().resolve(strict=True)
    temp=Path(tempfile.gettempdir()).resolve()
    production=(Path.home()/'Library/Application Support/Career Data').resolve()
    if root==production or temp not in root.parents:
        raise Invalid('本批只允许系统临时目录内的隔离恢复副本；禁止Production Cutover')
    if (root/'workspace.sqlite3').is_symlink() or (root/'workspace.sqlite3').stat().st_nlink!=1:
        raise Invalid('隔离数据库不能是符号链接或硬链接')
    return root


def dry_run(data_dir):
    report=inventory(data_dir)
    if report['snapshot']['schema_version']!=1:raise Invalid('dry-run需要v1源数据')
    if report['integrity']!=['ok'] or report['integrity_issues'] or report['foreign_key_violations']:
        raise Invalid('数据完整性检查未通过')
    return dict(migration_id=MIGRATION_ID,source_snapshot_sha256=report['snapshot_sha256'],
                source_schema_version=1,business_timezone='Asia/Shanghai',
                decisions=[dict(job_id=x['legacy_job_id'],action='defer_legacy') for x in report['canonical_opportunities']],
                canonical_candidates=report['canonical_opportunities'],company_candidates=report['company_candidates'],
                demo_legacy_findings=report['demo_legacy_findings'],migration_gates=report['migration_gates'])


class TransactionWriter:
    """Reuse existing SQL/CAS primitives without invoking Store initialization."""
    _get=Store._get
    _current=Store._current
    _save=Store._save


def _date(value):
    if value is None:return None
    if not isinstance(value,str):raise Invalid('阶段日期必须是ISO日期或null')
    try:
        if date.fromisoformat(value).isoformat()!=value:raise ValueError()
    except ValueError as exc:raise Invalid('阶段日期无效') from exc
    return value


def apply_migration(data_dir,plan,fault=lambda point:None):
    root=isolated_root(data_dir)
    fingerprint=digest(plan)
    with sqlite3.connect(root/'workspace.sqlite3') as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute("SELECT body FROM records WHERE id=? AND kind='opportunity_migration'",(MIGRATION_ID,)).fetchone()
        if row:
            saved=json.loads(row[0])
            if saved['fingerprint']!=fingerprint:raise Conflict('迁移已经执行，输入指纹不一致')
            if c.execute('PRAGMA user_version').fetchone()[0]!=2:raise Invalid('迁移标记与schema版本不一致')
            return saved['result']
        version=c.execute('PRAGMA user_version').fetchone()[0]
        if version!=1 or plan.get('migration_id')!=MIGRATION_ID:raise Invalid('迁移版本不匹配')
        before=inventory(root)
        if before['snapshot_sha256']!=plan.get('source_snapshot_sha256'):raise Conflict('源数据已变化，必须重新dry-run')
        if before['integrity']!=['ok'] or before['integrity_issues'] or before['foreign_key_violations']:raise Invalid('源数据完整性失败')
        jobs={r[0]:json.loads(r[1]) for r in c.execute("SELECT id,body FROM current WHERE kind='job'")}
        decisions=plan.get('decisions',[])
        if len(decisions)!=len(jobs) or {x.get('job_id') for x in decisions}!=set(jobs):raise Invalid('决策必须逐一覆盖所有旧Job，不能缺失或重复')
        writer=TransactionWriter();migrated=[];deferred=[];before_images=[]
        for choice in decisions:
            job=jobs[choice['job_id']];oid=canonical_id(job['id'])
            if choice.get('action')=='defer_legacy':deferred.append(oid);continue
            if choice.get('action')!='migrate' or choice.get('confirmed') is not True or not choice.get('reason'):
                raise Invalid('迁入需要明确确认及依据，不能猜测历史')
            if job.get('demo_dataset_id'):raise Invalid('本批案例仅作legacy保留，不替用户决定G1/G2')
            phase,result=choice.get('phase'),choice.get('result')
            if phase not in PHASES or result not in RESULTS:raise Invalid('必须明确phase/result')
            offer_id=choice.get('confirmed_offer_id')
            if offer_id:
                offer=writer._get(c,offer_id,'offer',True)
                if canonical_id(offer.get('opportunity_id') or offer.get('job_id',''))!=oid:raise Invalid('Offer不属于该机会')
            if result=='accepted' and (phase!='offer' or not offer_id):raise Invalid('接受结果需要已核对Offer')
            if offer_id:
                offers=[json.loads(r[0]) for r in c.execute("SELECT body FROM records WHERE kind='offer'")]
                if len([o for o in offers if canonical_id(o.get('opportunity_id') or o.get('job_id',''))==oid])!=1:
                    raise Invalid('多个Offer尚未消歧，本批保留legacy')
            ended_at=choice.get('result_changed_at')
            if ended_at is not None:
                if result=='active':raise Invalid('active不能包含结束时间')
                try: business_day(ended_at)
                except (ValueError,AttributeError,TypeError) as exc: raise Invalid('结束时间必须是带时区时间戳') from exc
            if 'company_id' not in choice and 'company_name' not in choice:raise Invalid('必须明确公司主体')
            owner=company(writer,c,choice)
            prior=c.execute("SELECT id,kind,revision,body FROM current WHERE id=?",(oid,)).fetchone()
            if prior and prior[1]!='opportunity':raise Conflict('canonical ID被其他对象占用')
            if prior:before_images.append(dict(zip(('id','kind','revision','body'),prior)))
            # A migration revision must not accidentally accept a stale Job revision.
            expected=prior[2] if prior else 0
            high=max(expected,job.get('revision',0))
            if prior and expected<high:
                c.execute('UPDATE current SET revision=? WHERE id=?',(high,oid));expected=high
            elif not prior and high:
                c.execute('INSERT INTO current VALUES(?,?,?,?)',(oid,'opportunity',high,dump({'id':oid})));expected=high
            created=job.get('created_at')
            if not created:raise Invalid('创建时间未知，保留legacy或先核对明确来源')
            obj=dict(id=oid,format_version=2,legacy_job_id=job['id'],company_id=owner['id'],
                     title=job['title'],jd=job['jd'],url=job.get('url',''),phase=phase,result=result,
                     created_at=created,created_on=business_day(created),phase_changed_on=_date(choice.get('phase_changed_on')),
                     phase_source=dict(action='ConfirmedLegacyMigration',reason=choice['reason'],known=choice.get('phase_changed_on') is not None),
                     result_changed_at=choice.get('result_changed_at'),confirmed_offer_id=offer_id)
            writer._save(c,'opportunity',obj,expected);migrated.append(oid)
            fault('after_opportunity')
        fault('before_commit')
        c.execute('UPDATE meta SET epoch=epoch+1 WHERE id=1')
        c.execute('PRAGMA user_version=2')
        result=dict(migration_id=MIGRATION_ID,migrated=migrated,deferred_legacy=deferred,schema_version=2)
        saved=dict(id=MIGRATION_ID,fingerprint=fingerprint,plan=plan,result=result,
                   before_snapshot=before['snapshot'],before_images=before_images,completed_at=now())
        c.execute('INSERT INTO records VALUES(?,?,?)',(MIGRATION_ID,'opportunity_migration',dump(saved)))
    return result


def verify_migration(data_dir):
    report=inventory(data_dir)
    root=Path(data_dir).resolve()
    with sqlite3.connect((root/'workspace.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
        row=c.execute("SELECT body FROM records WHERE id=? AND kind='opportunity_migration'",(MIGRATION_ID,)).fetchone()
    if not row:raise Invalid('没有迁移完成证据')
    saved=json.loads(row[0]);before=saved['before_snapshot'];changed=set(saved['result']['migrated'])
    differences=[]
    if _hash(before)!=saved['plan'].get('source_snapshot_sha256') or digest(saved['plan'])!=saved['fingerprint']:
        differences.append({'manifest':'source_or_plan_hash_mismatch'})
    for table,hashes in before['row_hashes'].items():
        for id,value in hashes.items():
            if table=='meta' or (table=='current' and id in changed):continue
            if report['snapshot']['row_hashes'][table].get(id)!=value:differences.append(dict(table=table,id=id))
    for image in saved['before_images']:
        if _hash(image)!=before['row_hashes']['current'].get(image['id']):
            differences.append({'before_image':image['id']})
    for ident in changed.intersection(before['row_hashes']['current']):
        if not any(x['id']==ident for x in saved['before_images']):differences.append({'missing_before_image':ident})
    if report['snapshot']['schema_hash']!=before['schema_hash']:differences.append({'schema':'changed'})
    if report['snapshot']['artifact_files']!=before['artifact_files']:differences.append({'artifacts':'changed'})
    if report['snapshot']['schema_version']!=2: differences.append({'schema_version':'not_v2'})
    if report['integrity']!=['ok'] or report['integrity_issues'] or report['foreign_key_violations']:differences.append({'integrity':'failed'})
    return dict(verified=not differences,differences=differences,table_counts=report['snapshot']['table_counts'],
                migrated=saved['result']['migrated'],deferred_legacy=saved['result']['deferred_legacy'],
                snapshot_sha256=report['snapshot_sha256'],schema_version=report['snapshot']['schema_version'])
