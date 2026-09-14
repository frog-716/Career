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

def backup(data_dir,output_dir):
    source=_outside(data_dir);output=_outside(output_dir)
    if not (source/'workspace.sqlite3').is_file():raise Invalid('源数据库不存在')
    output.mkdir(parents=True,exist_ok=True,mode=0o700)
    staging=Path(tempfile.mkdtemp(prefix='.partial-',dir=str(output)))
    final=output/('career-backup-'+str(uuid.uuid4()))
    try:
        with sqlite3.connect('file:'+str(source/'workspace.sqlite3')+'?mode=ro',uri=True) as src,sqlite3.connect(str(staging/'workspace.sqlite3')) as dest:
            src.backup(dest)
        manifest={'schemaVersion':1,'files':{}}
        with sqlite3.connect(str(staging/'workspace.sqlite3')) as c:
            for row in c.execute("SELECT body FROM records WHERE kind='artifact'"):
                a=json.loads(row[0]);original=read_artifact(source,a['path'])
                if hashlib.sha256(original.read_bytes()).hexdigest()!=a['sha256']:raise Invalid('附件校验失败，备份未完成')
                target=staging/a['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
                manifest['files'][a['path']]=a['sha256']
        manifest['files']['workspace.sqlite3']=hashlib.sha256((staging/'workspace.sqlite3').read_bytes()).hexdigest()
        (staging/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        os.rename(staging,final);return final
    except Exception:
        shutil.rmtree(staging);raise

def restore(backup_dir,destination):
    source=_outside(backup_dir);dest=_outside(destination)
    if dest.exists():raise Invalid('恢复目标必须是不存在的新目录，不会覆盖已有数据')
    manifest=json.loads((source/'manifest.json').read_text())
    if manifest.get('schemaVersion')!=1 or 'workspace.sqlite3' not in manifest.get('files',{}):raise Invalid('备份清单版本不支持')
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
        os.rename(stage,dest)
    except Exception:
        shutil.rmtree(stage);raise
