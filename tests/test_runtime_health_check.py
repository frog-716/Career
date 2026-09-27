import json
import sqlite3

from scripts import runtime_health_check


def test_runtime_health_check_reads_only_whitelisted_metadata(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / ".career-instance").write_text("a" * 32, encoding="utf-8")
    db_path = data_dir / "workspace.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.executescript("""
        CREATE TABLE current (id TEXT PRIMARY KEY, kind TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL);
        CREATE TABLE records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL);
        CREATE TABLE revisions (id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL);
        PRAGMA user_version=6;
    """)
    connection.execute("insert into current values(?,?,?,?)", (
        "profile", "profile", 1,
        json.dumps({"name": "PROFILE_CANARY_NAME", "email": "PROFILE_CANARY_EMAIL", "phone": "PROFILE_CANARY_PHONE"}),
    ))
    connection.execute("insert into current values(?,?,?,?)", (
        "resume-canary", "resume_document", 3,
        json.dumps({"content": "RESUME_CANARY_BODY"}),
    ))
    connection.execute("insert into current values(?,?,?,?)", (
        "person-canary", "work_person", 2,
        json.dumps({"name": "PERSON_CANARY_NAME", "role": "PERSON_CANARY_ROLE"}),
    ))
    connection.execute("insert into records values(?,?,?)", (
        "record-canary", "raw_material", json.dumps({"content": "RAW_CANARY_BODY"}),
    ))
    connection.execute("insert into revisions values(?,?,?,?)", (
        "resume-canary", 3, json.dumps({"content": "RESUME_REVISION_CANARY"}), "2026-09-27T00:00:00Z",
    ))
    connection.commit()
    connection.close()

    read_columns = []
    original_connect = sqlite3.connect

    def guarded_connect(*args, **kwargs):
        db = original_connect(*args, **kwargs)
        def authorize(action, table, column, _database, _source):
            if action == sqlite3.SQLITE_READ:
                read_columns.append((table, column))
                if column == "body":
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        db.set_authorizer(authorize)
        return db

    monkeypatch.setattr(runtime_health_check.sqlite3, "connect", guarded_connect)
    requested_urls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self):
            return json.dumps({
                "status": "ok", "build_id": "test-build",
                "profile": {"email": "HEALTH_RESPONSE_CANARY"},
            }).encode()

    def safe_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        return Response()

    monkeypatch.setattr(runtime_health_check.urllib.request, "urlopen", safe_urlopen)
    result = runtime_health_check.collect_runtime_health(
        "http://127.0.0.1:8765", data_dir,
    )

    serialized = json.dumps(result, ensure_ascii=False)
    for canary in (
        "PROFILE_CANARY_NAME", "PROFILE_CANARY_EMAIL", "PROFILE_CANARY_PHONE",
        "RESUME_CANARY_BODY", "PERSON_CANARY_NAME", "PERSON_CANARY_ROLE",
        "RAW_CANARY_BODY", "RESUME_REVISION_CANARY", "HEALTH_RESPONSE_CANARY",
        "profile", "resume-canary", "person-canary", "record-canary",
    ):
        assert canary not in serialized
    assert requested_urls == ["http://127.0.0.1:8765/healthz"]
    assert result["health"] == {"status": "ok", "build_id": "test-build"}
    assert result["database"]["schema_version"] == 6
    assert result["database"]["quick_check"] == "ok"
    assert result["database"]["data_instance_id"] == "a" * 32
    assert result["database"]["row_counts"] == {"current": 3, "records": 1, "revisions": 1}
    assert result["database"]["revision_count"] == 1
    assert len(result["database"]["id_manifest_sha256"]) == 64
    assert read_columns
    assert all(column != "body" for _table, column in read_columns)
