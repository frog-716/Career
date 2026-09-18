from batch_b_helpers import save_job
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.core import Conflict, Invalid, Missing, Store
from workbench.journey import journey_router
from workbench.providers import TestProvider


def client_for(tmp_path):
    store = Store(tmp_path, TestProvider())
    app = FastAPI(); app.state.store=store
    for cls, code in ((Invalid, 422), (Conflict, 409), (Missing, 404)):
        async def handle(request, exc, status=code):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": str(exc)}, status_code=status)
        app.add_exception_handler(cls, handle)
    app.include_router(journey_router(store))
    return TestClient(app), store


def make_job(store):
    return save_job(store,{"company": "虚构公司", "title": "研究员", "jd": "虚构 JD"})


def note(client, job, key="n1", content="原始私聊", submission_id=None):
    # Existing v1 interview raw fixture; B pauses NEW interviews, not corrections.
    from workbench.core import uid,now
    body=dict(id=uid(),scope_type='job',scope_id=job['id'],kind='interview',title='原始标题',content=content,idempotency_key=key,submission_id=submission_id,created_at=now())
    with client.app.state.store.connect() as db:client.app.state.store._record(db,'journey_note',body)
    return body



def test_correction_is_revisioned_and_original_note_immutable(tmp_path):
    c, store = client_for(tmp_path)
    job = make_job(store)
    n = note(c, job)
    corrected = c.post(f"/api/journey/notes/{n['id']}/correct", json={
        "expected_revision": 0, "title": "更正标题", "content": "更正选段",
        "idempotency_key": "corr-1",
    })
    assert corrected.status_code == 200
    assert corrected.json()["note_revision"] == 1
    shown = c.get("/api/journey").json()["notes"][0]
    assert shown["title"] == "更正标题" and shown["content"] == "更正选段"
    assert shown["original_content"] == "原始私聊" and shown["original_title"] == "原始标题"
    history = c.get(f"/api/journey/notes/{n['id']}/history").json()["revisions"]
    assert [r["revision"] for r in history] == [0, 1]
    assert history[0]["content"] == "原始私聊" and history[1]["content"] == "更正选段"
    with store.connect(False) as db:
        assert store._get(db, n["id"], "journey_note", True)["content"] == "原始私聊"
    assert c.post(f"/api/journey/notes/{n['id']}/correct", json={
        "expected_revision": 0, "title": "旧", "content": "旧", "idempotency_key": "corr-2",
    }).status_code == 409


def test_candidate_uses_selected_correction_and_origin_without_context_visibility(tmp_path):
    c, store = client_for(tmp_path)
    job = make_job(store)
    n = note(c, job, content="整份私聊：不要复制")
    c.post(f"/api/journey/notes/{n['id']}/correct", json={
        "expected_revision": 0, "title": "结论", "content": "只保留这一段",
        "idempotency_key": "corr-1",
    })
    body = {
        "expected_revision": 1, "title": "能力结论", "content": "用户整理后的选段",
        "entry_type": "experience", "scope_type": "job", "scope_id": job["id"],
        "promote_to_personal": False, "idempotency_key": "candidate-1",
    }
    created = c.post(f"/api/journey/notes/{n['id']}/candidate", json=body)
    assert created.status_code == 200, created.text
    candidate = created.json()
    assert candidate["status"] == "pending"
    state = store
    with state.connect(False) as db:
        source = state._get(db, candidate["source_ids"][0], "knowledge_source", True)
    assert source["content"] == "用户整理后的选段"
    assert "整份私聊" not in source["content"]
    assert source["origin"]["kind"] == "journey_note"
    assert source["origin"]["id"] == n["id"] and source["origin"]["revision"] == 1
    assert c.post(f"/api/journey/notes/{n['id']}/candidate", json=body).json() == candidate
    c.post(f"/api/journey/notes/{n['id']}/correct", json={
        "expected_revision": 1, "title": "再次更正", "content": "后来更正",
        "idempotency_key": "corr-2",
    })
    assert c.post(f"/api/journey/notes/{n['id']}/candidate", json=body).json() == candidate


def test_candidate_requires_explicit_personal_promotion_and_submission_matches_job(tmp_path):
    c, store = client_for(tmp_path)
    job = make_job(store)
    other = make_job(store)
    with store.connect() as db:
        db.execute("INSERT INTO records VALUES(?,?,?)", ("v", "version", '{"id":"v"}'))
        db.execute("INSERT INTO records VALUES(?,?,?)", ("a", "artifact", '{"id":"a"}'))
        from batch_c_helpers import insert_legacy_application
        insert_legacy_application(db, ("sub-1", job["id"], "v", "a", "k", '{"id":"sub-1","job_id":"'+job["id"]+'"}'))
    n = note(c, job, submission_id="sub-1")
    common = {"expected_revision": 0, "title": "结论", "content": "选段",
              "entry_type": "experience", "scope_type": "personal", "scope_id": "",
              "promote_to_personal": False, "idempotency_key": "bad-cross"}
    assert c.post(f"/api/journey/notes/{n['id']}/candidate", json=common).status_code == 422
    promoted = dict(common, promote_to_personal=True, idempotency_key="good-cross")
    assert c.post(f"/api/journey/notes/{n['id']}/candidate", json=promoted).status_code == 200
    bad = dict(promoted, idempotency_key="bad-job", scope_type="job", scope_id=other["id"], promote_to_personal=False)
    assert c.post(f"/api/journey/notes/{n['id']}/candidate", json=bad).status_code == 422
    linked = dict(promoted, idempotency_key="linked")
    assert c.post(f"/api/journey/notes/{n['id']}/candidate", json=linked).status_code == 200
    wrong = dict(promoted, idempotency_key="wrong-link", submission_id="missing")
    assert c.post(f"/api/journey/notes/{n['id']}/candidate", json=wrong).status_code == 409


def test_episode_export_has_consistent_full_correction_snapshot(tmp_path):
    c, store = client_for(tmp_path)
    episode = c.post("/api/journey/episodes", json={"company": "虚构公司", "role": "研究员", "focus": "阶段"}).json()
    n = c.post("/api/journey/notes", json={
        "scope_type": "episode", "scope_id": episode["id"], "kind": "reflection",
        "title": "原题", "content": "原文", "idempotency_key": "episode-note",
    }).json()
    c.post(f"/api/journey/notes/{n['id']}/correct", json={
        "expected_revision": 0, "title": "改题", "content": "完整更正正文",
        "idempotency_key": "episode-correction",
    })
    exported = c.get(f"/api/journey/episodes/{episode['id']}/export")
    assert exported.status_code == 200
    assert "原始记录（不可变）：\n原文" in exported.text
    assert "revision 1" in exported.text and "完整更正正文" in exported.text
