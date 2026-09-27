import json

import pytest

from workbench.core import Store
from workbench.model_gateway import GatewayError, ModelGateway, OpenAICompatibleAdapter
from workbench.providers import TestProvider
from workbench.runtime_mode import resolve_runtime_mode


CONFIG = {
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-flash",
}


class FakeResponse:
    def __init__(self, raw, status_code=200):
        self._raw = raw
        self.status_code = status_code

    def iter_bytes(self):
        yield self._raw


class FakeStream:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self.response

    def __exit__(self, *args):
        return False


class FakeClient:
    def __init__(self, response, **_kwargs):
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, *args, **kwargs):
        return FakeStream(self.response)


def response_for(content, *, finish_reason="stop", usage=True):
    body = {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
    }
    if usage:
        body["usage"] = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
    return json.dumps(body, ensure_ascii=False).encode()


def adapter_for(monkeypatch, raw):
    monkeypatch.setattr(
        "workbench.model_gateway.httpx.Client",
        lambda **kwargs: FakeClient(FakeResponse(raw), **kwargs),
    )
    return OpenAICompatibleAdapter(CONFIG, "synthetic-key", runtime_mode=resolve_runtime_mode("AI_ENABLED"))


def request(adapter):
    return adapter._request({
        "model": "deepseek-flash",
        "messages": [],
        "response_format": {"type": "json_object"},
        "max_tokens": 4096,
    })


@pytest.mark.parametrize(
    ("content", "expected_code", "first_char", "last_char", "finish_reason"),
    [
        ("", "empty_result", "empty", "empty", "stop"),
        (None, "empty_result", "empty", "empty", "stop"),
        ("   \n", "empty_result", "whitespace", "whitespace", "stop"),
        ('{"changes": [', "truncated_result", "object-start", "text", "length"),
        ('{"changes": [', "truncated_result", "object-start", "text", "stop"),
        ("```json\n{}\n```", "invalid_json", "fence", "fence", "stop"),
        ("这不是 JSON", "invalid_json", "text", "text", "stop"),
    ],
    ids=["empty", "null", "whitespace", "truncated-length", "truncated-heuristic", "fence", "plain-text"],
)
def test_response_parse_failures_are_classified_without_model_text(
    monkeypatch, content, expected_code, first_char, last_char, finish_reason,
):
    adapter = adapter_for(monkeypatch, response_for(content, finish_reason=finish_reason))
    with pytest.raises(GatewayError) as raised:
        request(adapter)
    error = raised.value
    assert error.code == expected_code
    diagnostics = error.response_diagnostics
    assert diagnostics["http_status"] == 200
    assert diagnostics["first_char_type"] == first_char
    assert diagnostics["last_char_type"] == last_char
    assert diagnostics["content_is_empty"] is (isinstance(content, str) and not content.strip())
    assert "content" not in diagnostics
    serialized = json.dumps(diagnostics, ensure_ascii=False)
    assert "这不是 JSON" not in serialized
    assert "```json" not in serialized


@pytest.mark.parametrize(
    "body",
    [{}, {"choices": []}, {"choices": [{}]}, {"choices": [{"message": {}}]}],
    ids=["missing-choices", "empty-choices", "missing-message", "missing-content"],
)
def test_envelope_extraction_failures_are_classified(monkeypatch, body):
    adapter = adapter_for(monkeypatch, json.dumps(body).encode())
    with pytest.raises(GatewayError) as raised:
        request(adapter)
    assert raised.value.code == "invalid_envelope"
    assert "content" not in raised.value.response_diagnostics


def test_outer_non_json_is_invalid_envelope(monkeypatch):
    adapter = adapter_for(monkeypatch, b"upstream response")
    with pytest.raises(GatewayError) as raised:
        request(adapter)
    assert raised.value.code == "invalid_envelope"
    assert raised.value.response_diagnostics["parser_error_type"] == "JSONDecodeError"
    assert "upstream response" not in json.dumps(raised.value.response_diagnostics)


def test_usage_presence_and_status_are_diagnostic_metadata(monkeypatch):
    adapter = adapter_for(monkeypatch, response_for("not-json", usage=False))
    with pytest.raises(GatewayError) as raised:
        request(adapter)
    diagnostics = raised.value.response_diagnostics
    assert diagnostics["usage_present"] is False
    assert diagnostics["finish_reason"] == "stop"
    assert diagnostics["content_chars"] == len("not-json")


def test_valid_json_wrong_schema_reaches_domain_as_dict(monkeypatch):
    adapter = adapter_for(monkeypatch, response_for(json.dumps({"unexpected": True})))
    assert request(adapter) == {"unexpected": True}


def test_wiki_compiler_prompt_enforces_conservative_patch_rules():
    adapter = OpenAICompatibleAdapter(CONFIG, "synthetic-key", runtime_mode=resolve_runtime_mode("AI_ENABLED"))
    packet = {
        "task": "analyze_new_raw_for_wiki_changes",
        "raw": {"id": "raw-fixture", "source_kind": "manual_text", "created_at": "2026-01-01", "content": "虚构原文"},
        "scopes": [{"type": "project", "stable_id": "project-fixture", "minimal_identity": {"name": "虚构项目"}}],
        "current_knowledge": [],
    }
    payload = adapter.build_payload(packet, {"version": 1, "type": "object", "example": {"patches": []}})
    prompt = payload["messages"][0]["content"]
    assert "返回0条" in prompt
    assert "不能创建或猜测Person" in prompt
    assert "Hypothesis" in prompt
    assert "confidence百分比" in prompt


def test_response_diagnostics_are_audited_without_raw_content(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    diagnostics = {
        "http_status": 200,
        "choices_present": True,
        "choices_count": 1,
        "message_present": True,
        "content_present": True,
        "content_type": "str",
        "content_is_null": False,
        "content_is_empty": False,
        "content_chars": 11,
        "finish_reason": "stop",
        "usage_present": True,
        "parser_error_type": "JSONDecodeError",
        "parser_error_position": 4,
        "first_char_type": "text",
        "last_char_type": "text",
    }
    ModelGateway(store)._audit(
        "resume_optimization", None, {"id": "synthetic"}, {"version": 2},
        False, "invalid_json", diagnostics,
    )
    with store.connect(False) as connection:
        record = json.loads(connection.execute("SELECT body FROM records WHERE kind='ai_call'").fetchone()[0])
    assert record["response_diagnostics"] == diagnostics
    assert "raw" not in record
