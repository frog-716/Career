"""Offline parsing and safe failure diagnostics for the HTML search adapter."""
import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient

from workbench import research
from workbench.app import create_app
from workbench.core import Invalid, Store
from workbench.opportunity import create_opportunity
from workbench.providers import TestProvider
from workbench.runtime_mode import resolve_runtime_mode
from workbench.search_provider import SearchProviderError


FIXTURES = Path(__file__).parent / "fixtures" / "research_search"


def _response(*, status=200, body="", content_type="text/html; charset=utf-8", history=()):
    response = httpx.Response(
        status,
        headers={"content-type": content_type},
        text=body,
        request=httpx.Request("GET", "https://html.duckduckgo.com/html/"),
    )
    response.history.extend(history)
    return response


def _fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def _install_response(monkeypatch, response):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(research.httpx, "get", fake_get)
    return calls


@pytest.mark.parametrize(
    ("fixture", "classification"),
    [
        ("changed-structure.html", "selector_mismatch"),
        ("zero-results.html", "zero_results"),
        ("challenge.html", "challenge_detected"),
        ("challenge-result.html", "challenge_detected"),
        ("malformed-url.html", "all_results_filtered"),
    ],
)
def test_search_html_failures_are_classified_without_retaining_body(monkeypatch, fixture, classification):
    body = _fixture(fixture)
    calls = _install_response(monkeypatch, _response(body=body))

    with pytest.raises(Invalid) as caught:
        research.web_search("虚构公司", "虚构岗位", "不发送的虚构 JD", resolve_runtime_mode("AI_ENABLED"))

    error = caught.value
    assert error.code == classification
    assert error.diagnostics["http_status"] == 200
    assert error.diagnostics["content_type"] == "text/html; charset=utf-8"
    assert error.diagnostics["redirect_count"] == 0
    assert "result_nodes" in error.diagnostics
    assert "anchor_nodes" in error.diagnostics
    assert "results_before_filter" in error.diagnostics
    assert "results_after_filter" in error.diagnostics
    assert body not in json.dumps(error.diagnostics, ensure_ascii=False)
    assert len(calls) == 1


def test_search_html_parses_multiple_and_tracking_results_once(monkeypatch):
    calls = _install_response(monkeypatch, _response(body=_fixture("normal.html")))
    results = research.web_search("虚构公司", "虚构岗位", "不发送的虚构 JD", resolve_runtime_mode("AI_ENABLED"))

    assert len(results) == 2
    assert results[0]["url"] == "https://example.test/news?ref=search"
    assert results[0]["title"] == "虚构来源 & 更新"
    assert results[1]["url"] == "https://example.test/about"
    assert len(calls) == 1
    request_url, kwargs = calls[0]
    assert "q=%E8%99%9A%E6%9E%84%E5%85%AC%E5%8F%B8+%E8%99%9A%E6%9E%84%E5%B2%97%E4%BD%8D" in request_url
    assert "%E4%BA%A7%E5%93%81+%E5%95%86%E4%B8%9A%E6%A8%A1%E5%BC%8F+%E6%9C%80%E6%96%B0%E5%8A%A8%E6%80%81" in request_url
    assert "不发送的虚构" not in request_url
    assert kwargs["timeout"] == 15.0 and kwargs["follow_redirects"] is False
    assert "headers" not in kwargs


def test_double_encoded_tracking_url_is_not_decoded_twice(monkeypatch):
    _install_response(monkeypatch, _response(body=_fixture("tracking-url.html")))
    results = research.web_search("虚构公司", "虚构岗位", "", resolve_runtime_mode("AI_ENABLED"))

    assert results[0]["url"] == "https://example.test/story?q=a%2Fb&utm_source=ddg"


@pytest.mark.parametrize(
    ("status", "classification", "redirect_count"),
    [(503, "http_error", 0), (302, "redirect_blocked", 1)],
)
def test_http_failures_are_classified_without_following_redirects(monkeypatch, status, classification, redirect_count):
    calls = _install_response(monkeypatch, _response(status=status, body="not retained"))
    with pytest.raises(Invalid) as caught:
        research.web_search("虚构公司", "虚构岗位", "", resolve_runtime_mode("AI_ENABLED"))

    assert caught.value.code == classification
    assert caught.value.diagnostics["http_status"] == status
    assert caught.value.diagnostics["redirect_count"] == redirect_count
    assert "not retained" not in json.dumps(caught.value.diagnostics)
    assert len(calls) == 1
    assert calls[0][1]["follow_redirects"] is False


def test_timeout_is_distinct_and_does_not_expose_transport_message(monkeypatch):
    def fake_get(url, **kwargs):
        raise httpx.ReadTimeout("synthetic transport detail", request=httpx.Request("GET", url))

    monkeypatch.setattr(research.httpx, "get", fake_get)
    with pytest.raises(Invalid) as caught:
        research.web_search("虚构公司", "虚构岗位", "", resolve_runtime_mode("AI_ENABLED"))

    assert caught.value.code == "timeout"
    assert caught.value.diagnostics["http_status"] is None
    assert "synthetic transport detail" not in str(caught.value)
    assert "synthetic transport detail" not in json.dumps(caught.value.diagnostics)


def test_empty_and_unexpected_response_bodies_fail_closed(monkeypatch):
    for response, classification in (
        (_response(body=""), "parse_error"),
        (_response(body="<html>text only</html>", content_type="application/json"), "parse_error"),
    ):
        _install_response(monkeypatch, response)
        with pytest.raises(Invalid) as caught:
            research.web_search("虚构公司", "虚构岗位", "", resolve_runtime_mode("AI_ENABLED"))
        assert caught.value.code == classification


def test_parser_exception_is_classified_without_exception_message(monkeypatch):
    _install_response(monkeypatch, _response(body="<html>synthetic</html>"))

    def fail_feed(self, value):
        raise RuntimeError("synthetic parser detail must not escape")

    monkeypatch.setattr(research._SearchParser, "feed", fail_feed)
    with pytest.raises(Invalid) as caught:
        research.web_search("虚构公司", "虚构岗位", "", resolve_runtime_mode("AI_ENABLED"))

    assert caught.value.code == "parse_error"
    assert caught.value.diagnostics["parser_error_type"] == "RuntimeError"
    assert "synthetic parser detail" not in str(caught.value)
    assert "synthetic parser detail" not in json.dumps(caught.value.diagnostics)


def test_research_api_exposes_only_safe_search_diagnostics(tmp_path, monkeypatch):
    class FailingSearchProvider:
        def search(self, query):
            raise SearchProviderError("http_error", diagnostics={
                "http_status": 502,
                "content_type": "application/json",
                "response_body": "synthetic response body must not escape",
            })

    store = Store(tmp_path / "data", TestProvider(), search_provider=FailingSearchProvider())
    store.runtime_mode = resolve_runtime_mode("AI_ENABLED")
    store.provider.runtime_mode = store.runtime_mode
    opportunity = create_opportunity(store, {
        "company_name": "诊断用虚构公司", "title": "虚构岗位", "jd": "虚构 JD",
        "idempotency_key": "search-diagnostic-opportunity",
    })
    provider_calls = []
    original_complete = store.provider.complete

    def count_provider_call(payload):
        provider_calls.append(True)
        return original_complete(payload)

    monkeypatch.setattr(store.provider, "complete", count_provider_call)
    client = TestClient(create_app(store), headers={"X-Career-Request": "1", "Content-Type": "application/json"})
    path = f"/api/opportunities/{opportunity['id']}/research/update"

    first = client.post(path, json={"idempotency_key": "search-diagnostic", "search_confirmed": True})
    assert first.status_code == 422
    payload = first.json()
    assert payload["code"] == "http_error"
    assert payload["diagnostics"]["http_status"] == 502
    assert "synthetic response body" not in json.dumps(payload)
    assert provider_calls == []
    with store.connect(False) as connection:
        assert store._records(connection, "ai_preparation") == []
        assert store._records(connection, "research_proposal") == []
