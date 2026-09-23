"""Research workspace: sourced company/opportunity intelligence and proposals."""
import json
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, urljoin, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .core import Conflict, Invalid, Missing, digest, now, required, uid
from . import opportunity as op
from . import ai_operations as ao
from . import context_manifest as cm
from . import research_store as rs
from .model_gateway import ModelGateway
from . import outbound_policy as outbound
from .runtime_mode import require_ai_enabled
from .secret_store import SecretStoreError
from .search_provider import SearchProviderError, SearchResult, TavilySearchProvider
from . import research_search_config


CATEGORIES = rs.CATEGORIES
CLASSIFICATIONS = rs.CLASSIFICATIONS

# Search results and the compiled request are intentionally process-local and
# short-lived.  The durable preparation/audit records contain only references
# and hashes; after a restart the user must explicitly re-preview the search
# and model payload.
_VOLATILE_RESEARCH_PREPARATIONS = {}


class SearchFailure(Invalid):
    """A fail-closed search error carrying only non-content diagnostics."""

    def __init__(self, classification, diagnostics):
        self.code = classification
        allowed = (
            "http_status", "content_type", "redirect_count", "result_nodes", "anchor_nodes",
            "results_before_filter", "results_after_filter", "filtered_count",
            "parser_error_type", "results_received", "results_accepted",
        )
        self.diagnostics = {key: diagnostics.get(key) for key in allowed if key in diagnostics}
        super().__init__(f"Research 搜索失败（{classification}）")


class _SearchParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.result_nodes = 0
        self.anchor_nodes = 0
        self.no_results = False
        self.challenge = False
        self.href = None
        self.text = []
        self.page_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        class_value = attrs.get("class") or ""
        id_value = attrs.get("id") or ""
        classes = set(class_value.split())
        identity = f"{id_value} {class_value}".lower()
        if "no-results" in classes or id_value.lower() in {"no-results", "no_results"}:
            self.no_results = True
        if any(marker in identity for marker in ("challenge", "captcha", "anomaly-modal")):
            self.challenge = True
        if tag == "a":
            self.anchor_nodes += 1
        if tag == "a" and "result__a" in classes:
            self.result_nodes += 1
            self.href = attrs.get("href")
            self.text = []

    def handle_data(self, data):
        self.page_text.append(data)
        if self.href is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.results.append({
                "url": self.href,
                "title": " ".join("".join(self.text).split()),
            })
            self.href = None
            self.text = []


_PAGE_CHALLENGE_MARKERS = (
    "verify you are human", "unusual traffic", "robot check", "security challenge",
    "complete the captcha", "complete captcha", "验证后继续", "机器人验证",
)
_RESULT_CHALLENGE_MARKERS = _PAGE_CHALLENGE_MARKERS + ("captcha",)


def _normalise_search_url(value):
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = urljoin("https://html.duckduckgo.com/", value.strip())
    try:
        parsed = urlsplit(candidate)
        host = (parsed.hostname or "").lower()
        if host == "duckduckgo.com" or host.endswith(".duckduckgo.com"):
            if parsed.path == "/l/":
                targets = parse_qs(parsed.query).get("uddg", [])
                if not targets:
                    return None
                candidate = targets[0]  # parse_qs already decodes exactly once.
                parsed = urlsplit(candidate)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        port = parsed.port
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))


def _search_diagnostics(response=None, *, result_nodes=0, anchor_nodes=0, before=0, after=0, **extra):
    status = getattr(response, "status_code", None)
    headers = getattr(response, "headers", {}) or {}
    content_type = headers.get("content-type") or headers.get("Content-Type")
    if content_type is not None:
        content_type = str(content_type)[:120]
    history = getattr(response, "history", ()) or ()
    redirects = len(history)
    if status is not None and 300 <= status < 400 and not redirects:
        redirects = 1
    return {
        "http_status": status,
        "content_type": content_type,
        "redirect_count": redirects,
        "result_nodes": result_nodes,
        "anchor_nodes": anchor_nodes,
        "results_before_filter": before,
        "results_after_filter": after,
        "filtered_count": max(0, before - after),
        **extra,
    }


def _search_failure(classification, response=None, **metadata):
    diagnostics = _search_diagnostics(response, **metadata)
    raise SearchFailure(classification, diagnostics) from None


def web_search(company, title, jd, runtime_mode=None):
    require_ai_enabled(runtime_mode)
    query = " ".join(x for x in (company, title, "产品 商业模式 最新动态") if x)
    try:
        response = httpx.get("https://html.duckduckgo.com/html/?q=" + quote_plus(query), timeout=15.0, follow_redirects=False)
    except httpx.TimeoutException:
        _search_failure("timeout")
    except httpx.HTTPError:
        _search_failure("http_error")

    if 300 <= response.status_code < 400:
        _search_failure("redirect_blocked", response)
    if response.status_code != 200:
        _search_failure("http_error", response)

    content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if content_type != "text/html":
        _search_failure("parse_error", response)
    try:
        body = response.text
        if not body or not body.strip():
            _search_failure("parse_error", response)
        parser = _SearchParser()
        parser.feed(body)
        parser.close()
    except SearchFailure:
        raise
    except Exception as exc:
        _search_failure("parse_error", response, parser_error_type=type(exc).__name__)

    diagnostic_base = {
        "result_nodes": parser.result_nodes,
        "anchor_nodes": parser.anchor_nodes,
        "before": parser.result_nodes,
    }
    page_text = " ".join(parser.page_text).casefold()
    if parser.challenge or any(marker in page_text for marker in _PAGE_CHALLENGE_MARKERS):
        _search_failure("challenge_detected", response, **diagnostic_base)
    if parser.no_results or any(marker in page_text for marker in ("no results found", "no results for", "没有搜索结果", "未找到结果")):
        _search_failure("zero_results", response, **diagnostic_base)
    if parser.result_nodes == 0:
        _search_failure("selector_mismatch", response, **diagnostic_base)

    candidates = []
    for item in parser.results:
        url = _normalise_search_url(item.get("url"))
        title_text = item.get("title", "").strip()
        if url and title_text:
            candidates.append({"url": url, "title": title_text})
    if not candidates:
        _search_failure("all_results_filtered", response, **diagnostic_base)
    if all(_search_result_is_challenge(item) for item in candidates):
        _search_failure("challenge_detected", response, **diagnostic_base)

    seen, results = set(), []
    for item in candidates:
        if item["url"] not in seen and not _search_result_is_challenge(item):
            seen.add(item["url"])
            results.append({**item, "retrieved_at": now()})
        if len(results) >= 8:
            break
    if not results:
        _search_failure("all_results_filtered", response, **diagnostic_base)
    return results


def _id(kind, owner): return rs.research_id(kind, owner)


def _get(store, c, kind, owner):
    return rs.get(store, c, kind, owner)


def _item(value, source_refs=None):
    return rs.normalise_item(value, source_refs)


def _search_result_is_challenge(value):
    text = " ".join(str(value.get(key, "")) for key in ("title", "url")).lower()
    return any(marker.lower() in text for marker in _RESULT_CHALLENGE_MARKERS)


def _search_results(results):
    if not isinstance(results, list):
        return []
    usable = []
    for raw in results:
        if not isinstance(raw, dict) or not raw.get("url") or not raw.get("title"):
            continue
        if _search_result_is_challenge(raw):
            continue
        value = dict(raw)
        retrieved_at = value.get("retrieved_at")
        try:
            parsed = datetime.fromisoformat(str(retrieved_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            value["date_status"] = "stale" if parsed < datetime.now(timezone.utc) - timedelta(days=90) else "current"
        except (TypeError, ValueError):
            value["date_status"] = "unknown"
        value["evidence_status"] = "lead"
        usable.append(value)
    return usable


def _manual_source_refs(refs, owner_id, scope):
    if not isinstance(refs, list) or len(refs) > 10:
        raise Invalid("Research 来源过多")
    result = []
    for raw in refs:
        if not isinstance(raw, dict):
            raise Invalid("Research 来源必须是对象")
        value = dict(raw)
        if value.get("owner_id") is not None and value.get("owner_id") != owner_id:
            raise Conflict("source_owner_conflict: Research 来源不属于当前目标")
        if value.get("scope") is not None and value.get("scope") != scope:
            raise Conflict("source_scope_conflict: Research 来源 scope 不属于当前目标")
        url = value.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise Invalid("Research 来源 URL 不合法")
        source_id = value.get("id")
        if source_id and (source_id.startswith("web:") or value.get("kind") == "web_source"):
            expected = "web:" + digest(url)
            if source_id != expected:
                raise Invalid("Research 来源 ID 与 URL 不匹配")
        value.update(
            id=source_id or "user-source:" + digest([owner_id, url, value.get("title", "")]),
            owner_id=owner_id,
            scope=scope,
            kind=value.get("kind") or "user_reference",
        )
        result.append(value)
    return result


def _validate_evidence(evidence, owner_id, scope):
    for item in evidence:
        if item.get("owner_id") != owner_id:
            raise Conflict("evidence_owner_conflict: Research 证据不属于当前目标")
        if item.get("scope") != scope:
            raise Conflict("evidence_scope_conflict: Research 证据 scope 不属于当前目标")


def _validate_relations(item, current_items, item_id=None):
    ids = {value.get("id") for value in current_items}
    for field in ("supersedes", "replaces"):
        for relation in item.get(field, []):
            if relation not in ids or relation == item_id:
                raise Missing("Research relation 目标不存在")


def view(store, c, opportunity_id):
    opportunity = op.resolve(store, c, opportunity_id)
    company = _get(store, c, "company_research", opportunity["company_id"])
    research = _get(store, c, "opportunity_research", opportunity["id"])
    return {
        "company": company, "opportunity": research, "items": research["items"],
        "revision": research["revision"],
        "pending_proposals": [proposal for proposal in _proposal_views(store, c, opportunity["id"])
                              if proposal.get("status") == "pending"],
    }


def _pack(store, c, opportunity, company, research, sources):
    return {
        "schemaVersion": 1, "task_type": "research_update", "policy_version": "research-v1",
        "required_context": ["opportunity", "web_sources"],
        "optional_context": ["company_research", "opportunity_research"],
        "forbidden_context": ["simulation", "feedback", "other_opportunities", "full_career_archive"],
        "target": {"opportunity_id": opportunity["id"], "company_id": opportunity["company_id"]},
        "sources": sources, "current_company_research": company["items"],
        "current_opportunity_research": research["items"], "unknowns": [],
        "budget_used": {"source_count": len(sources), "content_chars": sum(len(json.dumps(x, ensure_ascii=False)) for x in sources)},
    }


def _research_prepare(store, opportunity_id, body):
    with store.connect(False) as c:
        opportunity = op.resolve(store, c, opportunity_id)
        company, company_exists = rs.lookup(store, c, "company_research", opportunity["company_id"])
        research, research_exists = rs.lookup(store, c, "opportunity_research", opportunity["id"])
    return {
        "opportunity": opportunity, "company": company, "research": research,
        "company_exists": company_exists, "research_exists": research_exists,
        "body": body, "request_fingerprint": digest(_research_client_intent(opportunity_id, body)),
    }


def _research_client_intent(opportunity_id, body):
    return {
        "opportunity_id": op.canonical_id(opportunity_id),
        "idempotency_key": body.get("idempotency_key"),
        "model_config_id": body.get("model_config_id"),
    }


_RESEARCH_SEARCH_TERMS = "产品 商业模式 最新动态"


def _research_search_query(opportunity):
    # Only company, role title and fixed public research terms are searchable.
    # The JD and all candidate/interview/career materials stay out of this path.
    return " ".join(
        value for value in (opportunity.get("company"), opportunity.get("title"), _RESEARCH_SEARCH_TERMS)
        if isinstance(value, str) and value.strip()
    )


def _normalise_provider_results(results):
    if not isinstance(results, list):
        raise SearchProviderError("invalid_response")
    normalized = []
    for result in results:
        if isinstance(result, SearchResult):
            normalized.append(result.as_dict())
        elif isinstance(result, dict):
            # This is the explicit injectable-provider seam used by synthetic tests.
            title, url = result.get("title"), result.get("url")
            snippet = result.get("snippet", "")
            if not isinstance(title, str) or not title.strip() or not isinstance(url, str) or not isinstance(snippet, str):
                raise SearchProviderError("invalid_response")
            source = result.get("source") or {"provider": result.get("provider", "test")}
            if not isinstance(source, dict):
                raise SearchProviderError("invalid_response")
            normalized.append({
                "title": title.strip(), "url": url, "snippet": snippet,
                "source": dict(source),
                "provider": result.get("provider", source.get("provider", "test")),
                "retrieved_at": result.get("retrieved_at") or now(),
            })
        else:
            raise SearchProviderError("invalid_response")
    return normalized


def _search_manifest(opportunity):
    # Store only a digest of allowed query inputs, never the full JD in the
    # search operation audit manifest.
    public_identity = {
        "company": opportunity.get("company"),
        "title": opportunity.get("title"),
    }
    return cm.manifest(
        "research_search",
        {"kind": "opportunity", "id": opportunity["id"]},
        opportunity["revision"],
        [cm.dependency(
            "opportunity", opportunity["id"], opportunity["revision"],
            public_identity, "public_search_query",
        )],
    )


def _dispatch_research_search(store, opportunity, key):
    query = _research_search_query(opportunity)
    manifest = _search_manifest(opportunity)

    def prepare():
        return {"query": query, "manifest": manifest}

    def dispatch(prepared, binder):
        injected_provider = store.search_provider
        if injected_provider is None:
            ref = research_search_config.configured_ref_for_search(store)
            if not ref:
                store.set_runtime_search_secret_status("not_configured")
                error = ao.PreDispatchFailure("Tavily Search 尚未配置 Secret")
                error.code = "auth_error"
                raise error
            try:
                api_key = store.secret_store_for_maintenance().get(ref)
            except SecretStoreError as exc:
                store.set_runtime_search_secret_status(exc.code)
                error = ao.PreDispatchFailure("Tavily Search Secret 不可用")
                error.code = "auth_error"
                raise error from None
            except Exception:
                store.set_runtime_search_secret_status("error")
                error = ao.PreDispatchFailure("Tavily Search Secret 不可用")
                error.code = "auth_error"
                raise error from None
            if not isinstance(api_key, str) or not api_key:
                store.set_runtime_search_secret_status("error")
                error = ao.PreDispatchFailure("Tavily Search Secret 不可用")
                error.code = "auth_error"
                raise error
            store.set_runtime_search_secret_status("ready")
            provider = TavilySearchProvider(api_key)
        else:
            provider = injected_provider

        binder(digest({
            "destination": "https://api.tavily.com/search",
            "query": prepared["query"],
            "search_depth": "basic",
            "topic": "general",
            "max_results": 8,
            "include_answer": False,
            "include_raw_content": False,
        }), prepared["manifest"])
        try:
            results = _normalise_provider_results(provider.search(prepared["query"]))
            if not results:
                raise SearchProviderError(
                    "zero_results",
                    diagnostics={"results_received": 0, "results_accepted": 0},
                )
        except SearchProviderError as exc:
            if exc.outcome_unknown:
                raise
            raise SearchFailure(exc.code, exc.diagnostics) from None
        finally:
            if injected_provider is None:
                api_key = ""
                provider = None
        return results, {"provider": "tavily", "result_count": len(results)}

    return ao.execute(
        store, task_type="research_search", target_kind="opportunity",
        target_id=opportunity["id"], idempotency_key=key,
        client_intent={
            "opportunity_id": opportunity["id"],
            "query": query,
            "idempotency_key": key,
        },
        prepare=prepare,
        dispatch=dispatch,
        persist=lambda _prepared, results, _diagnostics: results,
    )


def _research_output_schema(sources=None):
    web_sources = [
        source for source in (sources or [])
        if isinstance(source, dict) and source.get("purpose") == "web_source"
    ]
    if not web_sources:
        return rs.research_proposal_output_schema()
    source = web_sources[0]
    selected = source.get("selected_content") or {}
    source_id, source_url = source.get("id"), selected.get("url")
    if not isinstance(source_id, str) or not isinstance(source_url, str) or not source_url:
        raise ao.PreDispatchFailure("Research Search 来源标识无效，未调用模型")
    return rs.research_proposal_output_schema(
        require_source_refs=True,
        example_source_ref={"id": source_id, "url": source_url},
    )


def _research_compile(store, prepared, results):
    opportunity, company, research = prepared["opportunity"], prepared["company"], prepared["research"]
    results = _search_results(results)
    if not results:
        raise ao.PreDispatchFailure("Web Research 没有来源，未调用模型")
    sources = [{"id": "web:" + digest(x["url"]), "revision": 0, "purpose": "web_source", "selected_content": x} for x in results]
    sources.insert(0, {"id": opportunity["id"], "revision": opportunity["revision"], "purpose": "opportunity", "selected_content": {
        "company": opportunity["company"], "title": opportunity["title"], "jd": opportunity.get("jd", "")
    }})
    pack = _pack(store, None, opportunity, company, research, sources)
    dependencies = [cm.dependency(
        "opportunity", opportunity["id"], opportunity["revision"],
        cm.selected_opportunity(opportunity), "current_jd"
    )]
    for kind, document, exists, purpose, owner in (
        ("company_research", company, prepared["company_exists"], "current_company_research", opportunity["company_id"]),
        ("opportunity_research", research, prepared["research_exists"], "current_opportunity_research", opportunity["id"]),
    ):
        dependencies.append(cm.dependency(
            kind, document["id"], document["revision"],
            rs.content_hash(document) if exists else None, purpose,
            content_hash=rs.content_hash(document) if exists else None,
            expected_absent=not exists, owner_id=owner,
        ))
    for source in sources:
        if source["purpose"] == "web_source":
            dependencies.append(cm.dependency(
                "web_source", source["id"], source["revision"], source["selected_content"], "web_source"
            ))
    manifest = cm.manifest(
        "research_update",
        {"kind": "opportunity", "id": opportunity["id"], "company_id": opportunity["company_id"]},
        opportunity["revision"], dependencies,
    )
    prepared.update(sources=sources, pack=pack, results=results, manifest=manifest)
    return prepared


def _research_create_preparation(store, opportunity_id, body):
    prepared = _research_prepare(store, opportunity_id, body)
    opportunity = prepared["opportunity"]
    client_intent = _research_client_intent(opportunity_id, body)
    require_ai_enabled(store.runtime_mode)
    try:
        search = _dispatch_research_search(store, opportunity, body["idempotency_key"])
    except SearchFailure as exc:
        operation = ao.find(store, "research_search", "opportunity", opportunity["id"], body["idempotency_key"])
        return JSONResponse({
            **(ao._public(operation) if operation else {}),
            "status": "failed", "code": exc.code,
            "diagnostics": exc.diagnostics,
            "message": "搜索失败；Career 不会自动重试或切换搜索服务。",
        }, status_code=422)
    except SearchProviderError as exc:
        operation = ao.find(store, "research_search", "opportunity", opportunity["id"], body["idempotency_key"])
        return JSONResponse({
            **(ao._public(operation) if operation else {}),
            "status": "outcome_unknown", "state": "outcome_unknown", "code": exc.code,
            "diagnostics": exc.diagnostics,
            "message": "搜索结果状态不确定；Career 不会自动重试。",
        }, status_code=409)
    except ao.PreDispatchFailure as exc:
        operation = ao.find(store, "research_search", "opportunity", opportunity["id"], body["idempotency_key"])
        return JSONResponse({
            **(ao._public(operation) if operation else {}),
            "status": "failed", "code": getattr(exc, "code", "auth_error"),
            "message": "Tavily Search Secret 不可用；没有发送搜索请求。",
        }, status_code=503)
    if search.state == "running":
        return ao.unwrap(search)
    if search.state == "outcome_unknown":
        return JSONResponse({
            **ao._public(search.operation),
            "code": search.operation.get("error_code") or "provider_error",
            "message": "搜索结果状态不确定；Career 不会自动重试。",
        }, status_code=409)
    if search.state == "failed":
        return JSONResponse({
            **ao._public(search.operation),
            "status": "failed",
            "code": search.operation.get("error_code") or "provider_error",
            "message": "搜索失败；Career 不会自动重试或切换搜索服务。",
        }, status_code=503)
    results = search.value
    prepared = _research_compile(store, prepared, results)
    payload, diagnostics, _, clean_pack, budget_info = ModelGateway(store).prepare_payload(
        "research_update", prepared["pack"], _research_output_schema(prepared["sources"]), body.get("model_config_id")
    )
    prepared.update(pack=clean_pack, payload=payload, diagnostics=diagnostics, budget=budget_info)
    value = outbound.create_preparation(
        store, task_type="research_update",
        target={"kind": "opportunity", "id": opportunity["id"]},
        client_intent=client_intent,
        packet=clean_pack, payload=payload, manifest=prepared["manifest"],
        diagnostics=diagnostics, budget_info=budget_info,
    )
    _VOLATILE_RESEARCH_PREPARATIONS[value["prepared_id"]] = prepared
    return value


def _research_prepare_for_execution(store, opportunity_id, body):
    base = _research_prepare(store, opportunity_id, body)
    volatile = _VOLATILE_RESEARCH_PREPARATIONS.get(body.get("prepared_id"))
    if volatile is None:
        raise Conflict("准备对象上下文已过期，请重新确认搜索和发送内容")
    current = _research_compile(store, base, volatile["results"])
    payload, diagnostics, _, clean_pack, budget_info = ModelGateway(store).prepare_payload(
        "research_update", current["pack"], _research_output_schema(current["sources"]), body.get("model_config_id")
    )
    outbound.validate_preparation(
        store, body["prepared_id"], task_type="research_update",
        target={"kind": "opportunity", "id": base["opportunity"]["id"]},
        client_intent=_research_client_intent(opportunity_id, body),
        payload_hash=body.get("payload_hash"), packet=clean_pack, payload=payload,
        manifest=current["manifest"],
    )
    current.update(pack=clean_pack, payload=payload, diagnostics=diagnostics, budget=budget_info)
    return current


def _research_dispatch(store, prepared, binder):
    if "pack" not in prepared:
        raise ao.PreDispatchFailure("Research 必须先完成已确认的 SearchProvider 搜索")
    sources = prepared.get("sources") or []
    if not any(
        isinstance(source, dict) and source.get("purpose") == "web_source"
        for source in sources
    ):
        raise ao.PreDispatchFailure("Research Search 来源不存在，未调用模型")
    result, diagnostics = ModelGateway(store).generate(
        "research_update", prepared["pack"], _research_output_schema(sources),
        prepared["body"].get("model_config_id"),
        before_call=lambda payload_hash: binder(payload_hash, prepared["manifest"]),
        operation_id=prepared.get("_operation_id"),
        target={"kind": "opportunity", "id": prepared["opportunity"]["id"]},
    )
    return result, diagnostics


def _research_persist(store, prepared, result, diagnostics):
    try:
        sources = prepared["sources"]
        search_backed = any(
            isinstance(source, dict) and source.get("purpose") == "web_source"
            for source in sources
        )
        result = rs.normalise_proposal_output(result, require_source_refs=search_backed)
        company_items = result["company_items"]
        opportunity_items = result["opportunity_items"]
        source_by_url = {
            source["selected_content"]["url"]: source for source in sources if source["purpose"] == "web_source"
        }
        for group, target_items, owner_id in (
            ("company_items", company_items, prepared["opportunity"]["company_id"]),
            ("opportunity_items", opportunity_items, prepared["opportunity"]["id"]),
        ):
            current_items = prepared["company"]["items"] if target_items is company_items else prepared["research"]["items"]
            for index, item in enumerate(target_items):
                item_path = f"{group}[{index}]"
                # A search title/URL is only a lead.  The model cannot turn
                # metadata into a fact or an independently verified claim.
                item.update(
                    classification="unknown", evidence_status="lead" if item["source_refs"] else "unknown",
                    evidence=[], verification={"user_confirmed": False, "independently_verified": False},
                )
                refs = []
                for ref_index, ref in enumerate(item["source_refs"]):
                    ref_path = f"{item_path}.source_refs[{ref_index}]"
                    if ref["url"] not in source_by_url:
                        raise rs.ResearchProposalValidationError(
                            "source_not_in_current_search", ref_path + ".url"
                        )
                    source = source_by_url[ref["url"]]
                    expected_source_id = source["id"]
                    if ref.get("id") is not None and ref["id"] != expected_source_id:
                        raise rs.ResearchProposalValidationError("source_id_mismatch", ref_path + ".id")
                    refs.append({**ref, "kind": "web_source", "id": expected_source_id,
                                 "owner_id": owner_id, "scope": "company" if target_items is company_items else "opportunity",
                                 "revision": source["revision"], "hash": digest(source["selected_content"]),
                                 "retrieved_at": source["selected_content"].get("retrieved_at"),
                                 "date_status": source["selected_content"].get("date_status", "unknown")})
                item["source_refs"] = refs
                duplicate = next((old for old in current_items if digest({
                    "owner_id": owner_id, "content": old.get("content"),
                    "source_refs": old.get("source_refs", []),
                }) == digest({"owner_id": owner_id, "content": item.get("content"), "source_refs": refs})), None)
                if duplicate:
                    item["duplicate_of"] = duplicate["id"]
    except rs.ResearchProposalValidationError as exc:
        raise ao.AIValidationError(str(exc), code=exc.code) from exc
    except (Invalid, TypeError, AttributeError, KeyError) as exc:
        raise ao.AIValidationError(str(exc)) from exc
    opportunity = prepared["opportunity"]
    body = prepared["body"]
    proposal = {
        "id": "research-proposal:" + uid(), "opportunity_id": opportunity["id"],
        "company_id": opportunity["company_id"], "company_items": company_items,
        "opportunity_items": opportunity_items,
        "expected_company_revision": prepared["company"]["revision"],
        "expected_opportunity_revision": prepared["research"]["revision"], "source_urls": prepared["results"],
        "manifest": prepared["manifest"],
        "request_key": body["idempotency_key"], "request_fingerprint": prepared["request_fingerprint"],
        "context": {"policy_version": prepared["pack"]["policy_version"], "source_count": len(prepared["sources"])},
        "status": "pending", "created_at": now(), "model": diagnostics,
    }
    with store.connect() as c:
        store._record(c, "research_proposal", proposal)
    return proposal


def update(store, opportunity_id, body):
    allowed = {"idempotency_key", "model_config_id", "search_confirmed", "prepared_id", "payload_hash", "confirm_outbound"}
    if set(body) - allowed: raise Invalid("Research 更新包含不允许的字段")
    key = required(body.get("idempotency_key"), "idempotency_key", 200)
    request_fingerprint = digest(_research_client_intent(opportunity_id, body))
    with store.connect(False) as c:
        opportunity = op.resolve(store, c, opportunity_id)
        for previous in store._records(c, "research_proposal"):
            if previous.get("opportunity_id") == opportunity["id"] and previous.get("request_key") == key:
                if previous.get("request_fingerprint") != request_fingerprint:
                    raise Conflict("请求标识已用于不同 Research 提案")
                if not ao.find(store, "research_update", "opportunity", opportunity["id"], key):
                    return previous
    if body.get("search_confirmed") is not True:
        query = _research_search_query(opportunity)
        return JSONResponse({
            "status": "search_confirmation_required",
            "target": {"kind": "opportunity", "id": opportunity["id"]},
            "provider": "tavily",
            "destination": "https://api.tavily.com/search",
            "fields": ["query"],
            "query": query,
        }, status_code=409)
    if not body.get("prepared_id") or body.get("confirm_outbound") is not True:
        preparation = _research_create_preparation(store, opportunity_id, body)
        if isinstance(preparation, JSONResponse):
            return preparation
        return JSONResponse(preparation, status_code=409)
    execution = ao.execute(
        store, task_type="research_update", target_kind="opportunity",
        target_id=op.canonical_id(opportunity_id), idempotency_key=key,
        client_intent={"opportunity_id": op.canonical_id(opportunity_id), "body": body},
        prepare=lambda: _research_prepare_for_execution(store, opportunity_id, body),
        dispatch=lambda prepared, binder: _research_dispatch(store, prepared, binder),
        persist=lambda prepared, result, diagnostics: _research_persist(store, prepared, result, diagnostics),
    )
    return ao.unwrap(execution)


def resolve(store, opportunity_id, proposal_id, body):
    if set(body) - {"decision"}: raise Invalid("Research proposal 包含不允许的字段")
    if body.get("decision") not in {"accept", "reject"}: raise Invalid("decision 只能是 accept 或 reject")
    with store.connect() as c:
        opportunity = op.resolve(store, c, opportunity_id)
        proposal = store._get(c, proposal_id, "research_proposal", True)
        if proposal["opportunity_id"] != opportunity["id"]: raise Missing("Research proposal 不存在")
        if proposal["status"] != "pending": return proposal
        if body["decision"] == "reject":
            proposal.update(status="rejected", resolved_at=now())
            store._record(c, "research_proposal", proposal)
            return proposal
        if not _search_proposal_has_valid_sources(proposal):
            raise Conflict("proposal_requires_regeneration: Search 提案缺少有效来源引用")
        opportunity = op.writable(store, c, opportunity_id)
        if proposal.get("company_id") != opportunity["company_id"]:
            raise Conflict("target_changed: Research 提案目标公司已变化")
        cm.validate(store, c, proposal.get("manifest"))
        current_company = _get(store, c, "company_research", opportunity["company_id"])
        current_opportunity = _get(store, c, "opportunity_research", opportunity["id"])
        changed = False
        if proposal["company_items"]:
            current_company = rs.append(store, c, "company_research", opportunity["company_id"], proposal["company_items"], current_company["revision"])
            changed = True
        if proposal["opportunity_items"]:
            current_opportunity = rs.append(store, c, "opportunity_research", opportunity["id"], proposal["opportunity_items"], current_opportunity["revision"])
            changed = True
        proposal["applied_revisions"] = {"company": current_company["revision"], "opportunity": current_opportunity["revision"]}
        if changed:
            store._bump(c)
        proposal.update(status="accepted" if body["decision"] == "accept" else "rejected", resolved_at=now())
        store._record(c, "research_proposal", proposal)
        return proposal


def _search_proposal_has_valid_sources(proposal):
    """Keep legacy Search-backed proposals without traceable refs unappliable."""
    if "source_urls" not in proposal:
        return True
    sources = proposal.get("source_urls")
    if not isinstance(sources, list) or not sources:
        return False
    allowed_urls = {
        source.get("url") for source in sources
        if isinstance(source, dict) and isinstance(source.get("url"), str)
    }
    for group in ("company_items", "opportunity_items"):
        items = proposal.get(group)
        if not isinstance(items, list):
            return False
        for item in items:
            if not isinstance(item, dict):
                return False
            refs = item.get("source_refs")
            if not isinstance(refs, list) or not refs:
                return False
            for ref in refs:
                if not isinstance(ref, dict):
                    return False
                url = ref.get("url")
                if (
                    not isinstance(url, str)
                    or url not in allowed_urls
                    or ref.get("id") != "web:" + digest(url)
                    or ref.get("kind") != "web_source"
                ):
                    return False
    return True


def _proposal_views(store, c, opportunity_id):
    opportunity = op.resolve(store, c, opportunity_id)
    result = []
    for proposal in store._records(c, "research_proposal"):
        if proposal.get("opportunity_id") != opportunity["id"]:
            continue
        proposal = dict(proposal)
        if proposal.get("status") == "pending":
            try:
                cm.validate(store, c, proposal.get("manifest"))
            except Conflict as exc:
                proposal.update(stale=True, stale_reason=str(exc))
        result.append(proposal)
    return result


def manual_item(store, opportunity_id, body, item_id=None):
    allowed = {
        "scope", "category", "content", "classification", "evidence_status", "evidence",
        "verification", "source_refs", "supersedes", "replaces", "status", "expected_revision", "idempotency_key",
    }
    if set(body) - allowed: raise Invalid("Research 手动编辑包含不允许的字段")
    if body.get("scope") not in {"company", "opportunity"}: raise Invalid("Research scope 不合法")
    key = required(body.get("idempotency_key"), "idempotency_key", 200)
    request_fingerprint = digest([opportunity_id, item_id, body])
    with store.connect() as c:
        opportunity = op.writable(store, c, opportunity_id)
        for previous in store._records(c, "research_command"):
            if previous.get("idempotency_key") == key:
                if previous.get("fingerprint") != request_fingerprint:
                    raise Conflict("请求标识已用于不同 Research 编辑")
                return previous["result"]
        owner = opportunity["company_id"] if body["scope"] == "company" else opportunity["id"]
        kind = "company_research" if body["scope"] == "company" else "opportunity_research"
        current = _get(store, c, kind, owner)
        expected = body.get("expected_revision")
        if expected != current["revision"]: raise Conflict("Research 已更新，请重新载入")
        evidence = rs.normalise_item({"content": body.get("content"), "category": body.get("category"),
                                      "classification": body.get("classification"),
                                      "evidence_status": body.get("evidence_status", "unknown"),
                                      "evidence": body.get("evidence", []),
                                      "verification": body.get("verification", {})}).get("evidence", [])
        evidence_status = body.get("evidence_status", "unknown")
        if evidence_status in {"excerpt_present", "user_confirmed"} and not evidence:
            raise Invalid("Research evidence_status 需要证据摘录")
        if body.get("verification", {}).get("independently_verified") is True:
            raise Invalid("Research 不能在本地手动声明 independently_verified")
        _validate_evidence(evidence, owner, body["scope"])
        refs = _manual_source_refs(body.get("source_refs", []), owner, body["scope"])
        item_payload = {field: body.get(field) for field in (
            "category", "content", "classification", "evidence", "verification",
            "supersedes", "replaces",
        )}
        item_payload.update(
            evidence_status=body.get("evidence_status", "unknown"),
            status=body.get("status", "active"), verification=body.get("verification", {}), source_refs=refs,
        )
        item = _item(item_payload)
        if not evidence and body.get("classification") in {"fact", "inference"}:
            item.update(classification="unknown", evidence_status="lead" if refs else "unknown")
        _validate_relations(item, current["items"], item_id)
        items = list(current["items"])
        if item_id:
            match = next((x for x in items if x["id"] == item_id), None)
            if not match: raise Missing("Research item 不存在")
            item["id"] = item_id
            item["revision"] = match.get("revision", 0) + 1
            items[items.index(match)] = item
        else: items.append(item)
        item["evidence"] = [dict(value, item_revision=item["revision"]) for value in item["evidence"]]
        result = rs.save(store, c, kind, owner, {**current, "items": items}, expected)
        store._bump(c)
        store._record(c, "research_command", {
            "id": "research-command:" + uid(), "idempotency_key": key,
            "fingerprint": request_fingerprint, "result": result, "created_at": now(),
        })
        return result


def retract_item(store, opportunity_id, item_id, body):
    if set(body) - {"scope", "expected_revision", "idempotency_key"}:
        raise Invalid("Research 撤回包含不允许的字段")
    if body.get("scope") not in {"company", "opportunity"}:
        raise Invalid("Research scope 不合法")
    key = required(body.get("idempotency_key"), "idempotency_key", 200)
    with store.connect(False) as c:
        opportunity = op.resolve(store, c, opportunity_id)
        owner = opportunity["company_id"] if body["scope"] == "company" else opportunity["id"]
        kind = "company_research" if body["scope"] == "company" else "opportunity_research"
        current = _get(store, c, kind, owner)
        target = next((item for item in current["items"] if item["id"] == item_id), None)
        if target is None:
            raise Missing("Research item 不存在")
        source = {field: target.get(field) for field in (
            "category", "content", "classification", "evidence_status", "evidence",
            "verification", "source_refs", "supersedes", "replaces",
        )}
    source.update(scope=body["scope"], status="retracted", expected_revision=body.get("expected_revision"), idempotency_key=key)
    return manual_item(store, opportunity_id, source, item_id)


def router(store):
    api = APIRouter(prefix="/api/opportunities/{opportunity_id}")
    @api.get("/research-overview")
    def overview(opportunity_id: str):
        with store.connect(False) as c: return view(store, c, opportunity_id)
    @api.post("/research/update")
    def research_update(opportunity_id: str, body: dict): return update(store, opportunity_id, body)
    @api.get("/research-proposals")
    def proposals(opportunity_id: str):
        with store.connect(False) as c:
            return _proposal_views(store, c, opportunity_id)
    @api.post("/research-proposals/{proposal_id}/resolve")
    def proposal_resolve(opportunity_id: str, proposal_id: str, body: dict): return resolve(store, opportunity_id, proposal_id, body)
    @api.post("/research/items")
    def item_create(opportunity_id: str, body: dict): return manual_item(store, opportunity_id, body)
    @api.put("/research/items/{item_id}")
    def item_update(opportunity_id: str, item_id: str, body: dict): return manual_item(store, opportunity_id, body, item_id)
    @api.post("/research/items/{item_id}/retract")
    def item_retract(opportunity_id: str, item_id: str, body: dict): return retract_item(store, opportunity_id, item_id, body)
    return api
