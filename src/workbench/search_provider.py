"""Stable Research search boundary and the basic Tavily Search adapter."""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_TRACKING_KEYS = {"gclid", "fbclid", "mc_cid", "mc_eid", "ref", "source"}


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: dict[str, str]
    retrieved_at: str

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": dict(self.source),
            "provider": self.source["provider"],
            "retrieved_at": self.retrieved_at,
        }


class SearchProvider(Protocol):
    def search(self, query: str) -> list[SearchResult]: ...


class SearchProviderError(Exception):
    """Safe, body-free provider failure with a stable classification."""

    def __init__(self, code: str, *, diagnostics: dict | None = None, outcome_unknown=False):
        self.code = code
        self.diagnostics = {
            key: value
            for key, value in (diagnostics or {}).items()
            if key in {"http_status", "content_type", "results_received", "results_accepted"}
        }
        self.outcome_unknown = bool(outcome_unknown)
        super().__init__(f"Research 搜索失败（{code}）")


def normalize_result_url(value: object) -> str | None:
    """Normalize safe public HTTP(S) URLs; reject local, credentialed and malformed URLs."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        if scheme not in {"http", "https"} or not parsed.netloc or not hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        host = hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return None
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            return None
        port = parsed.port
    except ValueError:
        return None
    if not host or any(ord(character) < 33 for character in host):
        return None
    if ":" in host:
        host = f"[{host}]"
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if port is None or default_port else f"{host}:{port}"
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_KEYS
    ]
    return urlunsplit((scheme, netloc, parsed.path or "/", urlencode(query, doseq=True), ""))


class TavilySearchProvider:
    """One bounded POST to Tavily's basic Search endpoint; never uses answer output."""

    def __init__(self, api_key: str, *, transport=None, timeout_seconds: float = 15.0):
        if not isinstance(api_key, str) or not api_key:
            raise SearchProviderError("auth_error")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._api_key = api_key
        self._transport = transport
        self._timeout_seconds = float(timeout_seconds)

    def search(self, query: str) -> list[SearchResult]:
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise SearchProviderError("invalid_response")
        payload = {
            "query": query.strip(),
            "search_depth": "basic",
            "topic": "general",
            "max_results": 8,
            "include_answer": False,
            "include_raw_content": False,
        }
        timeout = httpx.Timeout(
            self._timeout_seconds,
            connect=min(5.0, self._timeout_seconds),
            read=self._timeout_seconds,
            write=min(5.0, self._timeout_seconds),
            pool=min(5.0, self._timeout_seconds),
        )
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream(
                    "POST",
                    TAVILY_SEARCH_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                ) as response:
                    status = response.status_code
                    content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                    diagnostics = {"http_status": status, "content_type": content_type or None}
                    if status in {401, 403}:
                        raise SearchProviderError("auth_error", diagnostics=diagnostics)
                    if status == 429:
                        raise SearchProviderError("rate_limited", diagnostics=diagnostics)
                    if status < 200 or status >= 300:
                        raise SearchProviderError("http_error", diagnostics=diagnostics)
                    if content_type != "application/json":
                        raise SearchProviderError("invalid_response", diagnostics=diagnostics)
                    chunks = []
                    response_size = 0
                    for chunk in response.iter_bytes():
                        response_size += len(chunk)
                        if response_size > MAX_RESPONSE_BYTES:
                            raise SearchProviderError("invalid_response", diagnostics=diagnostics)
                        chunks.append(chunk)
                    response_body = b"".join(chunks)
        except httpx.TimeoutException:
            raise SearchProviderError("timeout", outcome_unknown=True) from None
        except httpx.HTTPError:
            raise SearchProviderError("provider_error", outcome_unknown=True) from None
        try:
            body = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SearchProviderError("invalid_response", diagnostics=diagnostics) from None
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise SearchProviderError("invalid_response", diagnostics=diagnostics)
        raw_results = body["results"]
        if not raw_results:
            raise SearchProviderError(
                "zero_results",
                diagnostics={**diagnostics, "results_received": 0, "results_accepted": 0},
            )

        results = []
        seen = set()
        for raw in raw_results:
            if not isinstance(raw, dict):
                raise SearchProviderError("invalid_response", diagnostics=diagnostics)
            title = raw.get("title")
            snippet = raw.get("content")
            url = normalize_result_url(raw.get("url"))
            if not isinstance(title, str) or not title.strip() or not isinstance(snippet, str):
                raise SearchProviderError("invalid_response", diagnostics=diagnostics)
            if not url:
                continue
            title = title.strip()[:500]
            snippet = snippet.strip()[:4000]
            if not snippet:
                raise SearchProviderError("invalid_response", diagnostics=diagnostics)
            if url in seen:
                continue
            seen.add(url)
            results.append(SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source={"provider": "tavily"},
                retrieved_at=datetime.now(timezone.utc).isoformat(),
            ))
            if len(results) >= 8:
                break
        if not results:
            raise SearchProviderError(
                "invalid_response",
                diagnostics={
                    **diagnostics,
                    "results_received": len(raw_results),
                    "results_accepted": 0,
                },
            )
        return results
