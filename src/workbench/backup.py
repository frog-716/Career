"""Explicit local backup; restore only to a new directory, never overwrite data."""
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path
from .core import Invalid, ROOT
from .artifacts import read_artifact

def _outside(path):
    p=Path(path).expanduser().resolve()
    if p==ROOT or ROOT in p.parents:raise Invalid('备份与数据目录必须在代码目录外')
    return p


def _artifact_records(connection):
    """Return the artifact path/hash pairs, rejecting ambiguous metadata."""
    records = {}
    for (body,) in connection.execute("SELECT body FROM records WHERE kind='artifact'"):
        try:
            artifact = json.loads(body)
            path, digest = artifact['path'], artifact['sha256']
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise Invalid('附件记录缺少路径或哈希，备份未完成') from exc
        if not isinstance(path, str) or not isinstance(digest, str):
            raise Invalid('附件记录缺少路径或哈希，备份未完成')
        if path in records and records[path] != digest:
            raise Invalid('多个附件记录使用同一路径但哈希不同，备份未完成')
        records[path] = digest
    return records


def _listed_artifact_files(root):
    directory = root / 'artifacts'
    if not directory.exists():
        return set()
    if directory.is_symlink() or not directory.is_dir():
        raise Invalid('附件目录无效')
    files = set()
    for path in directory.rglob('*'):
        if path.is_symlink() or not path.is_file():
            raise Invalid('附件目录包含无效文件')
        files.add(str(path.relative_to(root)))
    return files


def _validate_manifest_against_db(root, manifest, artifact_records):
    files = manifest.get('files')
    if not isinstance(files, dict) or 'workspace.sqlite3' not in files:
        raise Invalid('备份清单版本不支持')
    listed = {path: digest for path, digest in files.items() if path != 'workspace.sqlite3'}
    expected = set(artifact_records)
    if set(listed) != expected:
        missing = sorted(expected - set(listed))
        extra = sorted(set(listed) - expected)
        detail = []
        if missing: detail.append('清单遗漏附件：' + ', '.join(missing))
        if extra: detail.append('清单包含未引用附件：' + ', '.join(extra))
        raise Invalid('；'.join(detail) or '附件清单与数据库不一致')
    on_disk = _listed_artifact_files(root)
    if on_disk != set(listed):
        missing = sorted(set(listed) - on_disk)
        extra = sorted(on_disk - set(listed))
        detail = []
        if missing: detail.append('备份缺少附件文件：' + ', '.join(missing))
        if extra: detail.append('发现未列入清单的孤儿附件：' + ', '.join(extra))
        raise Invalid('；'.join(detail) or '附件文件与清单不一致')
    for path, digest in artifact_records.items():
        if listed[path] != digest:
            raise Invalid('附件清单哈希与数据库记录不一致：' + path)
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != digest:
            raise Invalid('附件文件哈希校验失败：' + path)

def backup(data_dir,output_dir,backup_name=None):
    source=_outside(data_dir);output=_outside(output_dir)
    if not (source/'workspace.sqlite3').is_file():raise Invalid('源数据库不存在')
    output.mkdir(parents=True,exist_ok=True,mode=0o700)
    staging=Path(tempfile.mkdtemp(prefix='.partial-',dir=str(output)))
    if backup_name is not None:
        if not isinstance(backup_name, str) or not backup_name or Path(backup_name).name != backup_name:
            raise Invalid('备份名称不合法')
        final=output/backup_name
    else:
        final=output/('career-backup-'+str(uuid.uuid4()))
    try:
        # Hold a SQLite write reservation while taking the DB snapshot and
        # collecting its referenced files. This gives the two halves one
        # stable application write window; file bytes are copied from the
        # bytes read in that window rather than reread after the snapshot.
        with sqlite3.connect(str(source/'workspace.sqlite3'), timeout=15) as locker:
            locker.execute('BEGIN IMMEDIATE')
            # The lock connection reserves the write window; a separate read
            # connection is required because sqlite's backup API waits when
            # its source connection itself owns a write transaction.
            with sqlite3.connect(str(source/'workspace.sqlite3'), timeout=15) as src, sqlite3.connect(str(staging/'workspace.sqlite3')) as dest:
                src.backup(dest)
            with sqlite3.connect(str(staging/'workspace.sqlite3')) as snapshot:
                artifact_records = _artifact_records(snapshot)
            manifest={'schemaVersion':1,'files':{}}
            for path, digest in artifact_records.items():
                original=read_artifact(source,path)
                data=original.read_bytes()
                if hashlib.sha256(data).hexdigest()!=digest:
                    raise Invalid('附件文件哈希与数据库记录不一致：' + path)
                target=staging/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
                if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                    raise Invalid('附件复制后哈希校验失败：' + path)
                manifest['files'][path]=digest
            manifest['files']['workspace.sqlite3']=hashlib.sha256((staging/'workspace.sqlite3').read_bytes()).hexdigest()
            if _listed_artifact_files(source) != set(artifact_records):
                raise Invalid('发现未列入数据库的孤儿附件，备份未完成')
            locker.commit()
        (staging/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        os.rename(staging,final);return final
    except Exception:
        shutil.rmtree(staging);raise

def restore(backup_dir,destination):
    source=_outside(backup_dir);dest=_outside(destination)
    if dest.exists():raise Invalid('恢复目标必须是不存在的新目录，不会覆盖已有数据')
    manifest=json.loads((source/'manifest.json').read_text())
    if manifest.get('schemaVersion')!=1 or 'workspace.sqlite3' not in manifest.get('files',{}):raise Invalid('备份清单版本不支持')
    database = source/'workspace.sqlite3'
    if hashlib.sha256(database.read_bytes()).hexdigest() != manifest['files']['workspace.sqlite3']:
        raise Invalid('备份数据库哈希校验失败')
    with sqlite3.connect(str(database)) as c:
        if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise Invalid('备份数据库损坏')
        source_artifacts = _artifact_records(c)
    _validate_manifest_against_db(source, manifest, source_artifacts)
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.career-restore-',dir=str(dest.parent)))
    try:
        for relative,hash in manifest['files'].items():
            p=(source/relative).resolve()
            if source not in p.parents or (relative!='workspace.sqlite3' and not relative.startswith('artifacts/')):raise Invalid('备份路径越界')
            data=p.read_bytes()
            if hashlib.sha256(data).hexdigest()!=hash:raise Invalid('备份哈希校验失败')
            target=stage/relative
            if stage not in target.resolve().parents:raise Invalid('恢复路径越界')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        with sqlite3.connect(str(stage/'workspace.sqlite3')) as c:
            if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise Invalid('备份数据库损坏')
            artifact_records = _artifact_records(c)
        _validate_manifest_against_db(stage, manifest, artifact_records)
        os.rename(stage,dest)
    except Exception:
        shutil.rmtree(stage);raise
