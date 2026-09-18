"""Research workspace: sourced company/opportunity intelligence and proposals."""
import html
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from fastapi import APIRouter

from .core import Conflict, Invalid, Missing, digest, now, required, uid
from . import opportunity as op
from .model_gateway import ModelGateway


CATEGORIES = {"company", "product_business", "current_dynamic", "role", "business", "department", "team", "why_role", "recruiting_context", "challenge", "unknown"}
CLASSIFICATIONS = {"fact", "inference", "unknown"}


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


def web_search(company, title, jd):
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


def _id(kind, owner): return kind + ":" + digest(owner)


def _get(store, c, kind, owner):
    ident = _id(kind, owner)
    row = c.execute("SELECT body FROM current WHERE id=? AND kind=?", (ident, kind)).fetchone()
    if row: return json.loads(row[0])
    key = "company_id" if kind == "company_research" else "opportunity_id"
    return {"id": ident, key: owner, "items": [], "revision": 0, "created_at": now()}


def _item(value, source_refs=None):
    if not isinstance(value, dict): raise Invalid("Research item 必须是对象")
    category = value.get("category", "unknown")
    content = value.get("content", "")
    classification = value.get("classification", "unknown")
    if category not in CATEGORIES or classification not in CLASSIFICATIONS or not isinstance(content, str) or not content.strip() or len(content) > 10000:
        raise Invalid("Research item 的 category/content/classification 不合法")
    refs = value.get("source_refs", source_refs or [])
    if not isinstance(refs, list) or len(refs) > 10: raise Invalid("Research 来源过多")
    return {"id": value.get("id") or uid(), "category": category, "content": content.strip(), "classification": classification, "source_refs": refs, "updated_at": now()}


def view(store, c, opportunity_id):
    opportunity = op.resolve(store, c, opportunity_id)
    company = _get(store, c, "company_research", opportunity["company_id"])
    research = _get(store, c, "opportunity_research", opportunity["id"])
    return {"company": company, "opportunity": research, "items": research["items"], "revision": research["revision"]}


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


def update(store, opportunity_id, body):
    if set(body) - {"idempotency_key", "model_config_id"}: raise Invalid("Research 更新包含不允许的字段")
    key = required(body.get("idempotency_key"), "idempotency_key", 200)
    with store.connect(False) as c:
        opportunity = op.resolve(store, c, opportunity_id)
        company = _get(store, c, "company_research", opportunity["company_id"])
        research = _get(store, c, "opportunity_research", opportunity["id"])
    results = web_search(opportunity["company"], opportunity["title"], opportunity.get("jd", ""))
    sources = [{"id": "web:" + digest(x["url"]), "revision": 0, "purpose": "web_source", "selected_content": x} for x in results]
    sources.insert(0, {"id": opportunity["id"], "revision": opportunity["revision"], "purpose": "opportunity", "selected_content": {"company": opportunity["company"], "title": opportunity["title"], "jd": opportunity.get("jd", "")}})
    pack = _pack(store, None, opportunity, company, research, sources)
    result, diagnostics = ModelGateway(store).generate("research_update", pack, {"version": 1, "required": ["company_items", "opportunity_items"]}, body.get("model_config_id"))
    company_items = [_item(x, []) for x in result.get("company_items", [])]
    opportunity_items = [_item(x, []) for x in result.get("opportunity_items", [])]
    valid_urls = {x["selected_content"]["url"] for x in sources if x["purpose"] == "web_source"}
    for item in company_items + opportunity_items:
        for ref in item["source_refs"]:
            if ref.get("url") and ref["url"] not in valid_urls: raise Invalid("Research 引用了本轮之外的来源")
    proposal = {"id": "research-proposal:" + uid(), "opportunity_id": opportunity["id"], "company_id": opportunity["company_id"], "company_items": company_items, "opportunity_items": opportunity_items, "expected_company_revision": company["revision"], "expected_opportunity_revision": research["revision"], "source_urls": results, "context": {"policy_version": pack["policy_version"], "source_count": len(sources)}, "status": "pending", "created_at": now(), "model": diagnostics}
    with store.connect() as c:
        store._record(c, "research_proposal", proposal)
    return proposal


def resolve(store, opportunity_id, proposal_id, body):
    if set(body) - {"decision"}: raise Invalid("Research proposal 包含不允许的字段")
    if body.get("decision") not in {"accept", "reject"}: raise Invalid("decision 只能是 accept 或 reject")
    with store.connect() as c:
        opportunity = op.writable(store, c, opportunity_id)
        proposal = store._get(c, proposal_id, "research_proposal", True)
        if proposal["opportunity_id"] != opportunity["id"]: raise Missing("Research proposal 不存在")
        if proposal["status"] != "pending": return proposal
        current_company = _get(store, c, "company_research", opportunity["company_id"])
        current_opportunity = _get(store, c, "opportunity_research", opportunity["id"])
        if current_company["revision"] != proposal["expected_company_revision"] or current_opportunity["revision"] != proposal["expected_opportunity_revision"]:
            raise Conflict("Research 已更新，请重新生成 proposal")
        if body["decision"] == "accept":
            company = store._save(c, "company_research", {**current_company, "items": current_company["items"] + proposal["company_items"]}, current_company["revision"])
            current_opportunity = store._save(c, "opportunity_research", {**current_opportunity, "items": current_opportunity["items"] + proposal["opportunity_items"]}, current_opportunity["revision"])
            proposal["applied_revisions"] = {"company": company["revision"], "opportunity": current_opportunity["revision"]}
            store._bump(c)
        proposal.update(status="accepted" if body["decision"] == "accept" else "rejected", resolved_at=now())
        store._record(c, "research_proposal", proposal)
        return proposal


def manual_item(store, opportunity_id, body, item_id=None):
    allowed = {"scope", "category", "content", "classification", "source_refs", "expected_revision", "idempotency_key"}
    if set(body) - allowed: raise Invalid("Research 手动编辑包含不允许的字段")
    if body.get("scope") not in {"company", "opportunity"}: raise Invalid("Research scope 不合法")
    item = _item(body, body.get("source_refs", [])); owner_key = "company_id" if body["scope"] == "company" else "id"
    with store.connect() as c:
        opportunity = op.writable(store, c, opportunity_id)
        owner = opportunity["company_id"] if body["scope"] == "company" else opportunity["id"]
        kind = "company_research" if body["scope"] == "company" else "opportunity_research"
        current = _get(store, c, kind, owner)
        expected = body.get("expected_revision")
        if expected != current["revision"]: raise Conflict("Research 已更新，请重新载入")
        items = list(current["items"])
        if item_id:
            match = next((x for x in items if x["id"] == item_id), None)
            if not match: raise Missing("Research item 不存在")
            item["id"] = item_id; items[items.index(match)] = item
        else: items.append(item)
        result = store._save(c, kind, {**current, "items": items}, expected)
        store._bump(c)
        return result


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
            opportunity = op.resolve(store, c, opportunity_id)
            return [x for x in store._records(c, "research_proposal") if x.get("opportunity_id") == opportunity["id"]]
    @api.post("/research-proposals/{proposal_id}/resolve")
    def proposal_resolve(opportunity_id: str, proposal_id: str, body: dict): return resolve(store, opportunity_id, proposal_id, body)
    @api.post("/research/items")
    def item_create(opportunity_id: str, body: dict): return manual_item(store, opportunity_id, body)
    @api.put("/research/items/{item_id}")
    def item_update(opportunity_id: str, item_id: str, body: dict): return manual_item(store, opportunity_id, body, item_id)
    return api
