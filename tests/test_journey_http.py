from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.backup import backup, restore
from workbench.core import Store
from workbench.providers import TestProvider


def test_same_origin_journey_survives_backup_restore(tmp_path):
    store = Store(tmp_path / "source", TestProvider())
    client = TestClient(create_app(store))
    body = {"company": "虚构工作期", "role": "研究员", "focus": "记录证据"}
    assert client.post("/api/journey/episodes", json=body).status_code == 403
    headers = {"X-Career-Request": "1"}
    assert client.post("/api/journey/episodes", json=body,
                       headers=dict(headers, Origin="https://example.com")).status_code == 403
    episode = client.post("/api/journey/episodes", json=body, headers=headers).json()
    note = client.post("/api/journey/notes", headers=headers, json={
        "scope_type": "episode", "scope_id": episode["id"],
        "kind": "reflection", "title": "阶段收获",
        "content": "  虚构记录：先确认问题，再核对结果。  ", "idempotency_key": "restore-note"
    })
    assert note.status_code == 200
    before = client.get("/api/journey").json()
    bundle = backup(store.data_dir, tmp_path / "backups")
    restore(bundle, tmp_path / "restored")
    restored = TestClient(create_app(Store(tmp_path / "restored", TestProvider())))
    assert restored.get("/api/journey").json() == before
    assert before["notes"][0]["content"].startswith("  ")
    exported = restored.get("/api/journey/episodes/" + episode["id"] + "/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["Content-Disposition"]
    assert "用户记录汇编（非 AI 总结）" in exported.text
    assert before["notes"][0]["content"] in exported.text
