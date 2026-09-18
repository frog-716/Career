"""Schema v3 constraints shared by empty-store creation and explicit migration."""
APPLICATIONS = '''CREATE TABLE applications (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
 version_id TEXT REFERENCES records(id), artifact_id TEXT REFERENCES records(id),
 idempotency_key TEXT NOT NULL UNIQUE, body TEXT NOT NULL,
 canonical_opportunity_id TEXT REFERENCES current(id),
 CHECK ((version_id IS NULL) = (artifact_id IS NULL)))'''

STATEMENTS = [
 "CREATE UNIQUE INDEX IF NOT EXISTS resume_owner ON current(json_extract(body,'$.opportunity_id')) WHERE kind='resume_document'",
 "CREATE UNIQUE INDEX IF NOT EXISTS submission_owner ON applications(canonical_opportunity_id) WHERE canonical_opportunity_id IS NOT NULL",
 '''CREATE TRIGGER IF NOT EXISTS submission_insert BEFORE INSERT ON applications BEGIN
 SELECT CASE WHEN NEW.canonical_opportunity_id IS NULL OR
 NOT EXISTS(SELECT 1 FROM current WHERE id=NEW.canonical_opportunity_id AND kind='opportunity' AND json_extract(body,'$.format_version')=2)
 OR json_extract(NEW.body,'$.submission_format') IS NOT 3
 OR json_extract(NEW.body,'$.opportunity_id') IS NOT NEW.canonical_opportunity_id
 OR json_extract(NEW.body,'$.version_id') IS NOT NEW.version_id
 OR json_extract(NEW.body,'$.artifact_id') IS NOT NEW.artifact_id
 THEN RAISE(ABORT,'canonical Submission required') END;
 END''',
 '''CREATE TRIGGER IF NOT EXISTS submission_frozen BEFORE UPDATE ON applications
 BEGIN SELECT RAISE(ABORT,'Submission is immutable'); END''',
 '''CREATE TRIGGER IF NOT EXISTS submission_delete BEFORE DELETE ON applications
 BEGIN SELECT RAISE(ABORT,'Submission is immutable'); END''',
 '''CREATE TRIGGER IF NOT EXISTS submission_version_update BEFORE UPDATE ON records
 WHEN OLD.kind='editor_version' AND json_extract(OLD.body,'$.version_kind')='submission'
 BEGIN SELECT RAISE(ABORT,'Submission version is immutable'); END''',
 '''CREATE TRIGGER IF NOT EXISTS submission_version_delete BEFORE DELETE ON records
 WHEN OLD.kind='editor_version' AND json_extract(OLD.body,'$.version_kind')='submission'
 BEGIN SELECT RAISE(ABORT,'Submission version is immutable'); END''',
 '''CREATE TRIGGER IF NOT EXISTS resume_owner_fixed BEFORE UPDATE ON current
 WHEN OLD.kind='resume_document' AND (NEW.kind!=OLD.kind OR json_extract(NEW.body,'$.opportunity_id') IS NOT json_extract(OLD.body,'$.opportunity_id'))
 BEGIN SELECT RAISE(ABORT,'Resume owner is immutable'); END''',
]

def install(c):
    for sql in STATEMENTS:c.execute(sql)
