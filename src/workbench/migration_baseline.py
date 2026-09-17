"""Read-only schema-v1 inventory and restore verification; never instantiate Store.

Reports contain identifiers, relationships and hashes, not personal prose. This
module proposes no mutations and cannot perform a domain/schema migration.
"""
import hashlib
import json
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPORT_VERSION = 1
TABLES = ('meta', 'current', 'records', 'applications', 'revisions')


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def _file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _root(path):
    root = Path(path).expanduser().resolve(strict=True)
    if not root.is_dir() or not (root / 'workspace.sqlite3').is_file():
        raise ValueError('必须明确指定包含workspace.sqlite3的已有数据目录')
    if (root / 'workspace.sqlite3').is_symlink():
        raise ValueError('数据库不能是符号链接')
    return root


def _files(root):
    return {name: _file_hash(root / name) for name in
            ('workspace.sqlite3', 'workspace.sqlite3-wal') if (root / name).is_file()}


def inventory(data_dir):
    """Inspect one consistent SQL snapshot and verify its local artifact references."""
    try:
        root = _root(data_dir)
    except OSError as exc:
        raise ValueError('数据目录或数据库不存在') from exc
    before = _files(root)
    c = sqlite3.connect((root / 'workspace.sqlite3').as_uri() + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    try:
        c.execute('PRAGMA query_only=ON')
        c.execute('BEGIN')
        version = c.execute('PRAGMA user_version').fetchone()[0]
        if version != 1:
            raise ValueError('只支持已核对的schema version 1，不推断未知schema')
        schema = [tuple(r) for r in c.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
        rows = {table: [dict(r) for r in c.execute('SELECT * FROM ' + table)] for table in TABLES}
        integrity = [r[0] for r in c.execute('PRAGMA integrity_check')]
        foreign_keys = [tuple(r) for r in c.execute('PRAGMA foreign_key_check')]
        current = {r['id']: dict(json.loads(r['body']), _kind=r['kind']) for r in rows['current']}
        records = {r['id']: dict(json.loads(r['body']), _kind=r['kind']) for r in rows['records']}
        apps = {r['id']: dict(json.loads(r['body']), _kind='application') for r in rows['applications']}
        objects = {**current, **records, **apps}
        issues, findings, refs = [], [], []

        def issue(code, **detail):
            issues.append(dict(code=code, **detail))

        def finding(code, values, **detail):
            values = list(values)
            classification = 'demo_legacy' if values and all(x.get('demo_dataset_id') for x in values) else 'unclassified_data'
            item = dict(code=code, classification=classification, **detail)
            findings.append(item)
            return item

        for table in ('current', 'records', 'applications'):
            for row in rows[table]:
                if json.loads(row['body']).get('id') != row['id']:
                    issue('body_id_mismatch', table=table, id=row['id'])
        for id in set(current) & set(records) | set(current) & set(apps) | set(records) & set(apps):
            issue('ambiguous_cross_table_id', id=id)
        jobs = {id: v for id, v in current.items() if v['_kind'] == 'job'}
        opportunities = {id: v for id, v in current.items() if v['_kind'] == 'opportunity'}
        canonical = []
        aliases = {id: 'opportunity:' + id for id in jobs}
        for id, value in opportunities.items():
            legacy = value.get('legacy_job_id')
            aliases[id] = 'opportunity:' + legacy if legacy in jobs else id
            if legacy not in jobs or id != 'opportunity:' + legacy:
                finding('canonical_mapping_conflict', [value], id=id, legacy_job_id=legacy)
        for id, value in jobs.items():
            target = 'opportunity:' + id
            other = opportunities.get(target)
            differences = [k for k in ('company', 'title', 'jd', 'url', 'status')
                           if other and other.get(k) != value.get(k)]
            canonical.append(dict(legacy_job_id=id, canonical_id=target,
                                  materialized=other is not None, differing_fields=differences))
            if differences:
                finding('job_opportunity_value_conflict', [value, other], id=id, fields=differences)

        def reference(owner, field, target, kinds, optional=False):
            if optional and target in (None, ''):
                return
            valid = target in objects and objects[target]['_kind'] in kinds if isinstance(target, str) else False
            # Existing old jobs can be exposed through a read-only canonical view.
            if 'opportunity' in kinds and target in aliases.values():
                valid = True
            refs.append(dict(owner=owner, field=field, target=target, valid=valid))
            if not valid:
                issue('missing_or_wrong_kind_reference', owner=owner, field=field, target=target)
            elif objects.get(target, {}).get('demo_dataset_id') and not objects[owner].get('demo_dataset_id'):
                refs[-1]['cross_dataset_reference'] = True

        contexts = [x for x in current.values() if x['_kind'] == 'opportunity_context']
        companies = {id: x for id, x in current.items() if x['_kind'] == 'domain_company'}
        company_candidates, company_conflicts = [], []
        for id, job in jobs.items():
            linked = [x for x in contexts if x.get('job_id') == id]
            matches = [cid for cid, x in companies.items() if x.get('name', '').strip() == job.get('company', '').strip()]
            company_candidates.append(dict(job_id=id, linked_ids=[x.get('company_id') for x in linked], exact_name_matches=matches))
            if not linked and len(matches) > 1:
                company_conflicts.append(finding('ambiguous_company_match', [job], job_id=id, candidates=matches))
            for context in linked:
                cid = context.get('company_id')
                if cid in companies and companies[cid].get('name') != job.get('company'):
                    company_conflicts.append(finding('company_name_conflict', [job, companies[cid]], job_id=id, company_id=cid))

        def groups(values):
            result = defaultdict(list)
            for id, value in values.items():
                raw = value.get('opportunity_id') or value.get('job_id')
                result[aliases.get(raw, raw)].append(id)
            return dict(sorted(result.items(), key=lambda p: str(p[0])))

        submissions = groups(apps)
        offers = groups({id: x for id, x in records.items() if x['_kind'] == 'offer'})
        multiple_submissions, multiple_offers = [], []
        for grouped, label, result in ((submissions, 'multiple_submissions', multiple_submissions),
                                       (offers, 'multiple_offers', multiple_offers)):
            for id, ids in grouped.items():
                if len(ids) > 1:
                    result.append(finding(label, [objects[x] for x in ids], opportunity_id=id, ids=ids))

        interviews = []
        typed_raw = {x.get('raw_note_id') for x in records.values() if x['_kind'] == 'interview'}
        for id, value in records.items():
            if value['_kind'] == 'interview' or (value['_kind'] == 'journey_note' and
                    value.get('kind') == 'interview' and value.get('scope_type') == 'job' and id not in typed_raw):
                unknown = []
                if value.get('type') not in ('real', 'simulation'): unknown.append('real_or_simulation')
                if not value.get('date'): unknown.append('business_interview_date')
                if not value.get('confirmed_at'): unknown.append('confirmation_date')
                if unknown:
                    interviews.append(finding('interview_semantics_unknown', [value], id=id, unknown=unknown))

        for id, obj in objects.items():
            kind = obj['_kind']
            fields = {}
            if kind in ('resume', 'version', 'journey_plan', 'run'):
                fields.update(job_id=['job'])
            if kind == 'version': fields.update(resume_id=['resume'])
            if kind == 'opportunity': fields.update(legacy_job_id=['job'])
            if kind in ('application', 'resume_use', 'editor_version', 'version'):
                fields.update(version_id=['version', 'editor_version'], artifact_id=['artifact'])
            if kind == 'application': fields.update(job_id=['job'], opportunity_id=['opportunity'])
            if kind == 'artifact': fields.update(version_id=['version', 'editor_version'])
            if kind in ('research_snapshot', 'communication', 'interview', 'offer'):
                fields.update(raw_note_id=['journey_note'], opportunity_id=['opportunity'], submission_id=['application'])
            if kind == 'opportunity_context':
                fields.update(job_id=['job'], company_id=['domain_company'], org_unit_id=['domain_org_unit'],
                              target_role_id=['domain_target_role'], search_cycle_id=['domain_search_cycle'])
            if kind == 'knowledge_candidate': fields.update(entry_id=['wiki_entry'])
            if kind in ('journey_note', 'knowledge_source', 'knowledge_candidate'):
                fields.update(submission_id=['application'])
            for field, kinds in fields.items():
                if field in obj:
                    reference(id, field, obj[field], kinds, optional=field in
                              ('submission_id', 'entry_id', 'company_id', 'org_unit_id', 'target_role_id', 'search_cycle_id'))
            if kind in ('wiki_entry', 'knowledge_candidate'):
                for sid in obj.get('source_ids', []):
                    reference(id, 'source_ids', sid, ['knowledge_source'])
                    source = records.get(sid)
                    if source and (obj.get('scope_type'), obj.get('scope_id')) != (source.get('scope_type'), source.get('scope_id')):
                        issue('source_scope_mismatch', owner=id, source_id=sid)
            for oid in obj.get('opportunity_ids', []):
                reference(id, 'opportunity_ids', oid, ['opportunity'])
            if kind in ('resume_use', 'knowledge_source', 'wiki_entry', 'knowledge_candidate', 'journey_note'):
                scope = {'job': ['job'], 'opportunity': ['opportunity'], 'role': ['domain_target_role'], 'episode': ['journey_episode']}.get(obj.get('scope_type'))
                if scope: reference(id, 'scope_id', obj.get('scope_id'), scope)
            for ref in obj.get('document', {}).get('meta', {}).get('source_refs', []):
                reference(id, 'document.source_refs', ref.get('source_id'), ['profile', 'wiki_entry'])
            origin = obj.get('origin', {})
            if kind in ('knowledge_source', 'knowledge_candidate') and origin.get('kind') == 'journey_note':
                reference(id, 'origin.id', origin.get('id'), ['journey_note'])
            if kind == 'resume_use' and obj.get('artifact_id') in records:
                artifact = records[obj['artifact_id']]
                if artifact.get('sha256') != obj.get('artifact_hash') or artifact.get('version_id') != obj.get('version_id'):
                    issue('resume_use_artifact_mismatch', owner=id, artifact_id=obj['artifact_id'])

        artifacts, disk_files = [], {}
        directory = root / 'artifacts'
        if directory.is_symlink():
            issue('unsafe_artifact_path', path='artifacts')
        elif directory.exists():
            for path in sorted(directory.rglob('*')):
                if path.is_symlink():
                    issue('unsafe_artifact_path', path=str(path.relative_to(root)))
                elif path.is_file():
                    disk_files[str(path.relative_to(root))] = _file_hash(path)
        for id, obj in records.items():
            if obj['_kind'] != 'artifact': continue
            relative = obj.get('path')
            safe = isinstance(relative, str) and relative.startswith('artifacts/') and not Path(relative).is_absolute()
            path = root / relative if safe else None
            safe = bool(safe and '..' not in Path(relative).parts and not directory.is_symlink()
                        and not path.is_symlink() and root in path.resolve().parents
                        and not any(p.is_symlink() for p in path.parents if p != root and root in p.parents))
            actual = disk_files.get(relative) if safe else None
            artifacts.append(dict(id=id, path=relative, expected_sha256=obj.get('sha256'), actual_sha256=actual))
            if not safe: issue('unsafe_artifact_path', id=id)
            elif actual is None or actual != obj.get('sha256'): issue('artifact_missing_or_hash_mismatch', id=id)
        referenced_paths = {x['path'] for x in artifacts}
        for relative in sorted(set(disk_files) - referenced_paths): issue('unreferenced_artifact', path=relative)
        after = _files(root)
        if before != after: issue('database_changed_during_inventory')
        row_hashes = {}
        for table, values in rows.items():
            row_hashes[table] = {json.dumps([x['id'], x['revision']]) if table == 'revisions' else str(x['id']): _hash(x)
                                 for x in values}
        snapshot = dict(schema_version=version, schema_hash=_hash(schema),
                        table_counts={k: len(v) for k, v in rows.items()}, row_hashes=row_hashes,
                        artifact_files=disk_files)
        return dict(report_version=REPORT_VERSION, observed_at=datetime.now(timezone.utc).isoformat(),
            data_dir=str(root), sqlite_files=after, source_files_stable=before == after,
            integrity=integrity, foreign_key_violations=foreign_keys, snapshot=snapshot,
            snapshot_sha256=_hash(snapshot), counts_by_kind={t: dict(Counter(x['kind'] for x in rows[t])) for t in ('current', 'records')},
            canonical_opportunities=canonical, company_candidates=company_candidates, company_conflicts=company_conflicts,
            submissions_by_opportunity=submissions, offers_by_opportunity=offers,
            multiple_submissions=multiple_submissions, multiple_offers=multiple_offers, interview_unknowns=interviews,
            references=refs, artifacts=artifacts, integrity_issues=issues,
            demo_legacy_findings=[x for x in findings if x['classification'] == 'demo_legacy'],
            migration_gates=[x for x in findings if x['classification'] != 'demo_legacy'],
            limitations=['Non-demo is not proof of real business facts.',
                         'Mappings are candidates only; no data has been migrated.',
                         'Historical rows are hashed in full; reference checks cover the listed current domain edges.'])
    finally:
        c.close()


def verify_restore(backup_dir, restored_dir):
    """Compare all schema-v1 rows and artifact bytes without opening either Store."""
    source, destination = _root(backup_dir), _root(restored_dir)
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('验证需两个独立目录')
    manifest = json.loads((source / 'manifest.json').read_text())
    a, b = inventory(source), inventory(destination)
    differences = []
    if a['snapshot'] != b['snapshot']: differences.append('snapshot')
    for name, report in (('backup', a), ('restored', b)):
        if report['integrity'] != ['ok'] or report['foreign_key_violations'] or report['integrity_issues']:
            differences.append(name + '_integrity')
        expected_files = dict(report['snapshot']['artifact_files'], **report['sqlite_files'])
        if manifest.get('schemaVersion') != 1 or manifest.get('files') != expected_files:
            differences.append(name + '_manifest')
    return dict(report_version=REPORT_VERSION, verified=not differences, differences=differences,
                backup_dir=str(source), restored_dir=str(destination),
                backup_snapshot_sha256=a['snapshot_sha256'], restored_snapshot_sha256=b['snapshot_sha256'],
                table_counts=b['snapshot']['table_counts'], checked_rows=sum(b['snapshot']['table_counts'].values()),
                artifact_count=len(b['artifacts']), backup_integrity=a['integrity'], restored_integrity=b['integrity'],
                reference_count=len(b['references']), reference_issues=b['integrity_issues'])


def write_report(output, report, protected_dirs):
    """Create a private report, refusing overwrite and writes into inspected roots."""
    path = Path(output).expanduser().absolute()
    resolved = path.resolve()
    if any(resolved == Path(p).resolve() or Path(p).resolve() in resolved.parents for p in protected_dirs):
        raise ValueError('报告必须写入受检数据目录之外')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')
