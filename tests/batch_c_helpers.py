"""Explicit synthetic document binding and legacy SQL fixtures, never shipped runtime."""
import json
import sqlite3
import uuid
from fastapi.testclient import TestClient
from workbench.app import create_app
from workbench.opportunity import create_opportunity
from workbench.resume_schema import install


def editor_client(store):
    c=TestClient(create_app(store),headers={'X-Career-Request':'1','Content-Type':'application/json'})
    bind_editor(c,store)
    return c


def bind_editor(c,store,owner=None):
    o=owner or create_opportunity(store,dict(company_name='Synthetic Editor Owner',title='Resume',jd='Synthetic JD',idempotency_key=str(uuid.uuid4())))
    r=c.post('/api/opportunities/'+o['id']+'/resume/start',json=dict(expected_opportunity_revision=o['revision'],idempotency_key='start-fixture',source={'kind':'blank'}),headers={'X-Career-Request':'1'})
    assert r.status_code==200,r.text
    c.editor_path='/api/resume-documents/'+r.json()['document_id']
    c.editor_id=r.json()['document_id'];c.editor_op=o
    return c


def legacy_storage(store,version=2):
    """Make the original six-column schema explicitly for old-data tests."""
    with sqlite3.connect(store.db) as c:
        for name, in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():c.execute('DROP TRIGGER '+name)
        for index in ('submission_owner','resume_owner','interview_preparation_owner',
                      'interview_raw_owner','interview_review_owner','opportunity_research_owner'):
            c.execute('DROP INDEX IF EXISTS '+index)
        c.execute('ALTER TABLE applications RENAME TO test_applications_new')
        c.execute('CREATE TABLE applications(id TEXT PRIMARY KEY,job_id TEXT NOT NULL,version_id TEXT NOT NULL REFERENCES records(id),artifact_id TEXT NOT NULL REFERENCES records(id),idempotency_key TEXT NOT NULL UNIQUE,body TEXT NOT NULL)')
        c.execute('INSERT INTO applications SELECT id,job_id,version_id,artifact_id,idempotency_key,body FROM test_applications_new')
        c.execute('DROP TABLE test_applications_new');c.execute('PRAGMA user_version='+str(version))


def insert_legacy_application(c,values):
    """Import-shaped fixture in v3; production insert guard restored in same txn."""
    columns=len(c.execute('PRAGMA table_info(applications)').fetchall())
    if columns==6:c.execute('INSERT INTO applications VALUES(?,?,?,?,?,?)',values);return
    c.execute('DROP TRIGGER submission_insert')
    c.execute('INSERT INTO applications VALUES(?,?,?,?,?,?,NULL)',values)
    install(c)
