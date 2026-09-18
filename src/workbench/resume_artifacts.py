"""Resume PDF staging. SQLite references are the commit record; no file WAL.

All callers hold Store's SQLite write reservation while moving files. A crash
before COMMIT can leave only a recognizable unreferenced c-resume file. Recovery
quarantines those files, never reconstructs business facts or deletes legacy data.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from .artifacts import ArtifactError, read_artifact

_FINAL = re.compile(r'c-resume-[0-9a-f-]{36}-[0-9a-f]{64}\.pdf$')


def fault(point):
    """Failure injection seam; production never reads an injection env var."""


def directory(root, name):
    p = Path(root)/name
    if p.is_symlink(): raise ArtifactError('附件目录不能是符号链接')
    p.mkdir(exist_ok=True, mode=0o700)
    return p


def sync_dir(path):
    fd=os.open(path, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def checked_bytes(root, artifact):
    p=read_artifact(root, artifact['path'])
    data=p.read_bytes()
    if hashlib.sha256(data).hexdigest()!=artifact['sha256']:
        raise ArtifactError('PDF hash不匹配，禁止使用该附件')
    return data


def recover(c, root):
    refs={}
    for row in c.execute("SELECT body FROM records WHERE kind='artifact'"):
        a=json.loads(row[0]);checked_bytes(root,a);refs[a['path']]=a['sha256']
    moved=[]
    artifacts=Path(root)/'artifacts'
    if artifacts.is_symlink():raise ArtifactError('附件目录不能是符号链接')
    stage=Path(root)/'resume-staging'
    if stage.is_symlink():raise ArtifactError('暂存目录不能是符号链接')
    candidates=[]
    if artifacts.exists():
        candidates += [p for p in artifacts.iterdir() if _FINAL.fullmatch(p.name) and 'artifacts/'+p.name not in refs]
    if stage.exists():candidates += list(stage.iterdir())
    for p in candidates:
        if p.is_symlink() or not p.is_file():raise ArtifactError('暂存/孤儿路径不安全')
        quarantine=directory(root,'resume-quarantine')
        target=quarantine/(str(uuid.uuid4())+'-'+p.name)
        os.replace(p,target);sync_dir(p.parent);sync_dir(quarantine);moved.append(p.name)
    return moved


def stage_pdf(root, aid, vid, raw, created):
    stage=directory(root,'resume-staging');final=directory(root,'artifacts')
    sha=hashlib.sha256(raw).hexdigest()
    pending=stage/(aid+'.pdf')
    with pending.open('xb') as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    sync_dir(stage);fault('after_stage')
    target=final/('c-resume-'+aid+'-'+sha+'.pdf')
    if target.exists():raise ArtifactError('附件目标已存在')
    os.replace(pending,target);sync_dir(stage);sync_dir(final);fault('after_rename')
    a=dict(id=aid,version_id=vid,path='artifacts/'+target.name,sha256=sha,
           media_type='application/pdf',size=len(raw),created_at=created)
    checked_bytes(root,a)
    return a
