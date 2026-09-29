"""T14: the smallest approved Employment/Project outcome -> Resume chain."""

import json

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.opportunity import create_opportunity
from workbench.providers import TestProvider
from workbench.secret_store import SecretStore
from workbench.core import digest, now
from workbench.work import _achievement_hash, _employment_owner, _evidence_pointer
from workbench import knowledge


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


class SecretAccessTrap(SecretStore):
    def __init__(self):
        self.calls = []

    def _fail(self, operation, *args):
        self.calls.append((operation, args))
        raise AssertionError(f"T14 touched secret store: {operation}")

    def allocate_ref(self):
        return self._fail("allocate_ref")

    def put(self, ref, value):
        return self._fail("put", ref, value)

    def get(self, ref):
        return self._fail("get", ref)

    def delete(self, ref):
        return self._fail("delete", ref)


class ProviderAccessTrap(TestProvider):
    def __init__(self):
        super().__init__()
        self.calls = []

    def _fail(self, operation):
        self.calls.append(operation)
        raise AssertionError(f"T14 touched Provider: {operation}")

    def build_payload(self, packet):
        return self._fail("build_payload")

    def complete(self, payload):
        return self._fail("complete")


def make_client(tmp_path, *, store=None):
    store = store or Store(tmp_path / "data", TestProvider())
    return TestClient(create_app(store), base_url="http://127.0.0.1", headers=HEADERS), store


def work_fixture(client):
    episode = client.post(
        "/api/journey/episodes",
        json={"company": "T14 虚构任职", "role": "T14 工程师", "focus": "EMPLOYMENT_PRIVATE_CANARY"},
    ).json()
    domain = client.get("/api/work-domain").json()
    employment = next(item for item in domain["employments"] if item["legacy_episode_id"] == episode["id"])
    project = client.post(
        "/api/work/projects",
        json={
            "name": "T14 虚构项目",
            "description": "PROJECT_PRIVATE_CANARY",
            "scope_type": "employment",
            "scope_id": employment["id"],
            "idempotency_key": "t14-project",
        },
    ).json()
    # Reconstruct historical rows directly: the old T14 creation endpoints are retired.
    store = client.app.state.store
    with store.connect() as db:
        achievement = store._save(db, "work_achievement", {
            "id": "historical-t14-achievement", "project_id": project["id"],
            "title": "T14 虚构成果", "content": "原始任职事实 ORIGINAL_EMPLOYMENT_FACT_CANARY",
            "created_at": now(),
        }, 0)
        evidence = {
            "id": "historical-t14-evidence", "scope_type": "project", "scope_id": project["id"],
            "title": "T14 证据指针", "source_type": "内部文档",
            "content": "敏感证据原文 PRIVATE_EVIDENCE_RAW_CANARY", "created_at": now(),
        }
        store._record(db, "work_evidence", evidence)
        link = {
            "id": "historical-t14-link", "achievement_id": achievement["id"],
            "evidence_id": evidence["id"], "achievement_revision": achievement["revision"],
            "evidence_created_at": evidence["created_at"], "created_at": now(),
        }
        store._record(db, "work_evidence_link", link)
    return episode, employment, project, achievement, evidence, link


def resume_fixture(store, client):
    opportunity = create_opportunity(
        store,
        {
            "company_name": "T14 虚构求职公司",
            "title": "T14 虚构岗位",
            "jd": "T14 虚构 JD",
            "idempotency_key": "t14-opportunity",
        },
    )
    response = client.post(
        f"/api/opportunities/{opportunity['id']}/resume/start",
        json={
            "expected_opportunity_revision": opportunity["revision"],
            "idempotency_key": "t14-resume-start",
            "source": {"kind": "blank"},
        },
    )
    assert response.status_code == 200, response.text
    document = response.json()
    return opportunity, document


def approve(client, achievement, *, content="脱敏后的求职表达 APPROVED_RESUME_CANARY", title="T14 脱敏成果"):
    store = client.app.state.store
    with store.connect() as db:
        project = store._get(db, achievement["project_id"], "work_project")
        evidence = next(item for item in store._records(db, "work_evidence")
                        if item["id"] == "historical-t14-evidence")
        provenance = {
            "kind": "work_achievement_reuse",
            "owner": _employment_owner(store, db, project),
            "source": {"kind": "work_achievement", "id": achievement["id"],
                       "revision": achievement["revision"], "hash": _achievement_hash(achievement)},
            "project_id": project["id"], "evidence_refs": [_evidence_pointer(evidence)],
            "approved_content_hash": digest({"title": title, "content": content}),
            "approved_at": now(), "allowed_uses": ["resume"],
        }
        entry = knowledge.create_reusable_personal_entry(
            store, db, title=title, content=content, provenance=provenance)
    return dict(entry, source_achievement_id=achievement["id"])


def select_material(client, document, entry, *, section="projects", key="t14-select"):
    response = client.post(
        f"/api/resume-documents/{document['document_id']}/select-facts",
        json={
            "expected_revision": document["revision"],
            "selections": [{"id": entry["id"], "revision": entry["revision"], "section_type": section}],
            "include_profile": False,
            "profile_revision": None,
            "idempotency_key": key,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_unapproved_achievement_cannot_be_read_or_selected_by_resume(tmp_path):
    client, store = make_client(tmp_path)
    _, _, _, achievement, evidence, _ = work_fixture(client)
    _, document = resume_fixture(store, client)

    materials = client.get(f"/api/resume-documents/{document['document_id']}/materials").json()
    encoded = json.dumps(materials, ensure_ascii=False)
    assert achievement["id"] not in encoded
    assert "ORIGINAL_EMPLOYMENT_FACT_CANARY" not in encoded
    assert "PRIVATE_EVIDENCE_RAW_CANARY" not in encoded

    rejected = client.post(
        f"/api/resume-documents/{document['document_id']}/select-facts",
        json={
            "expected_revision": 0,
            "selections": [{"id": achievement["id"], "revision": achievement["revision"], "section_type": "projects"}],
            "include_profile": False,
            "profile_revision": None,
            "idempotency_key": "t14-unapproved-select",
        },
    )
    assert rejected.status_code == 404


def test_approved_expression_becomes_resume_material_with_evidence_pointer(tmp_path):
    client, store = make_client(tmp_path)
    _, _, _, achievement, evidence, link = work_fixture(client)
    entry = approve(client, achievement)
    assert entry["fact_status"] == "confirmed"
    assert entry["reuse_status"] == "approved"
    assert entry["allowed_uses"] == ["resume"]
    assert entry["content"] == "脱敏后的求职表达 APPROVED_RESUME_CANARY"
    assert "PRIVATE_EVIDENCE_RAW_CANARY" not in json.dumps(entry, ensure_ascii=False)
    assert entry["reuse_provenance"]["source"]["id"] == achievement["id"]
    assert entry["reuse_provenance"]["source"]["revision"] == achievement["revision"]
    assert entry["reuse_provenance"]["evidence_refs"][0]["id"] == evidence["id"]
    assert entry["reuse_provenance"]["evidence_refs"][0]["id"] == link["evidence_id"]

    _, document = resume_fixture(store, client)
    materials = client.get(f"/api/resume-documents/{document['document_id']}/materials").json()
    assert [item["id"] for item in materials["entries"]] == [entry["id"]]
    assert materials["entries"][0]["reuse_provenance"]["evidence_refs"][0]["id"] == evidence["id"]
    assert "PRIVATE_EVIDENCE_RAW_CANARY" not in json.dumps(materials, ensure_ascii=False)
    selected = select_material(client, document, entry)
    selected_text = json.dumps(selected["document"], ensure_ascii=False)
    assert "APPROVED_RESUME_CANARY" in selected_text
    assert "ORIGINAL_EMPLOYMENT_FACT_CANARY" not in selected_text
    assert "PRIVATE_EVIDENCE_RAW_CANARY" not in selected_text
    assert selected["document"]["meta"]["source_refs"][0]["evidence_refs"][0]["id"] == evidence["id"]


def test_sanitizing_reuse_does_not_overwrite_employment_project_or_evidence(tmp_path):
    client, store = make_client(tmp_path)
    _, _, project, achievement, evidence, _ = work_fixture(client)
    entry = approve(client, achievement)
    domain = client.get("/api/work-domain").json()
    current_achievement = next(item for item in domain["achievements"] if item["id"] == achievement["id"])
    current_evidence = next(item for item in domain["evidence"] if item["id"] == evidence["id"])
    assert current_achievement["content"] == "原始任职事实 ORIGINAL_EMPLOYMENT_FACT_CANARY"
    assert current_achievement["project_id"] == project["id"]
    assert current_evidence["content"] == "敏感证据原文 PRIVATE_EVIDENCE_RAW_CANARY"
    assert entry["content"] != current_achievement["content"]


def test_revoke_blocks_new_resume_selection_but_preserves_confirmed_fact(tmp_path):
    client, store = make_client(tmp_path)
    _, _, _, achievement, _, _ = work_fixture(client)
    entry = approve(client, achievement)
    revoked = client.post(
        f"/api/work/reuses/{entry['id']}/revoke",
        json={"expected_revision": entry["revision"], "idempotency_key": "t14-revoke"},
    )
    assert revoked.status_code == 200, revoked.text
    revoked_entry = revoked.json()
    assert revoked_entry["status"] == "active"
    assert revoked_entry["fact_status"] == "confirmed"
    assert revoked_entry["reuse_status"] == "revoked"

    _, document = resume_fixture(store, client)
    materials = client.get(f"/api/resume-documents/{document['document_id']}/materials").json()
    assert entry["id"] not in {item["id"] for item in materials["entries"]}
    rejected = client.post(
        f"/api/resume-documents/{document['document_id']}/select-facts",
        json={
            "expected_revision": 0,
            "selections": [{"id": entry["id"], "revision": entry["revision"], "section_type": "projects"}],
            "include_profile": False,
            "profile_revision": None,
            "idempotency_key": "t14-revoked-select",
        },
    )
    assert rejected.status_code in {404, 422}


def test_frozen_resume_version_is_unchanged_after_future_revoke(tmp_path):
    client, store = make_client(tmp_path)
    _, _, _, achievement, _, _ = work_fixture(client)
    entry = approve(client, achievement)
    _, document = resume_fixture(store, client)
    selected = select_material(client, document, entry)
    version = client.post(
        f"/api/resume-documents/{document['document_id']}/versions",
        json={"name": "T14 冻结版本 A", "expected_revision": selected["revision"], "idempotency_key": "t14-version-a"},
    )
    assert version.status_code == 200, version.text
    frozen = version.json()
    revoked = client.post(
        f"/api/work/reuses/{entry['id']}/revoke",
        json={"expected_revision": entry["revision"], "idempotency_key": "t14-revoke-frozen"},
    )
    assert revoked.status_code == 200, revoked.text
    replay = client.get(f"/api/resume-documents/{document['document_id']}/versions/{frozen['id']}")
    assert replay.status_code == 200
    assert replay.json()["document"] == frozen["document"]
    assert replay.json()["document_hash"] == frozen["document_hash"]


def test_resume_and_context_never_expand_into_people_or_private_evidence(tmp_path):
    client, store = make_client(tmp_path)
    _, employment, project, achievement, evidence, _ = work_fixture(client)
    person = client.post(
        f"/api/work/employments/{employment['id']}/persons",
        json={"name": "T14 私聊人物 PRIVATE_PERSON_CANARY", "role": "内部协作", "idempotency_key": "t14-person"},
    ).json()
    participant = client.post(
        f"/api/work/projects/{project['id']}/participants",
        json={"person_id": person["id"], "role": "PRIVATE_PEOPLE_ROLE_CANARY", "idempotency_key": "t14-participant"},
    )
    assert participant.status_code == 200
    entry = approve(client, achievement)
    _, document = resume_fixture(store, client)
    materials = client.get(f"/api/resume-documents/{document['document_id']}/materials").json()
    text = json.dumps(materials, ensure_ascii=False)
    assert "PRIVATE_PERSON_CANARY" not in text
    assert "PRIVATE_PEOPLE_ROLE_CANARY" not in text
    assert "PRIVATE_EVIDENCE_RAW_CANARY" not in text

    with store.connect(False) as connection:
        job = store._get(connection, document["opportunity_id"], "opportunity")
        packet = store.context(job["id"], "job", wiki_ids=[entry["id"]])
    packet_text = json.dumps(packet, ensure_ascii=False)
    assert "APPROVED_RESUME_CANARY" in packet_text
    assert "PRIVATE_PERSON_CANARY" not in packet_text
    assert "PRIVATE_PEOPLE_ROLE_CANARY" not in packet_text
    assert "PRIVATE_EVIDENCE_RAW_CANARY" not in packet_text
    source = next(item for item in packet["sources"] if item["id"] == entry["id"])
    assert source["provenance"]["evidence_refs"][0]["id"] == evidence["id"]


def test_evidence_pointer_is_traceable_without_copying_evidence_text(tmp_path):
    client, store = make_client(tmp_path)
    _, _, _, achievement, evidence, _ = work_fixture(client)
    entry = approve(client, achievement)
    _, document = resume_fixture(store, client)
    selected = select_material(client, document, entry)
    sources = client.get(f"/api/resume-documents/{document['document_id']}/sources").json()
    source_text = json.dumps(sources, ensure_ascii=False)
    assert evidence["id"] in source_text
    assert "T14 证据指针" in source_text
    assert "PRIVATE_EVIDENCE_RAW_CANARY" not in source_text
    assert selected["document"]["meta"]["source_refs"][0]["evidence_refs"][0]["id"] == evidence["id"]


def test_editing_approved_resume_expression_never_writes_back_to_work_source(tmp_path):
    client, store = make_client(tmp_path)
    _, _, _, achievement, _, _ = work_fixture(client)
    entry = approve(client, achievement)
    _, document = resume_fixture(store, client)
    selected = select_material(client, document, entry)
    edited = json.loads(json.dumps(selected["document"]))
    next(section for section in edited["sections"] if section["type"] == "projects")["items"][0]["bullets"][0]["content"] = "用户在简历中的另一种表达"
    saved = client.put(
        f"/api/resume-documents/{document['document_id']}",
        json={"document": edited, "expected_revision": selected["revision"]},
    )
    assert saved.status_code == 200, saved.text
    domain = client.get("/api/work-domain").json()
    assert next(item for item in domain["achievements"] if item["id"] == achievement["id"])["content"] == "原始任职事实 ORIGINAL_EMPLOYMENT_FACT_CANARY"
    entries = client.get("/api/knowledge").json()["entries"]
    assert next(item for item in entries if item["id"] == entry["id"])["content"] == "脱敏后的求职表达 APPROVED_RESUME_CANARY"


def test_ai_context_only_receives_explicitly_approved_expression(tmp_path):
    client, store = make_client(tmp_path)
    _, _, _, achievement, _, _ = work_fixture(client)
    entry = approve(client, achievement)
    _, document = resume_fixture(store, client)
    store.save_profile("T14 基础资料", 0)
    with store.connect(False) as connection:
        job = store._get(connection, document["opportunity_id"], "opportunity")
        without_selection = store.context(job["id"], "job", wiki_ids=[])
        with_selection = store.context(job["id"], "job", wiki_ids=[entry["id"]])
    assert "APPROVED_RESUME_CANARY" not in json.dumps(without_selection, ensure_ascii=False)
    explicit = json.dumps(with_selection, ensure_ascii=False)
    assert "APPROVED_RESUME_CANARY" in explicit
    assert "ORIGINAL_EMPLOYMENT_FACT_CANARY" not in explicit
    assert "PRIVATE_EVIDENCE_RAW_CANARY" not in explicit


def test_reuse_requires_explicit_user_permission_and_cas(tmp_path):
    client, _ = make_client(tmp_path)
    _, _, _, achievement, _, _ = work_fixture(client)
    missing_permission = client.post(
        f"/api/work/achievements/{achievement['id']}/reuse",
        json={
            "expected_revision": achievement["revision"],
            "title": "未批准",
            "content": "不应成为个人事实",
            "allow_resume_reuse": False,
            "idempotency_key": "t14-no-permission",
        },
    )
    assert missing_permission.status_code == 409
    stale = client.post(
        f"/api/work/achievements/{achievement['id']}/reuse",
        json={
            "expected_revision": achievement["revision"] + 1,
            "title": "过期",
            "content": "不应写入",
            "allow_resume_reuse": True,
            "idempotency_key": "t14-stale",
        },
    )
    assert stale.status_code == 409
    assert client.get("/api/knowledge").json()["entries"] == []


def test_t14_manual_path_keeps_local_only_and_never_touches_secret_store(tmp_path, monkeypatch):
    monkeypatch.setenv("CAREER_AI_MODE", "LOCAL_ONLY")
    trap = SecretAccessTrap()
    provider = ProviderAccessTrap()
    store = Store(tmp_path / "data", provider, trap)
    client, _ = make_client(tmp_path, store=store)
    _, _, _, achievement, _, _ = work_fixture(client)
    entry = approve(client, achievement)
    assert entry["reuse_status"] == "approved"
    assert store.runtime_mode.value == "LOCAL_ONLY"
    assert trap.calls == []
    assert provider.calls == []
