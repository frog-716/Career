"""Synthetic Research proposal contract and validation regression tests."""
import json

import pytest
from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store, digest
from workbench.providers import TestProvider
from workbench.research_store import normalise_proposal_output
from workbench.secret_store import MemorySecretStore


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}
SOURCE_URL = "https://example.test/research-source"
PRIVATE_MARKER = "SYNTHETIC_INVALID_MODEL_CONTENT_MUST_NOT_BE_STORED"


class FakeSearchProvider:
    def __init__(self):
        self.calls = []

    def search(self, query):
        self.calls.append(query)
        return [{
            "title": "虚构公开研究来源",
            "url": SOURCE_URL,
            "snippet": "只用于测试的虚构来源摘录。",
            "source": {"provider": "fake-tavily"},
            "retrieved_at": "2026-09-23T00:00:00+00:00",
        }]


class FixedModelProvider(TestProvider):
    def __init__(self, result):
        super().__init__()
        self.result = result
        self.call_count = 0

    def complete(self, payload):
        self.call_count += 1
        return self.result


class FakeResponse:
    def __init__(self, raw):
        self.raw = raw
        self.status_code = 200
        self.headers = {"content-type": "application/json"}

    def iter_bytes(self):
        yield self.raw


class FakeStream:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self.response

    def __exit__(self, *_args):
        return False


class FakeHTTPClient:
    def __init__(self, response, calls):
        self.response = response
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def stream(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, "payload": kwargs.get("json")})
        return FakeStream(self.response)


def setup_client(tmp_path, monkeypatch, provider=None):
    monkeypatch.setenv("CAREER_AI_MODE", "AI_ENABLED")
    search = FakeSearchProvider()
    store = Store(
        tmp_path / "data",
        provider or TestProvider(),
        MemorySecretStore(),
        search_provider=search,
    )
    client = TestClient(create_app(store), headers=HEADERS)
    opportunity = client.post("/api/opportunities", json={
        "company_name": "虚构星河科技",
        "title": "虚构 AI 产品经理",
        "jd": "仅用于测试 Research proposal 输出合同。",
        "idempotency_key": "synthetic-opportunity",
    }).json()
    return store, client, search, opportunity


def execute_research(client, opportunity_id, key):
    path = f"/api/opportunities/{opportunity_id}/research/update"
    first = client.post(path, json={"idempotency_key": key})
    assert first.status_code == 409
    assert first.json()["status"] == "search_confirmation_required"

    after_search = client.post(path, json={
        "idempotency_key": key,
        "search_confirmed": True,
    })
    assert after_search.status_code == 409, after_search.text
    prepared = after_search.json()
    assert prepared["status"] == "context_confirmation_required"

    return client.post(path, json={
        "idempotency_key": key,
        "search_confirmed": True,
        "prepared_id": prepared["prepared_id"],
        "payload_hash": prepared["payload_hash"],
        "confirm_outbound": True,
    })


def valid_item(content, *, category="company", source_refs=None):
    return {
        "category": category,
        "classification": "unknown",
        "content": content,
        "source_refs": source_refs if source_refs is not None else [{
            "url": SOURCE_URL,
            "id": "web:" + digest(SOURCE_URL),
        }],
    }


def test_full_fake_openai_response_parses_and_creates_sourced_research_proposal(tmp_path, monkeypatch):
    store, client, search, opportunity = setup_client(tmp_path, monkeypatch)
    fake_calls = []
    result = {
        "company_items": [valid_item(
            "虚构公司提供虚构产品。", category="company_business", source_refs=[{"url": SOURCE_URL, "id": None}],
        )],
        "opportunity_items": [valid_item("虚构岗位负责虚构产品需求。", category="role")],
    }
    envelope = {
        "choices": [{
            "message": {"content": json.dumps(result, ensure_ascii=False)},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }
    raw = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    monkeypatch.setattr(
        "workbench.model_gateway.httpx.Client",
        lambda **_kwargs: FakeHTTPClient(FakeResponse(raw), fake_calls),
    )

    config = client.post("/api/ai/models", json={
        "display_name": "合成 DeepSeek",
        "provider": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-flash",
        "api_key": "synthetic-only-not-a-real-key",
        "enabled": True,
    })
    assert config.status_code == 200, config.text
    assert config.json()["secret_status"] == "ready"

    response = execute_research(client, opportunity["id"], "synthetic-valid-proposal")

    assert response.status_code == 200, response.text
    assert len(search.calls) == 1
    assert len(fake_calls) == 1
    request = fake_calls[0]["payload"]
    assert request["model"] == "deepseek-flash"
    assert request["response_format"] == {"type": "json_object"}
    system_prompt = request["messages"][0]["content"]
    assert '"company_items"' in system_prompt
    assert '"opportunity_items"' in system_prompt
    assert '"maxLength":10000' in system_prompt
    assert '"source_refs"' in system_prompt
    assert "purpose=web_source" in system_prompt
    assert "selected_content.url" in system_prompt
    assert "classification" in system_prompt
    assert "company_business" in system_prompt
    assert "禁止 Markdown code fence" in system_prompt
    assert "虚构星河科技经营虚构的协作产品。" in system_prompt

    proposal = response.json()
    assert [item["category"] for item in proposal["company_items"]] == ["company_business"]
    assert [item["category"] for item in proposal["opportunity_items"]] == ["role"]
    for item, expected_scope, expected_owner in (
        (proposal["company_items"][0], "company", opportunity["company_id"]),
        (proposal["opportunity_items"][0], "opportunity", opportunity["id"]),
    ):
        assert item["evidence_status"] == "lead"
        assert item["verification"]["user_confirmed"] is False
        assert item["source_refs"][0]["url"] == SOURCE_URL
        assert item["source_refs"][0]["id"] == "web:" + digest(SOURCE_URL)
        assert item["source_refs"][0]["scope"] == expected_scope
        assert item["source_refs"][0]["owner_id"] == expected_owner
        assert item["source_refs"][0]["kind"] == "web_source"

    overview = client.get(f"/api/opportunities/{opportunity['id']}/research-overview").json()
    assert overview["items"] == []


@pytest.mark.parametrize(
    ("group", "index", "item", "expected_code", "expected_path", "marker"),
    [
        ("company_items", 0, {"category": "company"}, "content_missing", "company_items[0].content", ""),
        ("opportunity_items", 0, {"content": "  "}, "content_empty", "opportunity_items[0].content", ""),
        ("company_items", 0, {"content": {"probe": PRIVATE_MARKER}}, "content_wrong_type", "company_items[0].content", PRIVATE_MARKER),
        ("opportunity_items", 1, {"content": "x" * 10001}, "content_too_long", "opportunity_items[1].content", ""),
    ],
    ids=["missing", "empty", "wrong-type", "too-long"],
)
def test_invalid_research_content_is_classified_without_persisting_content(
    tmp_path, monkeypatch, group, index, item, expected_code, expected_path, marker,
):
    store, client, search, opportunity = setup_client(tmp_path, monkeypatch)
    values = [valid_item("合成有效条目。", source_refs=[]) for _ in range(index + 1)]
    values[index] = {"category": "company", "classification": "unknown", "source_refs": [], **item}
    result = {
        "company_items": [],
        "opportunity_items": [],
    }
    result[group] = values
    model = FixedModelProvider(result)
    store.provider = model

    response = execute_research(client, opportunity["id"], f"synthetic-{expected_code}")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == expected_code
    assert body["detail"] == expected_path
    assert model.call_count == 1
    assert len(search.calls) == 1
    if marker:
        assert marker not in json.dumps(body, ensure_ascii=False)
    with store.connect(False) as connection:
        operation = connection.execute(
            "SELECT error_code,error_message FROM ai_operations WHERE task_type='research_update'"
        ).fetchone()
        records = connection.execute("SELECT body FROM records").fetchall()
    assert tuple(operation) == (expected_code, expected_path)
    if marker:
        assert all(marker not in row[0] for row in records)


@pytest.mark.parametrize(
    ("source_ref", "expected_code", "expected_path"),
    [
        ({"url": "https://example.test/not-in-this-search"}, "source_not_in_current_search", "company_items[0].source_refs[0].url"),
        ({"url": SOURCE_URL, "id": "web:wrong"}, "source_id_mismatch", "company_items[0].source_refs[0].id"),
        ({"url": SOURCE_URL, "extra": "not-in-contract"}, "source_ref_invalid", "company_items[0].source_refs[0]"),
    ],
    ids=["unknown-url", "mismatched-id", "unknown-field"],
)
def test_research_provenance_validation_is_fail_closed(tmp_path, monkeypatch, source_ref, expected_code, expected_path):
    result = {
        "company_items": [{
            "category": "company", "classification": "unknown",
            "content": "虚构公司研究内容。", "source_refs": [source_ref],
        }],
        "opportunity_items": [],
    }
    model = FixedModelProvider(result)
    store, client, search, opportunity = setup_client(tmp_path, monkeypatch, model)

    response = execute_research(client, opportunity["id"], "synthetic-invalid-source")

    assert response.status_code == 422
    assert response.json()["code"] == expected_code
    assert response.json()["detail"] == expected_path
    assert model.call_count == 1
    assert len(search.calls) == 1


def test_schema_example_passes_the_same_local_proposal_validator():
    from workbench.research import _research_output_schema

    schema = _research_output_schema()
    example = schema["example"]
    normalized = normalise_proposal_output(example)

    assert set(normalized) == {"company_items", "opportunity_items"}
    assert normalized["company_items"][0]["content"]
    assert normalized["opportunity_items"][0]["content"]
    assert normalized["company_items"][0]["source_refs"] == []
    assert normalized["opportunity_items"][0]["source_refs"] == []
