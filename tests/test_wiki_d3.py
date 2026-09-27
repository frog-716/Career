"""D3 business workspaces target one exact Project, Employment, or Person scope."""
import json
from copy import deepcopy
import sqlite3

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


def _harness(tmp_path, provider_result):
    provider = TestProvider()
    store = Store(tmp_path / "data", provider)
    client = TestClient(
        create_app(store), base_url="http://127.0.0.1",
        headers={"X-Career-Request": "1"},
    )
    calls = []

    def complete(payload):
        calls.append(deepcopy(payload))
        return deepcopy(provider_result)

    provider.complete = complete
    return client, store, calls


def _episode_and_employment(client, suffix):
    episode = client.post("/api/journey/episodes", json={
        "company": f"虚构任职公司 {suffix}", "role": "虚构负责人",
    })
    assert episode.status_code == 200, episode.text
    domain = client.get("/api/work-domain").json()
    employment = next(item for item in domain["employments"]
                      if item["legacy_episode_id"] == episode.json()["id"])
    return episode.json(), employment


def _project(client, name, employment_id=None):
    response = client.post("/api/work/projects", json={
        "name": name, "employment_id": employment_id,
        "idempotency_key": "project-" + name,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _raw(client, scope_type, scope_id, suffix):
    response = client.post("/api/raw", json={
        "scope_type": scope_type, "scope_id": scope_id,
        "source_kind": "manual_text", "title": f"虚构资料 {suffix}",
        "content": f"仅供自动测试的原始内容 {suffix}",
        "idempotency_key": "raw-" + suffix,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _wiki(client, scope_type, scope_id, content, suffix):
    response = client.post("/api/wiki", json={
        "scope_type": scope_type, "scope_id": scope_id,
        "knowledge_type": "fact", "content": content,
        "tags": [], "source_refs": [], "idempotency_key": "wiki-" + suffix,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _target(scope_type, scope_id):
    return {"scope_type": scope_type, "scope_id": scope_id}


def _execute(client, raw, target_scope, preview, key="d3-execute"):
    return client.post("/api/wiki/compiler/execute", json={
        "raw_id": raw["id"], "idempotency_key": key,
        "target_scope": target_scope,
        "prepared_id": preview["prepared_id"],
        "payload_hash": preview["payload_hash"],
        "confirm_outbound": True,
    })


def test_project_compiler_preview_and_patch_are_limited_to_the_entered_scope(tmp_path):
    project_patch = {
        "operation": "add", "scope_type": "project", "scope_id": "PROJECT_ID",
        "knowledge_type": "fact", "content": "虚构项目新增的长期知识。", "tags": ["#D3"],
        "source_refs": [{"kind": "raw_material", "id": "RAW_ID", "revision": 1}],
        "reason": "测试来源明确支持这条信息。",
    }
    client, store, calls = _harness(tmp_path, {"patches": [project_patch]})
    _episode, employment = _episode_and_employment(client, "项目边界")
    project = _project(client, "D3 虚构项目 A", employment["id"])
    other_project = _project(client, "D3 虚构项目 B")
    person = client.post(f"/api/work/employments/{employment['id']}/persons", json={
        "name": "D3 虚构人物", "role": "测试角色", "idempotency_key": "d3-person",
    }).json()
    linked = client.post(f"/api/work/projects/{project['id']}/participants", json={
        "person_id": person["id"], "role": "Reviewer", "idempotency_key": "d3-link-person",
    })
    assert linked.status_code == 200, linked.text
    raw = _raw(client, "project", project["id"], "project-scope")
    _wiki(client, "project", project["id"], "当前项目的虚构 Wiki。", "project-current")
    _wiki(client, "employment", employment["id"], "不应进入 Project 的任职 Wiki。", "employment-foreign")
    _wiki(client, "person", person["id"], "不应进入 Project 的人物 Wiki。", "person-foreign")
    _wiki(client, "project", other_project["id"], "不应进入当前项目的其他 Project Wiki。", "other-project")

    target = _target("project", project["id"])
    request = {"raw_id": raw["id"], "idempotency_key": "d3-project-prepare", "target_scope": target}
    preview_response = client.post("/api/wiki/compiler/prepare", json=request)
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    packet = preview["readable_context"]
    assert packet["scopes"] == [{
        "type": "project", "minimal_identity": {"name": "D3 虚构项目 A"},
    }]
    assert preview["target_scope"] == target
    assert [item["content"] for item in packet["current_knowledge"]] == ["当前项目的虚构 Wiki。"]
    encoded = json.dumps(packet, ensure_ascii=False)
    assert "不应进入" not in encoded
    assert calls == [], "prepare 必须保持零 Provider 调用"

    project_patch["scope_id"] = project["id"]
    project_patch["source_refs"][0]["id"] = raw["id"]
    response = _execute(client, raw, target, preview, "d3-project-prepare")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "proposal_pending"
    proposal = result["proposal"]
    assert proposal["target_scope"] == target
    assert proposal["patches"][0]["source_refs"] == [raw["source_ref"]]
    assert {(item["scope_type"], item["scope_id"]) for item in proposal["patches"]} == {
        ("project", project["id"]),
    }
    raw_workspace = client.get(
        f"/api/wiki/workspace?scope_type=project&scope_id={project['id']}"
    ).json()["raw"]
    assert next(item for item in raw_workspace if item["id"] == raw["id"])["pending_patch_count"] == 1
    listed_raw = client.get(
        f"/api/raw?scope_type=project&scope_id={project['id']}"
    ).json()["items"]
    assert next(item for item in listed_raw if item["id"] == raw["id"])["pending_patch_count"] == 1
    before_accept = client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json()
    assert {item["content"] for item in before_accept} == {"当前项目的虚构 Wiki。"}, \
        "pending proposal 不改正式 Wiki"
    assert len(calls) == 1

    resolved = client.post(
        f"/api/wiki/compiler/proposals/{proposal['id']}/patches/{proposal['patches'][0]['id']}/resolve",
        json={"decision": "accept", "idempotency_key": "d3-project-accept"},
    )
    assert resolved.status_code == 200, resolved.text
    assert client.get(
        f"/api/wiki/workspace?scope_type=project&scope_id={project['id']}"
    ).json()["raw"][0]["pending_patch_count"] == 0
    project_wiki = client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json()
    assert {item["content"] for item in project_wiki} == {
        "当前项目的虚构 Wiki。", "虚构项目新增的长期知识。",
    }
    assert client.get(f"/api/wiki?scope_type=employment&scope_id={employment['id']}").json()[0]["content"] == "不应进入 Project 的任职 Wiki。"
    assert client.get(f"/api/wiki?scope_type=person&scope_id={person['id']}").json()[0]["content"] == "不应进入 Project 的人物 Wiki。"
    with sqlite3.connect(store.db) as connection:
        assert connection.execute("pragma user_version").fetchone()[0] == 6
    store.shutdown()


def test_wiki_all_returns_only_titles_for_its_displayed_sources(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    first = _project(client, "D3.5 虚构项目一")
    second = _project(client, "D3.5 虚构项目二")
    raw_first = _raw(client, "project", first["id"], "first-title")
    raw_second = _raw(client, "project", second["id"], "second-title")
    response = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": first["id"],
        "knowledge_type": "fact", "content": "虚构知识，引用两个来源。",
        "tags": [], "source_refs": [raw_first["source_ref"], raw_second["source_ref"]],
        "idempotency_key": "d35-source-titles",
    })
    # A Project must not be allowed to cite another Project's Raw.
    assert response.status_code == 409
    for index, (project, raw) in enumerate(((first, raw_first), (second, raw_second))):
        response = client.post("/api/wiki", json={
            "scope_type": "project", "scope_id": project["id"],
            "knowledge_type": "fact", "content": f"虚构知识 {index}",
            "tags": [], "source_refs": [raw["source_ref"]],
            "idempotency_key": f"d35-source-title-{index}",
        })
        assert response.status_code == 200, response.text
    all_items = client.get("/api/wiki?scope_type=all&limit=50&include_source_titles=true")
    assert all_items.status_code == 200, all_items.text
    body = all_items.json()
    assert len(body["items"]) == 2
    titles = {item["title"] for item in body["source_catalog"]}
    assert titles == {raw_first["title"], raw_second["title"]}
    assert all("content" not in item for item in body["source_catalog"])
    assert calls == []
    store.shutdown()


def test_compiler_rejects_mismatched_target_scope_before_provider_dispatch(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project_a = _project(client, "D3 虚构项目 A")
    project_b = _project(client, "D3 虚构项目 B")
    raw = _raw(client, "project", project_a["id"], "wrong-target")
    response = client.post("/api/wiki/compiler/prepare", json={
        "raw_id": raw["id"], "idempotency_key": "d3-wrong-target",
        "target_scope": _target("project", project_b["id"]),
    })
    assert response.status_code == 422
    assert calls == []
    store.shutdown()


def test_person_workspace_compiler_reads_only_person_wiki_and_binds_confirm_to_scope(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    _episode, employment = _episode_and_employment(client, "人物范围")
    person = client.post(f"/api/work/employments/{employment['id']}/persons", json={
        "name": "D3 虚构人物 P", "role": "测试角色", "idempotency_key": "d3-person-p",
    }).json()
    other_episode, other_employment = _episode_and_employment(client, "另一个任职")
    _ = other_episode
    raw = _raw(client, "person", person["id"], "person-scope")
    person_fact = _wiki(client, "person", person["id"], "仅属于人物 P 的 Wiki。", "person-current")
    _wiki(client, "employment", employment["id"], "人物所属任职的 Wiki 不应自动进入。", "person-employment-foreign")
    _wiki(client, "employment", other_employment["id"], "其他任职的 Wiki。", "person-other-employment")

    target = _target("person", person["id"])
    intent = {"raw_id": raw["id"], "idempotency_key": "d3-person-prepare", "target_scope": target}
    preview_response = client.post("/api/wiki/compiler/prepare", json=intent)
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    packet = preview["readable_context"]
    assert packet["scopes"] == [{
        "type": "person", "minimal_identity": {
            "name": "D3 虚构人物 P", "employment_role": "测试角色",
        },
    }]
    assert preview["target_scope"] == target
    assert [item["content"] for item in packet["current_knowledge"]] == ["仅属于人物 P 的 Wiki。"]
    execute = _execute(client, raw, target, preview, "d3-person-prepare")
    assert execute.status_code == 200, execute.text
    assert execute.json()["status"] == "no_changes"
    assert execute.json()["message"] == "这份资料没有发现值得更新到 Wiki 的长期知识。"
    assert len(calls) == 1
    assert client.get(f"/api/wiki/{person_fact['id']}/history").json()["revisions"]
    store.shutdown()


def test_target_scope_cannot_change_between_preview_and_confirm(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project_a = _project(client, "D3 虚构项目 A")
    project_b = _project(client, "D3 虚构项目 B")
    raw = _raw(client, "project", project_a["id"], "target-change")
    intent = {"raw_id": raw["id"], "idempotency_key": "d3-target-freeze",
              "target_scope": _target("project", project_a["id"])}
    preview_response = client.post("/api/wiki/compiler/prepare", json=intent)
    assert preview_response.status_code == 200, preview_response.text
    response = client.post("/api/wiki/compiler/execute", json={
        **intent, "target_scope": _target("project", project_b["id"]),
        "prepared_id": preview_response.json()["prepared_id"],
        "payload_hash": preview_response.json()["payload_hash"],
        "confirm_outbound": True,
    })
    assert response.status_code in {409, 422}
    assert calls == []
    store.shutdown()


def test_employment_entry_uses_only_employment_wiki_and_rejects_person_patch(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    _episode, employment = _episode_and_employment(client, "任职边界")
    person = client.post(f"/api/work/employments/{employment['id']}/persons", json={
        "name": "D3 虚构任职人物", "role": "测试角色", "idempotency_key": "d3-employment-person",
    }).json()
    response = client.post("/api/raw", json={
        "scope_type": "employment", "scope_id": employment["id"],
        "source_kind": "manual_text", "title": "D3 任职测试资料",
        "content": "虚构会议中提到一位临时人物，但这不能自动创建长期 Person。",
        "idempotency_key": "raw-employment-scope",
    })
    assert response.status_code == 200, response.text
    raw = response.json()
    _wiki(client, "employment", employment["id"], "任职自己的当前理解。", "employment-current")
    _wiki(client, "person", person["id"], "不能混入任职页的人物 Wiki。", "employment-person-foreign")

    target = _target("employment", employment["id"])
    prepared = client.post("/api/wiki/compiler/prepare", json={
        "raw_id": raw["id"], "idempotency_key": "d3-employment-prepare", "target_scope": target,
    })
    assert prepared.status_code == 200, prepared.text
    preview = prepared.json()
    assert preview["readable_context"]["scopes"] == [{
        "type": "employment", "minimal_identity": {
            "company": "虚构任职公司 任职边界", "role": "虚构负责人",
        },
    }]
    assert [item["content"] for item in preview["readable_context"]["current_knowledge"]] == [
        "任职自己的当前理解。",
    ]
    person_wiki_before = client.get(
        f"/api/wiki?scope_type=person&scope_id={person['id']}"
    ).json()
    assert calls == [], "Preview 不应产生 Provider 调用"

    # Even a syntactically valid patch cannot escape the exact scope selected
    # by the business page when the model returns.
    calls.clear()
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {
        "patches": [{
            "operation": "add", "scope_type": "person", "scope_id": "person-from-mention",
            "knowledge_type": "fact", "content": "越界人物知识。", "tags": [],
            "source_refs": [{"kind": "raw_material", "id": raw["id"], "revision": raw["revision"]}],
            "reason": "越界回归测试。",
        }],
    }
    response = _execute(client, raw, target, preview, "d3-employment-prepare")
    assert response.status_code >= 400, response.text
    assert len(calls) == 1, "只有确认动作才调用被注入的 TestProvider"
    assert client.get("/api/work-domain").json()["persons"] == [person], \
        "Raw mention 或模型 Patch 不能创建 Person"
    assert client.get(f"/api/wiki?scope_type=person&scope_id={person['id']}").json() == person_wiki_before
    assert client.get(f"/api/wiki/compiler/proposals?raw_id={raw['id']}").json()["proposals"] == []
    store.shutdown()


def test_person_workspace_rejects_raw_owned_by_another_object(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    _episode, employment = _episode_and_employment(client, "Person Raw 边界")
    person = client.post(f"/api/work/employments/{employment['id']}/persons", json={
        "name": "D3 虚构人物 Raw 边界", "role": "测试角色", "idempotency_key": "d3-person-raw-boundary",
    }).json()
    project = _project(client, "D3 虚构项目 Raw 边界")
    raw = _raw(client, "project", project["id"], "not-person-raw")
    response = client.post("/api/wiki/compiler/prepare", json={
        "raw_id": raw["id"], "idempotency_key": "d3-person-foreign-raw",
        "target_scope": _target("person", person["id"]),
    })
    assert response.status_code == 422
    assert calls == []
    store.shutdown()
