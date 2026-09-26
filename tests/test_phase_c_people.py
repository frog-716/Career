import json

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from workbench.core import Conflict, Invalid, Missing, Store
from workbench.journey import journey_router
from workbench.providers import TestProvider
from workbench.work import work_router


def client_for(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    app = FastAPI()
    for cls, code in ((Invalid, 422), (Conflict, 409), (Missing, 404)):
        async def handle(request, exc, status=code):
            return JSONResponse({"detail": str(exc)}, status_code=status)
        app.add_exception_handler(cls, handle)
    app.include_router(journey_router(store))
    app.include_router(work_router(store))
    return TestClient(app), store


def create_employment(client, company):
    episode = client.post("/api/journey/episodes", json={
        "company": company, "role": "虚构岗位", "focus": "仅供 Phase C 测试",
    }).json()
    employment = next(
        item for item in client.get("/api/work-domain").json()["employments"]
        if item["legacy_episode_id"] == episode["id"]
    )
    return episode, employment


def create_person(client, employment, key, **values):
    return client.post(
        f"/api/work/employments/{employment['id']}/persons",
        json={"name": "虚构同事", "idempotency_key": key, **values},
    )


def update_person(client, employment, person, body):
    return client.post(
        f"/api/work/employments/{employment['id']}/persons/{person['id']}",
        json=body,
    )


def create_project(client, key, employment_id=None):
    return client.post("/api/work/projects", json={
        "name": "虚构项目", "employment_id": employment_id,
        "idempotency_key": key,
    })


def test_person_is_employment_scoped_and_manual_creation_confirms_identity(tmp_path):
    client, _ = client_for(tmp_path)
    _, employment_a = create_employment(client, "虚构公司甲")
    _, employment_b = create_employment(client, "虚构公司乙")

    first = create_person(client, employment_a, "person-a", role="直属领导")
    same_name = create_person(client, employment_b, "person-b", role="技术负责人")
    assert first.status_code == same_name.status_code == 200
    first, same_name = first.json(), same_name.json()
    assert first["employment_id"] == employment_a["id"]
    assert first["identity_status"] == "confirmed"
    assert first["role"] == "直属领导"
    assert same_name["employment_id"] == employment_b["id"]
    assert same_name["identity_status"] == "confirmed"
    assert first["id"] != same_name["id"]

    assert create_person(client, employment_a, "person-a", role="直属领导").json() == first
    assert create_person(client, employment_a, "person-a", role="别的人").status_code == 409
    assert client.post("/api/work/persons", json={
        "name": "不允许的全局人物", "idempotency_key": "global-person",
    }).status_code == 404


def test_raw_name_mentions_never_create_or_match_person_even_when_repeated(tmp_path):
    client, store = client_for(tmp_path)
    episode, employment = create_employment(client, "虚构公司")
    for index in range(2):
        response = client.post("/api/journey/notes", json={
            "scope_type": "episode", "scope_id": episode["id"],
            "kind": "collaboration", "title": "虚构协作原文",
            "content": "小王说这个方案有风险。",
            "idempotency_key": f"raw-mention-{index}",
        })
        assert response.status_code == 200

    domain = client.get("/api/work-domain").json()
    assert domain["persons"] == []
    person = client.post(f"/api/work/employments/{employment['id']}/persons", json={
        "name": "小王", "role": "直属领导", "idempotency_key": "manual-xiaowang",
    }).json()
    for index in range(2, 4):
        response = client.post("/api/journey/notes", json={
            "scope_type": "episode", "scope_id": episode["id"],
            "kind": "collaboration", "title": "虚构协作原文",
            "content": "小王说这个方案有风险。",
            "idempotency_key": f"raw-mention-{index}",
        })
        assert response.status_code == 200
    after_mentions = client.get("/api/work-domain").json()["persons"]
    assert after_mentions == [person]
    with store.connect(False) as db:
        assert db.execute("SELECT COUNT(*) FROM current WHERE kind='work_person'").fetchone()[0] == 1


def test_unresolved_person_is_not_selectable_until_user_confirms_identity(tmp_path):
    client, _ = client_for(tmp_path)
    _, employment = create_employment(client, "虚构公司")
    unresolved = create_person(
        client, employment, "unresolved-person", identity_status="unresolved",
    )
    assert unresolved.status_code == 200
    person = unresolved.json()
    assert person["identity_status"] == "unresolved"
    project = create_project(client, "employment-project", employment["id"]).json()

    denied = client.post(f"/api/work/projects/{project['id']}/participants", json={
        "person_id": person["id"], "role": "Reviewer", "idempotency_key": "pending-link",
    })
    assert denied.status_code == 422

    confirm = {
        "name": person["name"], "role": person["role"],
        "identity_status": "confirmed", "expected_revision": person["revision"],
        "idempotency_key": "confirm-person",
    }
    confirmed = update_person(client, employment, person, confirm)
    assert confirmed.status_code == 200
    assert confirmed.json()["identity_status"] == "confirmed"
    assert update_person(client, employment, person, confirm).json() == confirmed.json()

    stale = update_person(client, employment, person, {
        **confirm, "idempotency_key": "confirm-person-stale",
    })
    assert stale.status_code == 409
    assert create_person(client, employment, "invalid-state", identity_status="guessed").status_code == 422


def test_confirmed_person_identity_edit_is_scoped_cas_and_keeps_project_link(tmp_path):
    client, store = client_for(tmp_path)
    _, employment_a = create_employment(client, "虚构公司甲")
    _, employment_b = create_employment(client, "虚构公司乙")
    person_a = create_person(client, employment_a, "editable-person-a", role="旧角色").json()
    person_b = create_person(client, employment_b, "editable-person-b", role="另一任职角色").json()
    project = create_project(client, "editable-person-project", employment_a["id"]).json()
    participant = client.post(f"/api/work/projects/{project['id']}/participants", json={
        "person_id": person_a["id"], "role": "Reviewer", "idempotency_key": "editable-person-link",
    }).json()

    request = {
        "name": "Phase C 虚构人物 修正版", "role": "新角色",
        "expected_revision": person_a["revision"], "idempotency_key": "edit-confirmed-person",
    }
    response = update_person(client, employment_a, person_a, request)
    assert response.status_code == 200
    edited = response.json()
    assert edited["id"] == person_a["id"]
    assert edited["name"] == request["name"]
    assert edited["role"] == request["role"]
    assert edited["identity_status"] == "confirmed"
    assert edited["employment_id"] == employment_a["id"]
    assert edited["revision"] == person_a["revision"] + 1

    replay = update_person(client, employment_a, person_a, request)
    assert replay.status_code == 200
    assert replay.json() == edited
    stale = update_person(client, employment_a, person_a, {
        **request, "name": "不应覆盖", "idempotency_key": "edit-person-stale",
    })
    assert stale.status_code == 409
    wrong_scope_a = update_person(client, employment_b, person_a, {
        **request, "idempotency_key": "edit-person-from-wrong-employment",
    })
    wrong_scope_b = update_person(client, employment_a, person_b, {
        **request, "idempotency_key": "edit-other-employment-person",
    })
    assert wrong_scope_a.status_code == wrong_scope_b.status_code == 422
    assert client.post(f"/api/work/persons/{person_a['id']}", json=request).status_code == 404

    domain = client.get("/api/work-domain").json()
    saved = next(item for item in domain["persons"] if item["id"] == person_a["id"])
    assert saved == edited
    assert len([item for item in domain["persons"] if item["id"] == person_a["id"]]) == 1
    assert domain["participants"] == [participant]
    assert participant["person_id"] == saved["id"]
    with store.connect(False) as db:
        assert db.execute("SELECT COUNT(*) FROM current WHERE kind='work_person'").fetchone()[0] == 2



def test_only_confirmed_person_from_project_employment_can_be_linked(tmp_path):
    client, store = client_for(tmp_path)
    _, employment_a = create_employment(client, "虚构公司甲")
    _, employment_b = create_employment(client, "虚构公司乙")
    person_a = create_person(client, employment_a, "person-a", role="直属领导").json()
    person_b = create_person(client, employment_b, "person-b", role="经常合作的同事").json()
    project_a = create_project(client, "project-a", employment_a["id"]).json()
    project_b = create_project(client, "project-b", employment_b["id"]).json()
    personal_project = create_project(client, "personal-project").json()

    linked = client.post(f"/api/work/projects/{project_a['id']}/participants", json={
        "person_id": person_a["id"], "role": "决策者", "idempotency_key": "link-a",
    })
    assert linked.status_code == 200
    relation = linked.json()
    assert client.post(f"/api/work/projects/{project_a['id']}/participants", json={
        "person_id": person_a["id"], "role": "决策者", "idempotency_key": "link-a",
    }).json() == relation
    assert relation["role"] == "决策者"
    assert relation["person_id"] == person_a["id"]
    assert client.post(f"/api/work/projects/{project_b['id']}/participants", json={
        "person_id": person_a["id"], "role": "Reviewer", "idempotency_key": "wrong-employment",
    }).status_code == 422
    assert client.post(f"/api/work/projects/{project_a['id']}/participants", json={
        "person_id": person_b["id"], "role": "Reviewer", "idempotency_key": "wrong-project-employment",
    }).status_code == 422
    assert client.post(f"/api/work/projects/{personal_project['id']}/participants", json={
        "person_id": person_a["id"], "role": "Reviewer", "idempotency_key": "personal-project-person",
    }).status_code == 422

    domain = client.get("/api/work-domain").json()
    saved_person_a = next(item for item in domain["persons"] if item["id"] == person_a["id"])
    assert saved_person_a["role"] == "直属领导"
    assert domain["participants"] == [relation]
    with store.connect(False) as db:
        assert db.execute("SELECT COUNT(*) FROM current WHERE kind='work_project'").fetchone()[0] == 3


def test_employment_role_and_freeform_project_roles_are_independent(tmp_path):
    client, _ = client_for(tmp_path)
    _, employment = create_employment(client, "虚构公司")
    person = create_person(client, employment, "role-separation-person", role="产品总监").json()
    project_a = create_project(client, "role-separation-project-a", employment["id"]).json()
    project_b = create_project(client, "role-separation-project-b", employment["id"]).json()

    reviewer = client.post(f"/api/work/projects/{project_a['id']}/participants", json={
        "person_id": person["id"], "role": "Reviewer / 临时评审职责",
        "idempotency_key": "role-separation-reviewer",
    }).json()
    sponsor = client.post(f"/api/work/projects/{project_b['id']}/participants", json={
        "person_id": person["id"], "role": "Sponsor / 业务赞助人",
        "idempotency_key": "role-separation-sponsor",
    }).json()
    assert reviewer["role"] == "Reviewer / 临时评审职责"
    assert sponsor["role"] == "Sponsor / 业务赞助人"
    before_person_edit = client.get("/api/work-domain").json()
    saved_before_edit = next(item for item in before_person_edit["persons"] if item["id"] == person["id"])
    assert saved_before_edit["role"] == "产品总监"

    changed = update_person(client, employment, person, {
        "name": person["name"], "role": "产品策略负责人",
        "expected_revision": person["revision"],
        "idempotency_key": "role-separation-employment-edit",
    })
    assert changed.status_code == 200
    assert changed.json()["id"] == person["id"]
    assert changed.json()["role"] == "产品策略负责人"
    domain = client.get("/api/work-domain").json()
    saved_person = next(item for item in domain["persons"] if item["id"] == person["id"])
    assert saved_person["role"] == "产品策略负责人"
    assert {item["id"]: item["role"] for item in domain["participants"]} == {
        reviewer["id"]: "Reviewer / 临时评审职责",
        sponsor["id"]: "Sponsor / 业务赞助人",
    }


def test_ending_employment_keeps_person_and_project_participant_history(tmp_path):
    client, store = client_for(tmp_path)
    episode, employment = create_employment(client, "虚构公司")
    person = create_person(client, employment, "person", role="直属领导").json()
    project = create_project(client, "project", employment["id"]).json()
    participant = client.post(f"/api/work/projects/{project['id']}/participants", json={
        "person_id": person["id"], "role": "决策者", "idempotency_key": "participant",
    }).json()

    ended = client.post(f"/api/journey/episodes/{episode['id']}", json={
        **episode, "end_date": "2026-09-01", "expected_revision": episode["revision"],
    })
    assert ended.status_code == 200
    domain = client.get("/api/work-domain").json()
    saved_employment = next(item for item in domain["employments"] if item["id"] == employment["id"])
    saved_person = next(item for item in domain["persons"] if item["id"] == person["id"])
    saved_project = next(item for item in domain["projects"] if item["id"] == project["id"])
    assert saved_employment["end_date"] == "2026-09-01"
    assert saved_person["employment_id"] == employment["id"]
    assert saved_person["identity_status"] == "confirmed"
    assert saved_project["employment_id"] == employment["id"]
    assert domain["participants"] == [participant]
    with store.connect(False) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 6
        assert db.execute("SELECT COUNT(*) FROM current WHERE kind='work_person'").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM records WHERE kind='work_project_participant'").fetchone()[0] == 1


def test_legacy_global_person_is_preserved_but_isolated_from_new_domain(tmp_path):
    client, store = client_for(tmp_path)
    project = create_project(client, "legacy-project").json()
    with store.connect() as db:
        legacy = store._save(db, "work_person", {
            "id": "legacy-global-person", "name": "不输出的虚构姓名", "role": "旧数据",
        }, 0)
        orphan = store._save(db, "work_person", {
            "id": "orphan-person", "name": "隔离虚构姓名", "role": "旧数据",
            "employment_id": "employment:missing", "identity_status": "confirmed",
        }, 0)
        old_participant = {
            "id": "legacy-participant", "project_id": project["id"],
            "person_id": legacy["id"], "person_revision": legacy["revision"],
            "role": "旧角色",
        }
        store._record(db, "work_project_participant", old_participant)
        before = json.loads(db.execute(
            "SELECT body FROM current WHERE id=?", (legacy["id"],),
        ).fetchone()[0])
        orphan_before = json.loads(db.execute(
            "SELECT body FROM current WHERE id=?", (orphan["id"],),
        ).fetchone()[0])

    domain = client.get("/api/work-domain").json()
    assert domain["persons"] == []
    assert domain["participants"] == [old_participant]
    with store.connect(False) as db:
        after = json.loads(db.execute(
            "SELECT body FROM current WHERE id=?", (legacy["id"],),
        ).fetchone()[0])
        orphan_after = json.loads(db.execute(
            "SELECT body FROM current WHERE id=?", (orphan["id"],),
        ).fetchone()[0])
        assert after == before
        assert orphan_after == orphan_before
        assert db.execute("PRAGMA user_version").fetchone()[0] == 6
