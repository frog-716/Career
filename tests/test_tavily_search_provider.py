"""Contract tests for the Tavily adapter; MockTransport prevents all networking."""

import json

import httpx
import pytest

from workbench.search_provider import SearchProviderError, TavilySearchProvider


def test_tavily_search_sends_only_query_and_fixed_search_controls():
    captured = []

    def respond(request):
        captured.append(request)
        return httpx.Response(200, json={
            "results": [{
                "title": "虚构公司公开页面",
                "url": "https://Example.test/jobs?utm_source=search#section",
                "content": "公开岗位页面摘录",
                "score": 0.91,
            }],
            "answer": "This must not be used as a fact.",
        })

    provider = TavilySearchProvider(
        "fake-tv-key-7",
        transport=httpx.MockTransport(respond),
    )
    results = provider.search("虚构公司 虚构岗位 产品 商业模式 最新动态")

    assert len(captured) == 1
    request = captured[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.tavily.com/search"
    assert request.headers["Authorization"] == "Bearer fake-tv-key-7"
    assert json.loads(request.content) == {
        "query": "虚构公司 虚构岗位 产品 商业模式 最新动态",
        "search_depth": "basic",
        "topic": "general",
        "max_results": 8,
        "include_answer": False,
        "include_raw_content": False,
    }
    assert results[0].title == "虚构公司公开页面"
    assert results[0].url == "https://example.test/jobs"
    assert results[0].snippet == "公开岗位页面摘录"
    assert results[0].source == {"provider": "tavily"}


@pytest.mark.parametrize(
    ("status", "classification"),
    [(401, "auth_error"), (403, "auth_error"), (429, "rate_limited"), (503, "http_error")],
)
def test_tavily_http_errors_are_classified_without_response_body(status, classification):
    provider = TavilySearchProvider(
        "fake-tv-key-7",
        transport=httpx.MockTransport(lambda request: httpx.Response(status, text="do not expose")),
    )

    with pytest.raises(SearchProviderError) as caught:
        provider.search("虚构公司 虚构岗位")

    assert caught.value.code == classification
    assert "do not expose" not in str(caught.value)


@pytest.mark.parametrize(
    ("response", "classification"),
    [
        (httpx.Response(200, text="not-json", headers={"content-type": "application/json"}), "invalid_response"),
        (httpx.Response(200, json={"answer": "ignored"}), "invalid_response"),
        (httpx.Response(200, json={"results": []}), "zero_results"),
        (httpx.Response(302, headers={"location": "https://elsewhere.example"}), "http_error"),
    ],
)
def test_tavily_response_shapes_and_redirects_fail_closed(response, classification):
    provider = TavilySearchProvider(
        "fake-tv-key-7",
        transport=httpx.MockTransport(lambda request: response),
    )

    with pytest.raises(SearchProviderError) as caught:
        provider.search("虚构公司 虚构岗位")

    assert caught.value.code == classification


def test_tavily_normalizes_duplicates_and_filters_private_or_unsafe_urls():
    provider = TavilySearchProvider(
        "fake-tv-key-7",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
            "results": [
                {"title": "公开来源", "url": "https://EXAMPLE.test/a?utm_campaign=x#top", "content": "公开摘录"},
                {"title": "重复来源", "url": "https://example.test/a", "content": "重复摘录"},
                {"title": "本机地址", "url": "http://127.0.0.1/private", "content": "不应返回"},
                {"title": "脚本地址", "url": "javascript:alert(1)", "content": "不应返回"},
            ],
        })),
    )

    results = provider.search("虚构公司 虚构岗位")

    assert len(results) == 1
    assert results[0].url == "https://example.test/a"
    assert results[0].snippet == "公开摘录"


def test_tavily_timeout_is_bounded_and_marks_outcome_unknown():
    def timeout(request):
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    provider = TavilySearchProvider(
        "fake-tv-key-7",
        transport=httpx.MockTransport(timeout),
        timeout_seconds=0.1,
    )

    with pytest.raises(SearchProviderError) as caught:
        provider.search("虚构公司 虚构岗位")

    assert caught.value.code == "timeout"
    assert caught.value.outcome_unknown is True


@pytest.mark.parametrize(
    "result",
    [
        {"url": "https://example.test/missing-title", "content": "摘要"},
        {"title": "缺少 URL", "content": "摘要"},
        {"title": "缺少摘要", "url": "https://example.test/missing-content"},
    ],
)
def test_tavily_rejects_results_missing_required_fields(result):
    provider = TavilySearchProvider(
        "fake-tv-key-7",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"results": [result]})),
    )

    with pytest.raises(SearchProviderError) as caught:
        provider.search("虚构公司 虚构岗位")

    assert caught.value.code == "invalid_response"


def test_tavily_transport_error_is_provider_error_and_uncertain():
    def connection_error(request):
        raise httpx.ConnectError("synthetic network trap", request=request)

    provider = TavilySearchProvider(
        "fake-tv-key-7",
        transport=httpx.MockTransport(connection_error),
    )

    with pytest.raises(SearchProviderError) as caught:
        provider.search("虚构公司 虚构岗位")

    assert caught.value.code == "provider_error"
    assert caught.value.outcome_unknown is True
