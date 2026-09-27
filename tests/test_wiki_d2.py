"""D2 Wiki Compiler tests use only synthetic data and the local TestProvider."""
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


def test_compiler_preview_is_local_and_confirmed_replay_dispatches_once(tmp_path):
    provider = TestProvider()
    store = Store(tmp_path / "data", provider)
    client = TestClient(
        create_app(store), base_url="http://127.0.0.1",
        headers={"X-Career-Request": "1"},
    )
    sent = []

    def counted_complete(payload):
        sent.append(payload)
        return {"patches": []}

    provider.complete = counted_complete
    project_response = client.post("/api/work/projects", json={
        "name": "D2 虚构项目", "idempotency_key": "d2-project",
    })
    assert project_response.status_code == 200
    project = project_response.json()
    raw_response = client.post("/api/raw", json={
        "scope_type": "project", "scope_id": project["id"],
        "source_kind": "manual_text", "title": "虚构会议记录",
        "content": "虚构原文：周五前交付方案。",
        "idempotency_key": "d2-raw",
    })
    assert raw_response.status_code == 200
    raw = raw_response.json()

    request = {"raw_id": raw["id"], "idempotency_key": "d2-compile"}
    preview = client.post("/api/wiki/compiler/prepare", json=request)
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    assert preview_body["status"] == "context_confirmation_required"
    assert preview_body["preview"]["raw_count"] == 1
    assert preview_body["preview"]["wiki_count"] == 0
    assert sent == []

    execute_request = {
        **request,
        "prepared_id": preview_body["prepared_id"],
        "payload_hash": preview_body["payload_hash"],
        "confirm_outbound": False,
    }
    refused = client.post("/api/wiki/compiler/execute", json=execute_request)
    assert refused.status_code == 422
    assert sent == []
    execute_request["confirm_outbound"] = True
    result = client.post("/api/wiki/compiler/execute", json=execute_request)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "no_changes"
    assert len(sent) == 1

    replay = client.post("/api/wiki/compiler/execute", json=execute_request)
    assert replay.status_code == 200, replay.text
    assert len(sent) == 1

    packet = json.loads(sent[0]["messages"][1]["content"])
    assert set(packet) == {"task", "raw", "scopes", "current_knowledge"}
    assert set(packet["raw"]) == {"id", "source_kind", "created_at", "content"}
    assert set(packet["scopes"][0]) == {"type", "stable_id", "minimal_identity"}
    assert packet["task"] == "analyze_new_raw_for_wiki_changes"
    assert packet["raw"]["id"] == raw["id"]
    assert packet["raw"]["content"] == raw["content"]
    assert packet["scopes"] == [{
        "type": "project", "stable_id": project["id"],
        "minimal_identity": {"name": "D2 虚构项目"},
    }]
    assert "hash" not in json.dumps(packet)
    assert "secret" not in json.dumps(packet).lower()
    for kind in ("ai_call", "ai_audit", "ai_preparation", "ai_operation_result"):
        assert raw["content"] not in json.dumps(_records(store, kind), ensure_ascii=False)
    assert client.get(
        f"/api/wiki?scope_type=project&scope_id={project['id']}"
    ).json() == []
    store.shutdown()


def test_preview_content_is_an_exact_safe_projection_of_the_provider_context(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client, "D2 Preview 虚构项目")
    other_project = _project(client, "D2 Preview 其他项目")
    raw = client.post("/api/raw", json={
        "scope_type": "project", "scope_id": project["id"],
        "source_kind": "manual_text", "title": "虚构会议记录",
        "content": "D2 虚构资料：原型计划改到下周一，当前优先完成内部评审。",
        "idempotency_key": "d2-preview-raw",
    }).json()
    current = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"],
        "knowledge_type": "fact", "content": "原型原计划周五提交。",
        "tags": ["#D2-preview"], "source_refs": [],
        "idempotency_key": "d2-preview-wiki",
    })
    assert current.status_code == 200, current.text
    other = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": other_project["id"],
        "knowledge_type": "fact", "content": "不应送出的其他项目资料。",
        "tags": ["#other"], "source_refs": [],
        "idempotency_key": "d2-preview-other-wiki",
    })
    assert other.status_code == 200, other.text

    intent = {"raw_id": raw["id"], "idempotency_key": "d2-preview-compile"}
    response = client.post("/api/wiki/compiler/prepare", json=intent)
    assert response.status_code == 200, response.text
    prepared = response.json()
    preview_context = prepared["readable_context"]
    assert calls == [], "prepare / preview 必须保持零 Provider outbound"
    assert preview_context["raw"] == {
        "content": raw["content"], "created_at": raw["created_at"],
    }
    assert preview_context["scopes"] == [{
        "type": "project", "minimal_identity": {"name": project["name"]},
    }]
    assert preview_context["current_knowledge"] == [{
        "type": "fact", "content": "原型原计划周五提交。", "tags": ["#D2-preview"],
        "scope_type": "project", "scope_identity": {"name": project["name"]},
    }]
    assert prepared["preview_details"] == {
        "model": "测试模型", "raw_count": 1, "wiki_count": 1,
        "scopes": [f"项目 · {project['name']}"],
    }
    assert "不应送出的其他项目资料。" not in json.dumps(prepared, ensure_ascii=False)
    assert not any("secret" in key.lower() for key in prepared)

    execute = client.post("/api/wiki/compiler/execute", json={
        **intent, "prepared_id": prepared["prepared_id"],
        "payload_hash": prepared["payload_hash"], "confirm_outbound": True,
    })
    assert execute.status_code == 200, execute.text
    assert len(calls) == 1
    packet = json.loads(calls[0]["messages"][1]["content"])
    assert preview_context["raw"]["content"] == packet["raw"]["content"]
    assert preview_context["raw"]["created_at"] == packet["raw"]["created_at"]
    assert [
        {"type": item["type"], "minimal_identity": item["minimal_identity"]}
        for item in preview_context["scopes"]
    ] == [
        {"type": item["type"], "minimal_identity": item["minimal_identity"]}
        for item in packet["scopes"]
    ]
    assert [
        {key: item[key] for key in ("type", "content", "tags", "scope_type")}
        for item in preview_context["current_knowledge"]
    ] == [
        {"type": item["type"], "content": item["content"], "tags": item["tags"],
         "scope_type": item["scope_type"]}
        for item in packet["current_knowledge"]
    ]
    store.shutdown()


def test_default_model_prepare_confirm_hash_is_stable_without_network(tmp_path, monkeypatch):
    """The UI omits model_config_id, so both phases must hash the same resolved default."""
    from workbench.model_gateway import OpenAICompatibleAdapter
    from workbench.secret_store import MemorySecretStore

    monkeypatch.setenv("CAREER_AI_MODE", "AI_ENABLED")
    secrets = MemorySecretStore()
    store = Store(tmp_path / "data", TestProvider(), secrets)
    client = TestClient(
        create_app(store), base_url="http://127.0.0.1",
        headers={"X-Career-Request": "1"},
    )
    calls = []

    def synthetic_complete(_adapter, context, output_schema):
        calls.append((deepcopy(context), deepcopy(output_schema)))
        return {"patches": []}

    monkeypatch.setattr(OpenAICompatibleAdapter, "complete", synthetic_complete)
    config = client.post("/api/ai/models", json={
        "display_name": "Synthetic D2 model",
        "provider": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-flash",
        "api_key": "synthetic-never-sent",
        "enabled": True,
    })
    assert config.status_code == 200, config.text

    project = _project(client, "D2 default-model synthetic project")
    raw = _raw(client, project, "D2 default-model synthetic Raw")
    intent = {"raw_id": raw["id"], "idempotency_key": "d2-default-model-confirm"}
    preview = client.post("/api/wiki/compiler/prepare", json=intent)
    assert preview.status_code == 200, preview.text
    assert calls == [], "prepare 不得调用 Provider adapter"

    execute = client.post("/api/wiki/compiler/execute", json={
        **intent,
        "prepared_id": preview.json()["prepared_id"],
        "payload_hash": preview.json()["payload_hash"],
        "confirm_outbound": True,
    })
    assert execute.status_code == 200, execute.text
    assert execute.json()["status"] == "no_changes"
    assert len(calls) == 1
    with store.connect(False) as connection:
        operation = connection.execute(
            "SELECT state,dispatched_payload_hash FROM ai_operations WHERE task_type='wiki_compiler'"
        ).fetchone()
    assert operation[0] == "succeeded"
    assert operation[1]
    store.shutdown()


def test_default_model_identity_change_after_preview_is_stale_without_network(tmp_path, monkeypatch):
    from workbench.ai_config import _save_settings
    from workbench.model_gateway import OpenAICompatibleAdapter
    from workbench.secret_store import MemorySecretStore

    monkeypatch.setenv("CAREER_AI_MODE", "AI_ENABLED")
    store = Store(tmp_path / "data", TestProvider(), MemorySecretStore())
    client = TestClient(
        create_app(store), base_url="http://127.0.0.1",
        headers={"X-Career-Request": "1"},
    )
    calls = []
    monkeypatch.setattr(
        OpenAICompatibleAdapter, "complete",
        lambda _adapter, context, schema: calls.append((deepcopy(context), deepcopy(schema))) or {"patches": []},
    )
    model = {
        "display_name": "Synthetic same-model config",
        "provider": "DeepSeek", "base_url": "https://api.deepseek.com",
        "model": "deepseek-flash", "api_key": "synthetic-never-sent", "enabled": True,
    }
    first_config = client.post("/api/ai/models", json=model)
    assert first_config.status_code == 200, first_config.text
    project = _project(client, "D2 config identity synthetic project")
    raw = _raw(client, project, "D2 config identity synthetic Raw")
    intent = {"raw_id": raw["id"], "idempotency_key": "d2-config-identity-change"}
    preview = _prepare(client, raw, intent["idempotency_key"])

    second_config = client.post("/api/ai/models", json=model)
    assert second_config.status_code == 200, second_config.text
    assert first_config.json()["id"] != second_config.json()["id"]
    with store.connect() as connection:
        _save_settings(store, connection, second_config.json()["id"])

    response = _assert_pre_dispatch_stale(client, store, calls, intent, preview)
    assert response.status_code == 409
    store.shutdown()


def _harness(tmp_path, provider_result):
    provider = TestProvider()
    store = Store(tmp_path / "data", provider)
    client = TestClient(
        create_app(store), base_url="http://127.0.0.1",
        headers={"X-Career-Request": "1"},
    )
    calls = []

    original_complete = provider.complete

    def complete(payload):
        calls.append(deepcopy(payload))
        if provider_result is None:
            return original_complete(payload)
        if isinstance(provider_result, Exception):
            raise provider_result
        return deepcopy(provider_result)

    provider.complete = complete
    return client, store, calls


def _project(client, name="D2 项目"):
    response = client.post("/api/work/projects", json={
        "name": name, "idempotency_key": "project-" + name,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _raw(client, project, name="D2 Raw"):
    response = client.post("/api/raw", json={
        "scope_type": "project", "scope_id": project["id"],
        "source_kind": "manual_text", "title": name,
        "content": "虚构原文：周五前交付方案。",
        "idempotency_key": "raw-" + name,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _compile(client, raw, key="compile"):
    intent = {"raw_id": raw["id"], "idempotency_key": key}
    preview = client.post("/api/wiki/compiler/prepare", json=intent)
    assert preview.status_code == 200, preview.text
    response = client.post("/api/wiki/compiler/execute", json={
        **intent, "prepared_id": preview.json()["prepared_id"],
        "payload_hash": preview.json()["payload_hash"], "confirm_outbound": True,
    })
    return preview.json(), response


def _add_patch(raw, project, content="本周优先完成方案。"):
    return {
        "operation": "add", "scope_type": "project", "scope_id": project["id"],
        "knowledge_type": "fact", "content": content, "tags": ["#计划"],
        "source_refs": [{"kind": "raw_material", "id": raw["id"], "revision": raw["revision"]}],
        "reason": "虚构原文明确提出交付时间。",
    }


def _resolve(client, proposal, patch, decision, key, content=None):
    body = {"decision": decision, "idempotency_key": key}
    if content is not None:
        body["content"] = content
    return client.post(
        f"/api/wiki/compiler/proposals/{proposal['id']}/patches/{patch['id']}/resolve",
        json=body,
    )


def _records(store, kind):
    with store.connect(False) as c:
        return store._records(c, kind)


def _assert_pre_dispatch_stale(client, store, calls, intent, preview):
    preparations_before = len(_records(store, "ai_preparation"))
    with store.connect(False) as connection:
        operations_before = connection.execute(
            "SELECT COUNT(*) FROM ai_operations WHERE task_type='wiki_compiler'"
        ).fetchone()[0]
    dispatches_before = sum(
        item.get("task_type") == "wiki_compiler" and item.get("event") == "dispatched"
        for item in _records(store, "ai_audit")
    )
    response = client.post("/api/wiki/compiler/execute", json={
        **intent, "prepared_id": preview["prepared_id"],
        "payload_hash": preview["payload_hash"], "confirm_outbound": True,
    })
    assert response.status_code == 409, response.text
    assert "prepared_request_stale" in response.json()["detail"]
    assert len(_records(store, "ai_preparation")) == preparations_before, "stale 不自动重新 prepare"
    assert calls == [], "stale 必须在 Provider 调用前失败"
    dispatches_after = sum(
        item.get("task_type") == "wiki_compiler" and item.get("event") == "dispatched"
        for item in _records(store, "ai_audit")
    )
    assert dispatches_after == dispatches_before
    with store.connect(False) as connection:
        rows = connection.execute(
            "SELECT state,dispatched_payload_hash FROM ai_operations WHERE task_type='wiki_compiler'"
        ).fetchall()
    assert len(rows) == operations_before + 1, "一次 stale confirm 只能记录一次失败操作"
    assert rows[-1][0] == "failed"
    assert rows[-1][1] is None
    return response


def _prepare(client, raw, key):
    response = client.post("/api/wiki/compiler/prepare", json={
        "raw_id": raw["id"], "idempotency_key": key,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_add_patch_stays_separate_until_single_accept(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    # Replace the deterministic empty result with a valid, raw-bound suggestion.
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {"patches": [_add_patch(raw, project)]}
    preview, response = _compile(client, raw, "add-compile")
    assert response.status_code == 200, response.text
    proposal = response.json()["proposal"]
    patch = proposal["patches"][0]
    assert patch["status"] == "pending"
    assert client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json() == []

    resolved = _resolve(client, proposal, patch, "accept", "accept-add")
    assert resolved.status_code == 200, resolved.text
    accepted = resolved.json()["patch"]["resolution"]["result"]
    current = client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json()
    assert len(current) == 1 and current[0]["id"] == accepted["knowledge_id"]
    assert current[0]["content"] == "本周优先完成方案。"
    assert current[0]["source_refs"] == [raw["source_ref"]]
    assert proposal["id"] != current[0]["id"]
    assert calls and preview["preview"]["wiki_count"] == 0
    replay = _resolve(client, proposal, patch, "accept", "accept-add")
    assert replay.status_code == 200 and replay.json()["replay"] is True
    assert len(client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json()) == 1
    store.shutdown()


def test_edit_accept_writes_user_text_and_reject_never_writes(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    outputs = [{"patches": [_add_patch(raw, project, "AI 候选内容。")]}]
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or outputs.pop(0)
    _preview, response = _compile(client, raw, "edit-compile")
    proposal = response.json()["proposal"]
    patch = proposal["patches"][0]
    edited = _resolve(client, proposal, patch, "edit_accept", "edit-accept", "用户修订后的内容。")
    assert edited.status_code == 200, edited.text
    current = client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json()
    assert len(current) == 1 and current[0]["content"] == "用户修订后的内容。"

    other_raw = _raw(client, project, "D2 Raw 2")
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {"patches": [_add_patch(other_raw, project, "拒绝候选。")]}
    _preview, response = _compile(client, other_raw, "reject-compile")
    proposal = response.json()["proposal"]
    rejected = _resolve(client, proposal, proposal["patches"][0], "reject", "reject-patch")
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["patch"]["status"] == "rejected"
    assert len(client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json()) == 1
    store.shutdown()


def test_rewrite_retire_use_existing_id_and_preserve_history(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    created = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"], "knowledge_type": "fact",
        "content": "旧有虚构事实。", "tags": ["#旧"], "source_refs": [raw["source_ref"]],
        "idempotency_key": "seed-wiki",
    }).json()
    rewrite = {"operation": "rewrite", "target_knowledge_id": created["id"],
               "before_revision": created["revision"], "content": "更新后的虚构事实。",
               "source_refs": [{"kind": "raw_material", "id": raw["id"], "revision": raw["revision"]}],
               "reason": "新原文修正了旧内容。"}
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {"patches": [rewrite]}
    _preview, response = _compile(client, raw, "rewrite-compile")
    proposal = response.json()["proposal"]
    result = _resolve(client, proposal, proposal["patches"][0], "accept", "accept-rewrite")
    assert result.status_code == 200, result.text
    rewritten = result.json()["patch"]["resolution"]["result"]
    assert rewritten["knowledge_id"] == created["id"]
    assert rewritten["revision"] == created["revision"] + 1
    assert client.get(f"/api/wiki/{created['id']}/history").json()["revisions"][-1]["content"] == "更新后的虚构事实。"

    retire = {"operation": "retire", "target_knowledge_id": created["id"],
              "before_revision": rewritten["revision"],
              "source_refs": [{"kind": "raw_material", "id": raw["id"], "revision": raw["revision"]}],
              "reason": "该项不再适用于当前情况。"}
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {"patches": [retire]}
    _preview, response = _compile(client, raw, "retire-compile")
    proposal = response.json()["proposal"]
    result = _resolve(client, proposal, proposal["patches"][0], "accept", "accept-retire")
    assert result.status_code == 200, result.text
    assert client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json() == []
    history = client.get(f"/api/wiki/{created['id']}/history").json()["revisions"]
    assert len(history) == 3 and history[-1]["status"] == "retired"
    assert client.get(f"/api/raw/raw_material/{raw['id']}").json()["content"] == raw["content"]
    store.shutdown()


def test_retire_patch_can_edit_its_reason_without_changing_wiki_content(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    seeded = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"], "knowledge_type": "fact",
        "content": "需要保留的历史内容。", "tags": [], "source_refs": [raw["source_ref"]],
        "idempotency_key": "retire-edit-seed",
    }).json()
    retire = {
        "operation": "retire", "target_knowledge_id": seeded["id"],
        "before_revision": seeded["revision"],
        "source_refs": [{"kind": "raw_material", "id": raw["id"], "revision": raw["revision"]}],
        "reason": "模型给出的退役说明。",
    }
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {"patches": [retire]}
    _preview, response = _compile(client, raw, "retire-edit-reason")
    proposal = response.json()["proposal"]
    patch = proposal["patches"][0]
    resolved = client.post(
        f"/api/wiki/compiler/proposals/{proposal['id']}/patches/{patch['id']}/resolve",
        json={"decision": "edit_accept", "reason": "用户修订后的退役说明。", "idempotency_key": "retire-edit-accept"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["patch"]["resolution"]["edited_reason"] == "用户修订后的退役说明。"
    assert resolved.json()["patch"]["reason"] == "模型给出的退役说明。"
    history = client.get(f"/api/wiki/{seeded['id']}/history").json()["revisions"]
    assert history[-1]["content"] == "需要保留的历史内容。"
    assert history[-1]["status"] == "retired"
    store.shutdown()


def test_two_patches_require_two_individual_decisions_and_no_bulk_route(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    output = {"patches": [_add_patch(raw, project, "第一条。"), _add_patch(raw, project, "第二条。") ]}
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or output
    _preview, response = _compile(client, raw, "two-patches")
    proposal = response.json()["proposal"]
    patches = proposal["patches"]
    assert len(patches) == 2
    first = _resolve(client, proposal, patches[0], "accept", "accept-first")
    assert first.status_code == 200
    assert [item["status"] for item in first.json()["proposal"]["patches"]] == ["accepted", "pending"]
    assert len(client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json()) == 1
    assert client.post(f"/api/wiki/compiler/proposals/{proposal['id']}/resolve", json={"decision": "accept_all"}).status_code in {404, 405}
    second = _resolve(client, proposal, patches[1], "reject", "reject-second")
    assert second.status_code == 200
    assert second.json()["proposal"]["status"] == "resolved"
    assert len(client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json()) == 1
    store.shutdown()


def test_invalid_patch_shapes_types_sources_and_targets_fail_closed(tmp_path):
    cases = [
        {"operation": "delete", "source_refs": []},
        {"operation": "add", "scope_type": "project", "knowledge_type": "unknown"},
        {"operation": "add", "scope_type": "project", "knowledge_type": "fact", "content": "x", "tags": [], "source_refs": None, "reason": "x"},
        {"operation": "add", "scope_type": "project", "scope_id": "foreign", "knowledge_type": "fact", "content": "x", "tags": [], "source_refs": [{"kind": "raw_material", "id": "foreign", "revision": 1}], "reason": "x"},
        {"operation": "rewrite", "target_knowledge_id": "missing", "before_revision": 1, "content": "x", "source_refs": [{"kind": "raw_material", "id": "raw", "revision": 1}], "reason": "x"},
    ]
    for index, candidate in enumerate(cases):
        client, store, calls = _harness(tmp_path / str(index), {"patches": []})
        project = _project(client)
        raw = _raw(client, project, f"Raw {index}")
        good = _add_patch(raw, project)
        if candidate.get("operation") == "add":
            good.update(candidate)
        else:
            good = candidate
        store.provider.complete = lambda payload, value=good: calls.append(deepcopy(payload)) or {"patches": [value]}
        _preview, response = _compile(client, raw, f"invalid-{index}")
        assert response.status_code == 422, response.text
        assert _records(store, "wiki_compiler_proposal") == []
        assert client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json() == []
        assert len(calls) == 1
        store.shutdown()


def test_two_operations_for_same_wiki_target_fail_closed(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    current = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"],
        "knowledge_type": "fact", "content": "当前虚构知识。", "tags": [],
        "source_refs": [raw["source_ref"]], "idempotency_key": "target-duplicate-seed",
    }).json()
    common = {
        "target_knowledge_id": current["id"], "before_revision": current["revision"],
        "source_refs": [{"kind": "raw_material", "id": raw["id"], "revision": raw["revision"]}],
        "reason": "虚构来源说明。",
    }
    output = {"patches": [
        {"operation": "rewrite", **common, "content": "改写候选。"},
        {"operation": "retire", **common},
    ]}
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or output
    _preview, response = _compile(client, raw, "duplicate-target-ops")
    assert response.status_code == 422
    assert _records(store, "wiki_compiler_proposal") == []
    still_current = client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json()
    assert len(still_current) == 1 and still_current[0]["content"] == "当前虚构知识。"
    assert len(calls) == 1
    store.shutdown()


@pytest.mark.parametrize("operation", ["rewrite", "retire"])
def test_wiki_target_change_after_proposal_rejects_stale_patch(tmp_path, operation):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    seeded = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"], "knowledge_type": "fact",
        "content": "旧内容。", "tags": [], "source_refs": [raw["source_ref"]],
        "idempotency_key": "stale-seed",
    }).json()
    patch = {
        "operation": operation, "target_knowledge_id": seeded["id"],
        "before_revision": seeded["revision"],
        "source_refs": [{"kind": "raw_material", "id": raw["id"], "revision": raw["revision"]}],
        "reason": "修正。",
    }
    if operation == "rewrite":
        patch["content"] = "AI 新内容。"
    output = {"patches": [patch]}
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or output
    _preview, response = _compile(client, raw, "stale-target")
    proposal = response.json()["proposal"]
    changed = client.post(f"/api/wiki/{seeded['id']}", json={
        "content": "人工先更新。", "expected_revision": seeded["revision"],
        "idempotency_key": "manual-change",
    })
    assert changed.status_code == 200
    rejected = _resolve(client, proposal, proposal["patches"][0], "accept", "stale-accept")
    assert rejected.status_code == 409
    current = client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json()
    assert current[0]["content"] == "人工先更新。" and current[0]["id"] == seeded["id"]
    store.shutdown()


def test_prepare_stales_if_scope_changes_before_confirmation_without_dispatch(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    intent = {"raw_id": raw["id"], "idempotency_key": "scope-stale"}
    preview = client.post("/api/wiki/compiler/prepare", json=intent).json()
    updated = client.post(f"/api/work/projects/{project['id']}", json={
        "name": "改名后的 D2 项目", "description": "", "tags": [], "status": "active",
        "status_note": "", "employment_id": None, "expected_revision": project["revision"],
        "idempotency_key": "rename-scope",
    })
    assert updated.status_code == 200
    _assert_pre_dispatch_stale(client, store, calls, intent, preview)
    store.shutdown()


def test_prepare_stales_if_current_wiki_changes_before_confirmation(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    seeded = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"], "knowledge_type": "fact",
        "content": "初始当前知识。", "tags": [], "source_refs": [raw["source_ref"]],
        "idempotency_key": "pre-confirm-seed",
    }).json()
    intent = {"raw_id": raw["id"], "idempotency_key": "wiki-stale-confirm"}
    preview = client.post("/api/wiki/compiler/prepare", json=intent).json()
    changed = client.post(f"/api/wiki/{seeded['id']}", json={
        "content": "人工在确认前改过。", "expected_revision": seeded["revision"],
        "idempotency_key": "pre-confirm-change",
    })
    assert changed.status_code == 200
    _assert_pre_dispatch_stale(client, store, calls, intent, preview)
    store.shutdown()


@pytest.mark.parametrize("change", ["content", "revision"])
def test_prepare_stales_if_raw_changes_before_confirmation_without_dispatch(tmp_path, change):
    from workbench.core import digest

    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    intent = {"raw_id": raw["id"], "idempotency_key": "raw-stale-" + change}
    preview = _prepare(client, raw, intent["idempotency_key"])
    with store.connect() as connection:
        stored = store._get(connection, raw["id"], "raw_material", record=True)
        if change == "content":
            stored["content"] = "虚构原文在预览后发生变化。"
            stored["hash"] = digest({
                key: stored[key]
                for key in ("scope_type", "scope_id", "source_kind", "title", "content")
            })
        else:
            stored["revision"] += 1
        store._record(connection, "raw_material", stored)
    _assert_pre_dispatch_stale(client, store, calls, intent, preview)
    store.shutdown()


@pytest.mark.parametrize("change", ["content", "revision"])
def test_prepare_stales_if_current_wiki_content_or_revision_changes(tmp_path, change):
    import json

    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    seeded = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"],
        "knowledge_type": "fact", "content": "预览时的当前知识。", "tags": [],
        "source_refs": [raw["source_ref"]], "idempotency_key": "wiki-change-seed-" + change,
    }).json()
    intent = {"raw_id": raw["id"], "idempotency_key": "wiki-change-" + change}
    preview = _prepare(client, raw, intent["idempotency_key"])
    with store.connect() as connection:
        if change == "revision":
            current = store._get(connection, seeded["id"], "wiki_knowledge")
            store._save(connection, "wiki_knowledge", current, seeded["revision"])
        else:
            row = connection.execute(
                "SELECT revision,body FROM current WHERE id=?", (seeded["id"],)
            ).fetchone()
            body = json.loads(row[1])
            body["content"] = "预览后变化的当前知识。"
            connection.execute(
                "UPDATE current SET body=? WHERE id=?",
                (json.dumps(body, ensure_ascii=False, sort_keys=True), seeded["id"]),
            )
            assert row[0] == body["revision"]
    _assert_pre_dispatch_stale(client, store, calls, intent, preview)
    store.shutdown()


def test_preview_manifest_ignores_ui_refresh_time_and_storage_order(tmp_path, monkeypatch):
    import json
    import workbench.outbound_policy as outbound_policy

    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client, "D2 不变语义项目")
    raw = _raw(client, project, "D2 不变语义 Raw")
    for index in range(3):
        response = client.post("/api/wiki", json={
            "scope_type": "project", "scope_id": project["id"],
            "knowledge_type": "fact", "content": f"稳定知识 {index}。", "tags": [f"#tag{index}"],
            "source_refs": [], "idempotency_key": f"stable-wiki-{index}",
        })
        assert response.status_code == 200, response.text

    first = _prepare(client, raw, "stable-preview-one")
    assert len(_records(store, "ai_preparation")) == 1
    with store.connect(False) as connection:
        first_preparation = store._get(
            connection, first["prepared_id"], "ai_preparation", record=True,
        )
    workspace = client.get(
        f"/api/wiki/workspace?scope_type=project&scope_id={project['id']}"
    )
    assert workspace.status_code == 200

    # Re-key the serialized Project fields and move only a non-semantic timestamp.
    with store.connect() as connection:
        project_row = connection.execute(
            "SELECT body FROM current WHERE id=?", (project["id"],)
        ).fetchone()
        project_body = json.loads(project_row[0])
        project_body["updated_at"] = "2099-01-01T00:00:00+00:00"
        reversed_project_body = dict(reversed(list(project_body.items())))
        connection.execute(
            "UPDATE current SET body=? WHERE id=?",
            (json.dumps(reversed_project_body, ensure_ascii=False), project["id"]),
        )

        # Change physical row order without changing any Wiki object or revision.
        rows = connection.execute(
            "SELECT id,kind,revision,body FROM current WHERE kind='wiki_knowledge'"
        ).fetchall()
        connection.execute("DELETE FROM current WHERE kind='wiki_knowledge'")
        for row in reversed(rows):
            connection.execute("INSERT INTO current VALUES(?,?,?,?)", tuple(row))

    real_now = outbound_policy.now
    monkeypatch.setattr(outbound_policy, "now", lambda: "2099-01-02T00:00:00+00:00")
    second = _prepare(client, raw, "stable-preview-two")
    monkeypatch.setattr(outbound_policy, "now", real_now)
    with store.connect(False) as connection:
        second_preparation = store._get(
            connection, second["prepared_id"], "ai_preparation", record=True,
        )

    assert second["payload_hash"] == first["payload_hash"]
    assert second["readable_context"] == first["readable_context"]
    assert second_preparation["manifest"] == first_preparation["manifest"]
    assert len(_records(store, "ai_preparation")) == 2

    confirmed = client.post("/api/wiki/compiler/execute", json={
        "raw_id": raw["id"], "idempotency_key": "stable-preview-one",
        "prepared_id": first["prepared_id"], "payload_hash": first["payload_hash"],
        "confirm_outbound": True,
    })
    assert confirmed.status_code == 200, confirmed.text
    assert len(calls) == 1
    assert confirmed.json()["status"] == "no_changes"
    store.shutdown()


def test_prepare_fails_closed_when_compiler_exceeds_shared_source_budget(tmp_path):
    from workbench.outbound_policy import SOURCE_LIMIT

    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client)
    raw = _raw(client, project)
    for index in range(SOURCE_LIMIT):
        response = client.post("/api/wiki", json={
            "scope_type": "project", "scope_id": project["id"],
            "knowledge_type": "fact", "content": f"预算测试知识 {index}。",
            "tags": [], "source_refs": [raw["source_ref"]],
            "idempotency_key": f"budget-wiki-{index}",
        })
        assert response.status_code == 200, response.text

    preview = client.post("/api/wiki/compiler/prepare", json={
        "raw_id": raw["id"], "idempotency_key": "over-source-budget",
    })
    assert preview.status_code == 422
    assert calls == []
    store.shutdown()


def test_model_cannot_cite_another_raw_even_when_that_raw_exists(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    project = _project(client, "D2 原文项目")
    other_project = _project(client, "D2 另一项目")
    selected_raw = _raw(client, project, "选中 Raw")
    other_raw = _raw(client, other_project, "其他 Raw")
    patch = _add_patch(selected_raw, project)
    patch["source_refs"] = [{
        "kind": "raw_material", "id": other_raw["id"], "revision": other_raw["revision"],
    }]
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {"patches": [patch]}
    _preview, response = _compile(client, selected_raw, "foreign-raw-ref")
    assert response.status_code == 422
    assert _records(store, "wiki_compiler_proposal") == []
    packet = json.loads(calls[0]["messages"][1]["content"])
    assert "其他 Raw" not in json.dumps(packet)
    assert client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json() == []
    store.shutdown()


def test_provider_outcome_unknown_is_not_automatically_retried(tmp_path):
    from workbench.model_gateway import GatewayError

    client, store, calls = _harness(tmp_path, GatewayError("timeout", "synthetic lost response"))
    project = _project(client)
    raw = _raw(client, project)
    intent = {"raw_id": raw["id"], "idempotency_key": "unknown-result"}
    preview = client.post("/api/wiki/compiler/prepare", json=intent).json()
    request = {**intent, "prepared_id": preview["prepared_id"],
               "payload_hash": preview["payload_hash"], "confirm_outbound": True}
    first = client.post("/api/wiki/compiler/execute", json=request)
    second = client.post("/api/wiki/compiler/execute", json=request)
    assert first.status_code == second.status_code == 409
    assert first.json()["state"] == second.json()["state"] == "outcome_unknown"
    assert len(calls) == 1
    assert _records(store, "wiki_compiler_proposal") == []
    store.shutdown()


def test_test_provider_e2e_returns_successful_empty_result(tmp_path):
    client, store, calls = _harness(tmp_path, None)
    project = _project(client)
    raw = _raw(client, project)
    _preview, response = _compile(client, raw, "test-provider-empty")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "no_changes"
    assert len(calls) == 1
    assert client.get(f"/api/wiki?scope_type=project&scope_id={project['id']}").json() == []
    store.shutdown()


def test_context_includes_only_explicit_related_scopes_and_active_wiki(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    episode = client.post("/api/journey/episodes", json={
        "company": "虚构任职公司", "role": "产品总监",
    }).json()
    employment = next(item for item in client.get("/api/work-domain").json()["employments"]
                      if item["legacy_episode_id"] == episode["id"])
    person = client.post(f"/api/work/employments/{employment['id']}/persons", json={
        "name": "虚构确认人物", "role": "产品总监", "idempotency_key": "confirmed-person",
    }).json()
    project = client.post("/api/work/projects", json={
        "name": "D2 关联项目", "employment_id": employment["id"],
        "idempotency_key": "related-project",
    }).json()
    linked = client.post(f"/api/work/projects/{project['id']}/participants", json={
        "person_id": person["id"], "role": "Reviewer", "idempotency_key": "link-confirmed-person",
    })
    assert linked.status_code == 200, linked.text
    raw = _raw(client, project)

    other_project = _project(client, "D2 隔离项目")
    other_raw = _raw(client, other_project, "隔离来源")
    client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"], "knowledge_type": "fact",
        "content": "D2 允许的项目知识。", "tags": [], "source_refs": [raw["source_ref"]],
        "idempotency_key": "d2-own-wiki",
    })
    client.post("/api/wiki", json={
        "scope_type": "employment", "scope_id": employment["id"], "knowledge_type": "observation",
        "content": "D2 允许的任职知识。", "tags": [], "source_refs": [raw["source_ref"]],
        "idempotency_key": "d2-own-employment-wiki",
    })
    client.post("/api/wiki", json={
        "scope_type": "person", "scope_id": person["id"], "knowledge_type": "fact",
        "content": "D2 允许的人物知识。", "tags": [], "source_refs": [raw["source_ref"]],
        "idempotency_key": "d2-own-person-wiki",
    })
    retired = client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": project["id"], "knowledge_type": "fact",
        "content": "不应进入 Context 的退役知识。", "tags": [], "source_refs": [raw["source_ref"]],
        "idempotency_key": "d2-retired-wiki",
    }).json()
    client.post(f"/api/wiki/{retired['id']}", json={
        "status": "retired", "expected_revision": retired["revision"],
        "idempotency_key": "d2-retire-wiki",
    })
    client.post("/api/wiki", json={
        "scope_type": "project", "scope_id": other_project["id"], "knowledge_type": "fact",
        "content": "FOREIGN-PROJECT-SENTINEL", "tags": [], "source_refs": [other_raw["source_ref"]],
        "idempotency_key": "d2-foreign-wiki",
    })
    other_episode = client.post("/api/journey/episodes", json={
        "company": "不可读的其他任职", "role": "隔离角色",
    }).json()
    other_employment = next(item for item in client.get("/api/work-domain").json()["employments"]
                            if item["legacy_episode_id"] == other_episode["id"])
    other_employment_raw = client.post("/api/raw", json={
        "scope_type": "employment", "scope_id": other_employment["id"],
        "source_kind": "manual_text", "title": "隔离任职原文",
        "content": "FOREIGN-EMPLOYMENT-RAW-SENTINEL", "idempotency_key": "other-employment-raw",
    }).json()
    client.post("/api/wiki", json={
        "scope_type": "employment", "scope_id": other_employment["id"],
        "knowledge_type": "fact", "content": "FOREIGN-EMPLOYMENT-WIKI-SENTINEL", "tags": [],
        "source_refs": [other_employment_raw["source_ref"]], "idempotency_key": "other-employment-wiki",
    })
    opp = client.post("/api/opportunities", json={
        "company_name": "隔离机会", "title": "隔离岗位", "jd": "FOREIGN-OPPORTUNITY-SENTINEL",
        "idempotency_key": "foreign-opportunity",
    })
    assert opp.status_code == 200, opp.text
    client.post("/api/wiki", json={
        "scope_type": "opportunity", "scope_id": opp.json()["id"], "knowledge_type": "fact",
        "content": "FOREIGN-OPPORTUNITY-WIKI-SENTINEL", "tags": [], "source_refs": [],
        "idempotency_key": "foreign-opportunity-wiki",
    })

    original_current = store._current
    original_records = store._records

    def guarded_current(c, kind):
        if kind in {"wiki_knowledge", "work_person"}:
            raise AssertionError("Compiler must query only explicitly scoped Wiki and People")
        return original_current(c, kind)

    def guarded_records(c, kind):
        if kind == "work_project_participant":
            raise AssertionError("Compiler must query participants for the selected Project only")
        return original_records(c, kind)

    store._current = guarded_current
    store._records = guarded_records
    _preview, response = _compile(client, raw, "scope-closure")
    assert response.status_code == 200, response.text
    packet = json.loads(calls[-1]["messages"][1]["content"])
    scope_keys = {(item["type"], item["stable_id"]) for item in packet["scopes"]}
    assert scope_keys == {
        ("project", project["id"]), ("employment", employment["id"]), ("person", person["id"]),
    }
    person_scope = next(item for item in packet["scopes"] if item["type"] == "person")
    assert person_scope["minimal_identity"]["employment_role"] == "产品总监"
    assert person_scope["minimal_identity"]["project_role"] == "Reviewer"
    encoded = json.dumps(packet, ensure_ascii=False)
    assert "FOREIGN-PROJECT-SENTINEL" not in encoded
    assert "FOREIGN-EMPLOYMENT-RAW-SENTINEL" not in encoded
    assert "FOREIGN-EMPLOYMENT-WIKI-SENTINEL" not in encoded
    assert "FOREIGN-OPPORTUNITY-SENTINEL" not in encoded
    assert "FOREIGN-OPPORTUNITY-WIKI-SENTINEL" not in encoded
    assert "不应进入 Context 的退役知识。" not in encoded
    assert "D2 允许的项目知识。" in encoded
    assert "D2 允许的任职知识。" in encoded
    assert "D2 允许的人物知识。" in encoded
    assert len(packet["current_knowledge"]) == 3
    assert all("source_refs" not in item for item in packet["current_knowledge"])
    assert all(set(item) == {
        "knowledge_id", "type", "content", "tags", "revision", "scope_type", "scope_id",
    } for item in packet["current_knowledge"])
    store._current = original_current
    store._records = original_records
    store.shutdown()


def test_unresolved_person_mention_never_becomes_person_scope_or_patch(tmp_path):
    client, store, calls = _harness(tmp_path, {"patches": []})
    episode = client.post("/api/journey/episodes", json={"company": "虚构公司", "role": "虚构职位"}).json()
    employment = next(item for item in client.get("/api/work-domain").json()["employments"]
                      if item["legacy_episode_id"] == episode["id"])
    unresolved = client.post(f"/api/work/employments/{employment['id']}/persons", json={
        "name": "未确认的虚构名字", "role": "", "identity_status": "unresolved",
        "idempotency_key": "unresolved-person",
    })
    assert unresolved.status_code == 200, unresolved.text
    raw_response = client.post("/api/raw", json={
        "scope_type": "employment", "scope_id": employment["id"],
        "source_kind": "manual_text", "title": "提到未确认人物",
        "content": "虚构记录：未确认的虚构名字说了几句话。",
        "idempotency_key": "unresolved-mention-raw",
    })
    assert raw_response.status_code == 200
    raw = raw_response.json()
    preview = client.post("/api/wiki/compiler/prepare", json={
        "raw_id": raw["id"], "idempotency_key": "unresolved-context",
    })
    assert preview.status_code == 200
    intent = {"raw_id": raw["id"], "idempotency_key": "unresolved-context"}
    # Prepare rejects this candidate locally because the Person is not one of the disclosed scopes.
    store.provider.complete = lambda payload: calls.append(deepcopy(payload)) or {"patches": [{
        "operation": "add", "scope_type": "person", "scope_id": unresolved.json()["id"],
        "knowledge_type": "fact", "content": "未确认者提出的要求。", "tags": [],
        "source_refs": [{"kind": "raw_material", "id": raw["id"], "revision": raw["revision"]}],
        "reason": "原文有名字。",
    }]}
    response = client.post("/api/wiki/compiler/execute", json={
        **intent, "prepared_id": preview.json()["prepared_id"],
        "payload_hash": preview.json()["payload_hash"], "confirm_outbound": True,
    })
    assert response.status_code == 422
    packet = json.loads(calls[-1]["messages"][1]["content"])
    assert all(item["stable_id"] != unresolved.json()["id"] for item in packet["scopes"])
    assert all(item["scope_type"] != "person" for item in packet["current_knowledge"])
    assert _records(store, "wiki_compiler_proposal") == []
    store.shutdown()
