"""Predeclared T01/T03/T08/T09/T10/T13 failure and provenance contracts."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest
from test_record_submitted import client_at, opportunity, start, save, version, submit, post, PDF
from workbench.core import Store, digest
from workbench.providers import TestProvider
from workbench.resume_artifacts import ArtifactError


@pytest.mark.parametrize('point',['after_stage','after_rename','after_version','after_submission','before_commit','after_commit'])
def test_real_process_interruption_and_recovery(tmp_path,point):
    c,s=client_at(tmp_path/'data');o=opportunity(c,'进程中断');d=save(c,start(c,o),'虚构稿')
    body=dict(expected_revision=o['revision'],idempotency_key='crash',resume=dict(mode='draft',document_id=d['document_id'],expected_document_revision=d['revision'],document=d['document'],pdf_base64=PDF))
    request=tmp_path/'request.json';request.write_text(json.dumps(body))
    code='''import json,os,sys
from workbench.core import Store
from workbench.providers import TestProvider
from workbench.submission import record_submitted
from workbench import resume_artifacts
s=Store(sys.argv[1],TestProvider())
resume_artifacts.fault=lambda point: os._exit(73) if point==sys.argv[4] else None
record_submitted(s,sys.argv[2],json.load(open(sys.argv[3])))
'''
    env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    result=subprocess.run([sys.executable,'-c',code,str(s.data_dir),o['id'],str(request),point],env=env,capture_output=True)
    assert result.returncode==73,result.stderr
    reopened=Store(s.data_dir,TestProvider());state=reopened.state()
    committed=point=='after_commit'
    assert len(state['applications'])==int(committed)
    assert state['opportunities'][0]['phase']==('submitted' if committed else 'resume')
    assert len(state['artifacts'])==int(committed)
    assert len(list((s.data_dir/'artifacts').glob('*')))==int(committed)
    retry=submit(c,o,body['resume'],'crash');assert retry.status_code==200,retry.text
    assert len(reopened.state()['applications'])==1
    for a in reopened.state()['artifacts']:reopened.artifact(a['id'])


def test_db_exception_and_corrupt_pdf_fail_closed(tmp_path,monkeypatch):
    from workbench import resume_artifacts
    c,s=client_at(tmp_path);o=opportunity(c,'失败');d=start(c,o)
    req=dict(mode='draft',document_id=d['document_id'],expected_document_revision=d['revision'],document=d['document'],pdf_base64=PDF)
    def fail(p):
        if p=='after_submission':raise RuntimeError('database transaction failed')
    monkeypatch.setattr(resume_artifacts,'fault',fail)
    with pytest.raises(RuntimeError):submit(c,o,req)
    assert s.state()['applications']==[] and s.state()['artifacts']==[]
    assert s.state()['opportunities'][0]['phase']=='resume'
    monkeypatch.setattr(resume_artifacts,'fault',lambda point:None)
    result=submit(c,o,req).json();a=result['submission']['artifact_snapshot']
    (s.data_dir/a['path']).write_bytes(b'corrupt')
    assert c.get('/api/artifacts/'+a['id']).status_code==422
    with pytest.raises(ArtifactError):Store(s.data_dir,TestProvider())


def test_explicit_source_copy_and_stale_profile(tmp_path):
    c,s=client_at(tmp_path);a=opportunity(c,'来源');d=save(c,start(c,a),'来源表达');v=version(c,d)
    b=opportunity(c,'复制');copied=start(c,b,dict(kind='version',source_version_id=v['id'],source_document_hash=digest(v['document'])))
    assert copied['document']['profile']['name']=='来源表达' and copied['document_id']!=d['document_id']
    # A real legacy-shaped source is stored only as a test fixture, never assigned ownership.
    with s.connect() as con:con.execute('INSERT INTO current VALUES(?,?,?,?)',('editor-main','editor_draft',4,json.dumps(dict(id='editor-main',document=d['document']))))
    legacy=opportunity(c,'旧稿复制');legacy_copy=start(c,legacy,dict(kind='legacy_draft',source_revision=4,source_hash=digest(d['document'])))
    assert legacy_copy['document']['profile']['name']=='来源表达'
    p=post(c,'/profile/basics',dict(expected_revision=0,basics=dict(name='新事实',phone='',email='')))
    p2=post(c,'/profile/basics',dict(expected_revision=p['revision'],basics=dict(name='更新事实',phone='',email='')))
    r=c.post('/api/resume-documents/'+copied['document_id']+'/select-facts',json=dict(expected_revision=copied['revision'],profile_revision=p['revision'],include_profile=True,selections=[],idempotency_key='stale'))
    assert r.status_code==409
    assert c.get('/api/resume-documents/'+copied['document_id']).json()==copied
    assert c.get('/api/editor').json()['revision']==4
    with s.connect(False) as con:assert s._get(con,v['id'],'editor_version',True)['document_id']==d['document_id']


def test_frozen_db_constraints_and_no_second_application_null_bypass(tmp_path):
    c,s=client_at(tmp_path);o=opportunity(c,'不可变');d=start(c,o)
    result=submit(c,o,dict(mode='draft',document_id=d['document_id'],expected_document_revision=d['revision'],document=d['document'],pdf_base64=PDF)).json()
    with pytest.raises(sqlite3.IntegrityError):
        with s.connect() as con:con.execute('DELETE FROM records WHERE id=?',(result['submission_version']['id'],))
    with pytest.raises(sqlite3.IntegrityError):
        with s.connect() as con:con.execute("UPDATE applications SET body='{}'")
    with pytest.raises(sqlite3.IntegrityError):
        with s.connect() as con:con.execute("INSERT INTO applications VALUES('attack','alias',NULL,NULL,'key','{}',NULL)")


@pytest.mark.parametrize('reference',['resume_use','shared_artifact'])
def test_ordinary_delete_checks_other_owners(tmp_path,reference):
    c,s=client_at(tmp_path);o=opportunity(c,'引用');d=start(c,o);v=version(c,d)
    with s.connect() as con:
        if reference=='resume_use':s._record(con,'resume_use',dict(id='use',version_id=v['id']))
        else:
            a=s._get(con,v['artifact_id'],'artifact',True)
            s._record(con,'artifact',dict(a,id='shared',version_id='another-version'))
    assert c.delete('/api/resume-documents/'+d['document_id']+'/versions/'+v['id']).status_code==409
    assert c.get('/api/artifacts/'+v['artifact_id']).status_code==200


@pytest.mark.parametrize('point',['after_delete','after_commit'])
def test_real_delete_interruption_preserves_references(tmp_path,point):
    c,s=client_at(tmp_path/'data');o=opportunity(c,'删除中断');d=start(c,o);v=version(c,d)
    code='''import os,sys
from fastapi.testclient import TestClient
from workbench.core import Store
from workbench.app import create_app
from workbench.providers import TestProvider
from workbench import resume_artifacts
s=Store(sys.argv[1],TestProvider())
resume_artifacts.fault=lambda p: os._exit(73) if p==sys.argv[4] else None
TestClient(create_app(s),headers={'X-Career-Request':'1','Content-Type':'application/json'}).delete('/api/resume-documents/'+sys.argv[2]+'/versions/'+sys.argv[3])
'''
    env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    result=subprocess.run([sys.executable,'-c',code,str(s.data_dir),d['document_id'],v['id'],point],env=env,capture_output=True)
    assert result.returncode==73,result.stderr
    reopened=Store(s.data_dir,TestProvider())
    expected=1 if point=='after_delete' else 0
    assert len(reopened.state()['artifacts'])==expected
    assert len(list((s.data_dir/'artifacts').glob('*')))==expected
    for a in reopened.state()['artifacts']:reopened.artifact(a['id'])


def test_startup_cannot_quarantine_another_process_pending_pdf(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event
    from workbench import resume_artifacts
    c,s=client_at(tmp_path);o=opportunity(c,'启动与投递并发');d=start(c,o)
    renamed=Event();release=Event()
    def pause(point):
        if point=='after_rename':renamed.set();assert release.wait(5)
    monkeypatch.setattr(resume_artifacts,'fault',pause)
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer=pool.submit(submit,c,o,dict(mode='draft',document_id=d['document_id'],expected_document_revision=d['revision'],document=d['document'],pdf_base64=PDF))
        assert renamed.wait(3)
        opener=pool.submit(Store,s.data_dir,TestProvider())
        try:
            with pytest.raises(TimeoutError):opener.result(timeout=.1)
        finally:release.set()
        result=writer.result();assert result.status_code==200,result.text
        opened=opener.result()
    assert len(opened.state()['applications'])==1
    for a in opened.state()['artifacts']:opened.artifact(a['id'])
