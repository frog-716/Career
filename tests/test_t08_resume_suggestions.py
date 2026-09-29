"""T08 field-level resume AI suggestions over isolated fake providers."""
from copy import deepcopy
import json

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store, digest
from workbench.model_gateway import OpenAICompatibleAdapter
from workbench.opportunity import create_opportunity
from workbench.providers import TestProvider
from workbench.resume_documents import _resume_output_schema


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


def resume_fixture(tmp_path, provider):
    store = Store(tmp_path / "data", provider)
    client = TestClient(create_app(store), headers=HEADERS)
    opportunity = create_opportunity(store, {
        "company_name": "T08 虚构公司",
        "title": "T08 虚构岗位",
        "jd": "只用于 T08 的虚构 JD",
        "idempotency_key": "t08-opportunity",
    })
    started = client.post(
        f"/api/opportunities/{opportunity['id']}/resume/start",
        json={
            "expected_opportunity_revision": opportunity["revision"],
            "idempotency_key": "t08-resume-start",
            "source": {"kind": "blank"},
        },
    )
    assert started.status_code == 200, started.text
    document_id = started.json()["document_id"]
    document = {
        "schemaVersion": 1,
        "profile": {
            "id": "t08-profile",
            "name": "虚构候选人甲",
            "contacts": [{
                "id": "t08-email",
                "kind": "identity",
                "content": "邮箱：candidate@example.test",
                "href": "",
            }],
        },
        "sections": [
            {
                "id": "section-skills",
                "type": "skills",
                "title": "专业技能",
                "items": [{"id": "t08-skill", "content": "Python"}],
            },
            {
                "id": "section-experience",
                "type": "experience",
                "title": "工作经历",
                "items": [{
                    "id": "t08-experience",
                    "organization": "虚构公司甲",
                    "role": "软件工程师",
                    "date": "2024-2025",
                    "bullets": [{"id": "t08-bullet", "content": "维护内部工具"}],
                }],
            },
            {
                "id": "section-projects",
                "type": "projects",
                "title": "项目经历",
                "items": [{
                    "id": "t08-project",
                    "title": "虚构项目",
                    "responsibility": "负责实现",
                    "date": "2025",
                    "bullets": [{"id": "t08-project-bullet", "content": "完成接口"}],
                }],
            },
        ],
        "formatting": {},
        "meta": {"source_refs": []},
    }
    saved = client.put(f"/api/resume-documents/{document_id}", json={
        "document": document,
        "expected_revision": started.json()["revision"],
    })
    assert saved.status_code == 200, saved.text
    # This is a pre-D1 confirmed fact, planted as synthetic history. Its
    # selected-fact behavior remains under test after old intake is retired.
    with store.connect() as connection:
        store._record(connection, "knowledge_source", {
            "id": "t08-old-source", "title": "T08 虚构来源",
            "content": "只用于 T08 的已确认虚构来源",
            "source_type": "text", "locator": "", "scope_type": "personal",
            "scope_id": "", "created_at": "2026-01-01T00:00:00Z",
        })
        entry = store._save(connection, "wiki_entry", {
            "id": "t08-old-entry", "title": "T08 虚构事实",
            "content": "只用于 T08 的已确认虚构事实",
            "entry_type": "project", "source_ids": ["t08-old-source"],
            "scope_type": "personal", "scope_id": "", "status": "active",
            "verification": "user_asserted", "created_at": "2026-01-01T00:00:00Z",
        }, 0)
    assert entry in client.get("/api/knowledge").json()["entries"]
    selected = client.post(f"/api/resume-documents/{document_id}/select-facts", json={
        "expected_revision": saved.json()["revision"],
        "selections": [{
            "id": entry["id"],
            "revision": entry["revision"],
            "section_type": "skills",
        }],
        "include_profile": False,
        "profile_revision": 0,
        "idempotency_key": "t08-select-source",
    })
    assert selected.status_code == 200, selected.text
    return client, store, selected.json()


class FieldSuggestionProvider(TestProvider):
    def __init__(self, changes=None):
        self.call_count = 0
        self.changes = changes

    def complete(self, payload):
        self.call_count += 1
        packet = json.loads(payload["messages"][1]["content"])
        current = next(
            source["selected_content"]
            for source in packet["sources"]
            if source.get("purpose") == "current_resume_document"
        )
        changes = self.changes(current) if callable(self.changes) else (self.changes or [])
        return {"changes": deepcopy(changes), "suggestions": [f"fake-call-{self.call_count}"], "claims": []}


class LegacyWholeDocumentProvider(TestProvider):
    def __init__(self):
        self.call_count = 0

    def complete(self, payload):
        self.call_count += 1
        packet = json.loads(payload["messages"][1]["content"])
        current = next(
            source["selected_content"]
            for source in packet["sources"]
            if source.get("purpose") == "current_resume_document"
        )
        proposed = deepcopy(current)
        proposed["profile"]["name"] = "不应被整稿替换"
        return {"document": proposed, "suggestions": ["legacy whole document"]}


class ObservedDeepSeekShapeProvider(TestProvider):
    """Redacted fixture for the observed extra-field validation failure."""

    def __init__(self):
        self.call_count = 0

    def complete(self, payload):
        self.call_count += 1
        packet = json.loads(payload["messages"][1]["content"])
        current = next(
            source["selected_content"]
            for source in packet["sources"]
            if source.get("purpose") == "current_resume_document"
        )
        skill = current["sections"][0]["items"][0]["content"]
        # The retained audit evidence identifies this validator branch, but not
        # the real provider's extra key. Keep that key explicitly synthetic.
        return {
            "changes": [{
                "change_id": "observed-shape-change",
                "item_id": "t08-skill",
                "field": "content",
                "before_hash": digest(skill),
                "proposed_text": "虚构的兼容性复现",
                "source_refs": [],
                "reason": "脱敏失败形态复现",
                "requires_fact_check": False,
                "synthetic_provider_extra_field": "not from retained payload",
            }],
            "suggestions": [],
            "claims": [],
        }


def prepare_request(client, document_id, key):
    seed = {"instruction": "只优化虚构简历表达", "idempotency_key": key}
    prepared = client.post(f"/api/resume-documents/{document_id}/ai-suggest", json=seed)
    assert prepared.status_code == 409, prepared.text
    details = prepared.json()
    return {
        **seed,
        "prepared_id": details["prepared_id"],
        "payload_hash": details["payload_hash"],
        "confirm_outbound": True,
    }


def test_legacy_whole_document_output_is_rejected_without_writing(tmp_path):
    provider = LegacyWholeDocumentProvider()
    client, store, before = resume_fixture(tmp_path, provider)
    body = prepare_request(client, before["document_id"], "t08-legacy-output")

    response = client.post(f"/api/resume-documents/{before['document_id']}/ai-suggest", json=body)

    assert response.status_code == 422, response.text
    assert "unsupported_proposal_format" in response.text
    assert provider.call_count == 1
    assert client.get(f"/api/resume-documents/{before['document_id']}").json() == before
    assert client.get(f"/api/resume-documents/{before['document_id']}/ai-proposals").json() == []
    with store.connect(False) as connection:
        assert connection.execute("SELECT state,error_code FROM ai_operations").fetchone() == ("failed", "invalid_result")


def test_observed_deepseek_extra_field_shape_reproduces_invalid_result(tmp_path):
    provider = ObservedDeepSeekShapeProvider()
    client, store, before = resume_fixture(tmp_path, provider)
    response = client.post(
        f"/api/resume-documents/{before['document_id']}/ai-suggest",
        json=prepare_request(client, before["document_id"], "t08-observed-extra-field"),
    )

    assert response.status_code == 422, response.text
    assert "unsupported_proposal_format: change 含有未支持字段" in response.text
    assert provider.call_count == 1
    assert client.get(f"/api/resume-documents/{before['document_id']}/ai-proposals").json() == []
    with store.connect(False) as connection:
        assert connection.execute("SELECT state,error_code FROM ai_operations").fetchone() == ("failed", "invalid_result")


def test_resume_output_contract_is_explicit_for_json_only_deepseek_mode():
    adapter = OpenAICompatibleAdapter({
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-flash",
    }, "synthetic-key", runtime_mode="AI_ENABLED")
    payload = adapter.build_payload({"task_type": "resume_optimization"}, _resume_output_schema())
    system = payload["messages"][0]["content"]

    assert payload["response_format"] == {"type": "json_object"}
    assert payload["max_tokens"] == 4096
    assert "只能输出一个 JSON 对象" in system
    assert "禁止 Markdown code fence" in system
    assert "禁止前后解释文字" in system
    assert "禁止输出合同未列出的字段" in system
    assert "最小完整 JSON 示例" in system
    assert "虚构示例" in system
    for field in ("change_id", "item_id", "field", "before_hash", "proposed_text", "source_refs", "reason", "requires_fact_check"):
        assert field in system
    schema = _resume_output_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["changes"]["items"]["additionalProperties"] is False


def test_field_changes_are_whitelisted_and_selected_atomically(tmp_path):
    def changes(document):
        skill = document["sections"][0]["items"][0]["content"]
        bullet = document["sections"][1]["items"][0]["bullets"][0]["content"]
        return [
            {
                "change_id": "t08-change-skill",
                "item_id": "t08-skill",
                "field": "content",
                "before_hash": digest(skill),
                "proposed_text": "Python 与自动化测试",
                "source_refs": [],
                "reason": "表达调整",
                "requires_fact_check": False,
            },
            {
                "change_id": "t08-change-bullet",
                "item_id": "t08-experience",
                "field": "bullets.t08-bullet.content",
                "before_hash": digest(bullet),
                "proposed_text": "维护并改进内部工具",
                "source_refs": [],
                "reason": "表达调整",
                "requires_fact_check": False,
            },
        ]

    provider = FieldSuggestionProvider(changes)
    client, _, before = resume_fixture(tmp_path, provider)
    body = prepare_request(client, before["document_id"], "t08-selective-apply")
    proposal_response = client.post(f"/api/resume-documents/{before['document_id']}/ai-suggest", json=body)
    assert proposal_response.status_code == 200, proposal_response.text
    proposal = proposal_response.json()
    assert [change["field"] for change in proposal["changes"]] == [
        "content", "bullets.t08-bullet.content"
    ]
    assert proposal["changes"][0]["source_refs"] == []

    edited = client.post(
        f"/api/resume-documents/{before['document_id']}/ai-proposals/{proposal['id']}/resolve",
        json={
            "decision": "accept",
            "changes": [{
                "change_id": "t08-change-skill",
                "selected": True,
                "proposed_text": "Python 与隔离自动化测试",
            }, {
                "change_id": "t08-change-bullet",
                "selected": False,
                "proposed_text": "用户没有选择的改写",
            }],
        },
    )
    assert edited.status_code == 200, edited.text
    result = edited.json()
    document = result["document"]["document"]
    assert result["proposal"]["status"] == "accepted"
    assert document["sections"][0]["items"][0]["content"] == "Python 与隔离自动化测试"
    assert document["sections"][1]["items"][0]["bullets"][0]["content"] == "维护内部工具"
    assert document["profile"]["name"] == before["document"]["profile"]["name"]
    assert document["meta"]["source_refs"] == before["document"]["meta"]["source_refs"]
    assert document["sections"][1]["items"][0]["organization"] == "虚构公司甲"

    replay = client.post(
        f"/api/resume-documents/{before['document_id']}/ai-proposals/{proposal['id']}/resolve",
        json={"decision": "accept"},
    )
    assert replay.status_code == 200
    assert replay.json()["status"] == "accepted"
    assert client.get(f"/api/resume-documents/{before['document_id']}").json()["revision"] == before["revision"] + 1
    assert provider.call_count == 1


def test_invalid_item_and_fact_fields_fail_without_proposal(tmp_path):
    def changes(_document):
        return [{
            "change_id": "t08-invalid-item",
            "item_id": "not-in-this-document",
            "field": "content",
            "before_hash": digest("unknown"),
            "proposed_text": "不应写入",
            "reason": "越权",
        }]

    provider = FieldSuggestionProvider(changes)
    client, _, before = resume_fixture(tmp_path, provider)
    response = client.post(
        f"/api/resume-documents/{before['document_id']}/ai-suggest",
        json=prepare_request(client, before["document_id"], "t08-invalid-item"),
    )
    assert response.status_code == 422
    assert "item" in response.text
    assert client.get(f"/api/resume-documents/{before['document_id']}/ai-proposals").json() == []


def test_locked_identity_field_is_rejected_and_numeric_change_is_flagged(tmp_path):
    def changes(document):
        experience = document["sections"][1]["items"][0]
        return [{
            "change_id": "t08-locked-role",
            "item_id": experience["id"],
            "field": "role",
            "before_hash": digest(experience["role"]),
            "proposed_text": "首席工程师",
            "reason": "身份字段改写",
        }]

    provider = FieldSuggestionProvider(changes)
    client, _, before = resume_fixture(tmp_path, provider)
    response = client.post(
        f"/api/resume-documents/{before['document_id']}/ai-suggest",
        json=prepare_request(client, before["document_id"], "t08-locked-role"),
    )
    assert response.status_code == 422
    assert "field" in response.text

    def numeric(_document):
        return [{
            "change_id": "t08-numeric",
            "item_id": "t08-skill",
            "field": "content",
            "before_hash": digest("Python"),
            "proposed_text": "Python，性能提升 300%",
            "reason": "表达调整",
            "requires_fact_check": False,
        }]

    provider.changes = numeric
    numeric_body = prepare_request(client, before["document_id"], "t08-numeric")
    numeric_response = client.post(
        f"/api/resume-documents/{before['document_id']}/ai-suggest", json=numeric_body
    )
    assert numeric_response.status_code == 200, numeric_response.text
    assert numeric_response.json()["changes"][0]["requires_fact_check"] is True


def test_pending_suggestions_survive_reopen_without_provider_call(tmp_path):
    provider = FieldSuggestionProvider([])
    client, store, before = resume_fixture(tmp_path, provider)
    body = prepare_request(client, before["document_id"], "t08-reopen")
    created = client.post(f"/api/resume-documents/{before['document_id']}/ai-suggest", json=body)
    assert created.status_code == 200, created.text
    assert provider.call_count == 1

    reopened_store = Store(store.data_dir, provider)
    reopened_client = TestClient(create_app(reopened_store), headers=HEADERS)
    pending = reopened_client.get(f"/api/resume-documents/{before['document_id']}/ai-proposals")
    assert pending.status_code == 200
    assert pending.json()[0]["status"] == "pending"
    assert provider.call_count == 1


def test_stale_document_revision_blocks_apply_without_partial_write(tmp_path):
    def changes(document):
        value = document["sections"][0]["items"][0]["content"]
        return [{
            "change_id": "t08-stale",
            "item_id": "t08-skill",
            "field": "content",
            "before_hash": digest(value),
            "proposed_text": "过期提案",
            "reason": "表达调整",
        }]

    provider = FieldSuggestionProvider(changes)
    client, _, before = resume_fixture(tmp_path, provider)
    body = prepare_request(client, before["document_id"], "t08-stale")
    proposal = client.post(f"/api/resume-documents/{before['document_id']}/ai-suggest", json=body).json()
    changed = deepcopy(before["document"])
    changed["sections"][0]["items"][0]["content"] = "用户当前输入"
    saved = client.put(f"/api/resume-documents/{before['document_id']}", json={
        "document": changed,
        "expected_revision": before["revision"],
    })
    assert saved.status_code == 200
    response = client.post(
        f"/api/resume-documents/{before['document_id']}/ai-proposals/{proposal['id']}/resolve",
        json={"decision": "accept"},
    )
    assert response.status_code == 409
    current = client.get(f"/api/resume-documents/{before['document_id']}").json()
    assert current["document"]["sections"][0]["items"][0]["content"] == "用户当前输入"


def test_source_refs_outside_manifest_are_rejected(tmp_path):
    def changes(_document):
        return [{
            "change_id": "t08-forged-source",
            "item_id": "t08-skill",
            "field": "content",
            "before_hash": digest("Python"),
            "proposed_text": "引用伪造来源",
            "source_refs": [{"id": "not-in-manifest", "revision": 99}],
            "reason": "越权引用",
        }]

    provider = FieldSuggestionProvider(changes)
    client, _, before = resume_fixture(tmp_path, provider)
    response = client.post(
        f"/api/resume-documents/{before['document_id']}/ai-suggest",
        json=prepare_request(client, before["document_id"], "t08-forged-source"),
    )
    assert response.status_code == 422
    assert "source_refs" in response.text
    assert client.get(f"/api/resume-documents/{before['document_id']}/ai-proposals").json() == []


def test_long_field_change_is_applied_without_changing_structure(tmp_path):
    long_text = "可核对的长表述" * 1200

    def changes(_document):
        return [{
            "change_id": "t08-long-content",
            "item_id": "t08-skill",
            "field": "content",
            "before_hash": digest("Python"),
            "proposed_text": long_text,
            "reason": "保留长内容",
        }]

    provider = FieldSuggestionProvider(changes)
    client, _, before = resume_fixture(tmp_path, provider)
    body = prepare_request(client, before["document_id"], "t08-long-content")
    proposal = client.post(f"/api/resume-documents/{before['document_id']}/ai-suggest", json=body)
    assert proposal.status_code == 200, proposal.text
    accepted = client.post(
        f"/api/resume-documents/{before['document_id']}/ai-proposals/{proposal.json()['id']}/resolve",
        json={"decision": "accept"},
    )
    assert accepted.status_code == 200, accepted.text
    document = accepted.json()["document"]["document"]
    assert document["sections"][0]["items"][0]["content"] == long_text
    assert [section["type"] for section in document["sections"]] == ["skills", "experience", "projects"]
