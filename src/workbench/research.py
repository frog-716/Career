"""Research workspace: sourced company/opportunity intelligence and proposals."""
import html
import json
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

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


CATEGORIES = rs.CATEGORIES
CLASSIFICATIONS = rs.CLASSIFICATIONS

# Search results and the compiled request are intentionally process-local and
# short-lived.  The durable preparation/audit records contain only references
# and hashes; after a restart the user must explicitly re-preview the search
# and model payload.
_VOLATILE_RESEARCH_PREPARATIONS = {}


class _SearchParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.results = []; self.href = None; self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "result__a" in attrs.get("class", ""):
            self.href = attrs.get("href"); self.text = []

    def handle_data(self, data):
        if self.href is not None: self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            href = self.href
            query = parse_qs(urlparse(href).query).get("uddg")
            if query: href = unquote(query[0])
            title = html.unescape(" ".join("".join(self.text).split()))
            if href.startswith("http") and title:
                self.results.append({"url": href, "title": title})
            self.href = None; self.text = []


def web_search(company, title, jd, runtime_mode=None):
    require_ai_enabled(runtime_mode)
    query = " ".join(x for x in (company, title, "产品 商业模式 最新动态") if x)
    try:
        response = httpx.get("https://html.duckduckgo.com/html/?q=" + quote_plus(query), timeout=15.0, follow_redirects=False)
        response.raise_for_status()
        parser = _SearchParser(); parser.feed(response.text)
    except httpx.HTTPError as exc:
        raise Invalid("Web Research 暂时不可用，请保留手动研究入口") from exc
    seen, results = set(), []
    for item in parser.results:
        if item["url"] not in seen:
            seen.add(item["url"]); results.append({**item, "retrieved_at": now()})
        if len(results) >= 8: break
    return results


def _id(kind, owner): return rs.research_id(kind, owner)


def _get(store, c, kind, owner):
    return rs.get(store, c, kind, owner)


def _item(value, source_refs=None):
    return rs.normalise_item(value, source_refs)


_SEARCH_CHALLENGE_MARKERS = (
    "captcha", "验证后继续", "verify you are human", "unusual traffic",
    "robot check", "机器人验证", "security challenge",
)


def _search_result_is_challenge(value):
    text = " ".join(str(value.get(key, "")) for key in ("title", "url")).lower()
    return any(marker.lower() in text for marker in _SEARCH_CHALLENGE_MARKERS)


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


def _research_output_schema():
    return {"version": 1, "required": ["company_items", "opportunity_items"]}


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
    with store.connect(False) as c:
        existing = next((row for row in store._records(c, "ai_preparation")
                         if row.get("task_type") == "research_update"
                         and row.get("target") == {"kind": "opportunity", "id": opportunity["id"]}
                         and row.get("idempotency_key") == body.get("idempotency_key")), None)
    if existing:
        if existing.get("client_intent_hash") != digest(client_intent):
            raise Conflict("请求标识已用于不同 Research 准备操作")
        volatile = _VOLATILE_RESEARCH_PREPARATIONS.get(existing["id"])
        if volatile is None:
            raise Conflict("准备对象上下文已过期，请重新确认搜索和发送内容")
        return outbound.public_preparation(existing, payload_preview=volatile["payload"])
    results = web_search(opportunity["company"], opportunity["title"], opportunity.get("jd", ""), store.runtime_mode)
    prepared = _research_compile(store, prepared, results)
    payload, diagnostics, _, clean_pack, budget_info = ModelGateway(store).prepare_payload(
        "research_update", prepared["pack"], _research_output_schema(), body.get("model_config_id")
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
        "research_update", current["pack"], _research_output_schema(), body.get("model_config_id")
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
        opportunity = prepared["opportunity"]
        _research_compile(store, prepared, web_search(opportunity["company"], opportunity["title"], opportunity.get("jd", ""), store.runtime_mode))
    result, diagnostics = ModelGateway(store).generate(
        "research_update", prepared["pack"], _research_output_schema(),
        prepared["body"].get("model_config_id"),
        before_call=lambda payload_hash: binder(payload_hash, prepared["manifest"]),
        operation_id=prepared.get("_operation_id"),
        target={"kind": "opportunity", "id": prepared["opportunity"]["id"]},
    )
    return result, diagnostics


def _research_persist(store, prepared, result, diagnostics):
    try:
        sources = prepared["sources"]
        company_items = [_item(x, []) for x in result.get("company_items", [])]
        opportunity_items = [_item(x, []) for x in result.get("opportunity_items", [])]
        source_by_url = {
            source["selected_content"]["url"]: source for source in sources if source["purpose"] == "web_source"
        }
        for target_items, owner_id in ((company_items, prepared["opportunity"]["company_id"]),
                                       (opportunity_items, prepared["opportunity"]["id"])):
            current_items = prepared["company"]["items"] if target_items is company_items else prepared["research"]["items"]
            for item in target_items:
                # A search title/URL is only a lead.  The model cannot turn
                # metadata into a fact or an independently verified claim.
                item.update(
                    classification="unknown", evidence_status="lead" if item["source_refs"] else "unknown",
                    evidence=[], verification={"user_confirmed": False, "independently_verified": False},
                )
                refs = []
                for ref in item["source_refs"]:
                    if not isinstance(ref, dict) or ref.get("url") not in source_by_url:
                        raise ao.AIValidationError("Research 引用了本轮之外的来源")
                    source = source_by_url[ref["url"]]
                    expected_source_id = source["id"]
                    if ref.get("id") is not None and ref.get("id") != expected_source_id:
                        raise ao.AIValidationError("Research 来源 ID 与本轮来源不匹配")
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
        query = " ".join(x for x in (opportunity["company"], opportunity["title"], "产品 商业模式 最新动态") if x)
        return JSONResponse({
            "status": "search_confirmation_required",
            "target": {"kind": "opportunity", "id": opportunity["id"]},
            "query": query,
        }, status_code=409)
    if not body.get("prepared_id") or body.get("confirm_outbound") is not True:
        return JSONResponse(_research_create_preparation(store, opportunity_id, body), status_code=409)
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
