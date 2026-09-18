"""Structured local resume editor endpoints.

The editor has a deliberately separate storage namespace from the analysis
context and the legacy text resume tables.
"""
import base64
import binascii
import hashlib
import html
from copy import deepcopy
import json
import re
from pathlib import Path

from fastapi import APIRouter

from .artifacts import _atomic_write, _target, read_artifact
from .core import Conflict, Invalid, Missing, dump, digest, now, uid


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MAX_DOCUMENT = 1024 * 1024
_MAX_PDF = 5 * 1024 * 1024


def _document(value):
    if not isinstance(value, dict):
        raise Invalid("文档必须是对象")
    if value.get("schemaVersion") != 1:
        raise Invalid("文档 schemaVersion 必须为 1")
    required = ("profile", "sections", "formatting", "meta")
    if any(k not in value for k in required):
        raise Invalid("文档缺少必需结构")
    if not isinstance(value["profile"], dict) or not isinstance(value["sections"], list):
        raise Invalid("文档 profile 或 sections 结构不正确")
    if not isinstance(value["formatting"], dict) or not isinstance(value["meta"], dict):
        raise Invalid("文档 formatting 或 meta 结构不正确")
    encoded = dump(value).encode("utf-8")
    if len(encoded) > _MAX_DOCUMENT:
        raise Invalid("文档大小不能超过 1MB")
    profile = value["profile"]
    if not isinstance(profile.get("id"), str) or not _ID.fullmatch(profile["id"]):
        raise Invalid("profile.id 不合法")
    if not isinstance(profile.get("name"), str):
        raise Invalid("profile.name 必须是字符串")
    if not isinstance(profile.get("contacts"), list):
        raise Invalid("profile.contacts 必须是数组")
    for contact in profile["contacts"]:
        if not isinstance(contact, dict) or not isinstance(contact.get("id"), str) or not _ID.fullmatch(contact["id"]):
            raise Invalid("联系方式结构或 ID 不合法")
        if not isinstance(contact.get("content"), str) or contact.get("kind") not in ("identity", "link") or not isinstance(contact.get("href"), str):
            raise Invalid("联系方式字段不合法")
    allowed = {"experience", "projects", "education", "skills"}
    section_types = set()
    for section in value["sections"]:
        if not isinstance(section, dict) or section.get("type") not in allowed:
            raise Invalid("文档包含不支持的 section")
        if section["type"] in section_types:
            raise Invalid("同类分区只能有一个，请把条目放入同一分区")
        section_types.add(section["type"])
        if not isinstance(section.get("id"), str) or not _ID.fullmatch(section["id"]):
            raise Invalid("section ID 不合法")
        if not isinstance(section.get("title"), str) or not isinstance(section.get("items"), list):
            raise Invalid("section 字段不合法")
        for item in section["items"]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not _ID.fullmatch(item["id"]):
                raise Invalid("section 条目结构或 ID 不合法")
            if section["type"] == "skills":
                if not isinstance(item.get("content"), str):
                    raise Invalid("技能条目 content 必须是字符串")
            else:
                fields = {"experience": ("organization", "role", "date"), "projects": ("title", "responsibility", "date"), "education": ("school", "major", "date")}[section["type"]]
                if any(not isinstance(item.get(field), str) for field in fields) or not isinstance(item.get("bullets"), list):
                    raise Invalid("经历条目字段或 bullets 结构不合法")
                for bullet in item["bullets"]:
                    if not isinstance(bullet, dict) or not isinstance(bullet.get("id"), str) or not _ID.fullmatch(bullet["id"]) or not isinstance(bullet.get("content"), str):
                        raise Invalid("要点结构或 ID 不合法")
    seen = set()

    def walk(item):
        if isinstance(item, dict):
            if "id" in item:
                ident = item["id"]
                if not isinstance(ident, str) or not _ID.fullmatch(ident):
                    raise Invalid("文档条目 ID 不合法")
                if ident in seen:
                    raise Invalid("文档条目 ID 不能重复")
                seen.add(ident)
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
    walk(value)
    return value


def _blank():
    return {"schemaVersion": 1, "profile": {"id": "profile-main", "name": "", "contacts": []}, "sections": [], "formatting": {}, "meta": {}}


def _result(document, revision, saved_at):
    return {"document": document, "revision": revision, "savedAt": saved_at}


def _draft(c, store):
    row = c.execute("SELECT revision,body FROM current WHERE id=? AND kind='editor_draft'", ("editor-main",)).fetchone()
    if not row:
        return _blank(), 0, None
    body = json.loads(row[1])
    return body["document"], row[0], body.get("savedAt")


def _pdf(data):
    if not isinstance(data, str):
        raise Invalid("PDF 必须是 Base64 字符串")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError, TypeError) as exc:
        raise Invalid("PDF 数据不是有效 Base64") from exc
    if not raw or len(raw) > _MAX_PDF:
        raise Invalid("PDF 大小必须不超过 5MB")
    if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-1024:]:
        raise Invalid("PDF 文件头或尾部标记无效")
    return raw


def _fact_allowed(entry, job_id):
    return entry.get('status') == 'active' and (entry.get('scope_type') == 'personal' or
        (job_id and entry.get('scope_type') == 'job' and entry.get('scope_id') == job_id))


def _item_ids(document):
    return {document['profile']['id']} | {item['id'] for section in document['sections'] for item in section['items']}


def _apply_profile(document, profile):
    """Refresh the current resume contact block from the saved basic profile."""
    document = deepcopy(document)
    basics = profile['basics']
    document['profile']['name'] = html.escape(basics['name'])
    old_contacts = document['profile']['contacts']
    identity = [
        dict(id='contact-'+key, kind='identity', content=label+'：'+html.escape(basics[key]), href='')
        for key, label in [('phone','电话'),('email','邮箱'),('wechat','微信')]
        if basics.get(key)
    ]
    if 'wechat' not in basics:
        identity += [contact for contact in old_contacts if contact['id'] == 'contact-wechat' or contact['content'].startswith('微信：')]
    websites = []
    if basics.get('github'):
        websites.append(dict(id='contact-github', kind='link', content='GitHub：'+html.escape(basics['github']), href=basics['github']))
    websites += [
        dict(id='contact-profile-web-'+str(index), kind='link',
             content=html.escape((link['label']+'：' if link['label'] else '')+link['url']), href=link['url'])
        for index, link in enumerate(basics.get('links', []))
    ]
    managed_ids = {'contact-phone', 'contact-email', 'contact-wechat', 'contact-github'}
    website_urls = {contact['href'] for contact in websites}
    unmanaged = [
        contact for contact in old_contacts
        if contact['kind'] == 'link' and contact['id'] not in managed_ids
        and not contact['id'].startswith('contact-profile-web-') and contact['href'] not in website_urls
    ]
    document['profile']['contacts'] = identity + websites + unmanaged
    refs = document['meta'].setdefault('source_refs', [])
    refs[:] = [ref for ref in refs if ref['source_kind'] != 'profile']
    refs.append(dict(item_id=document['profile']['id'], source_kind='profile', source_id='profile',
                     revision=profile['revision'], hash=digest(profile), title='基础信息',
                     scope_type='personal', scope_id=''))
    return document


def editor_router(store):
    """Legacy read adapter. No unscoped writes survive schema v3."""
    router = APIRouter(prefix='/api/editor')
    @router.get('')
    def legacy():
        with store.connect(False) as c:
            doc, revision, saved = _draft(c,store)
            return dict(_result(doc,revision,saved), legacy=True, read_only=True, document_hash=digest(doc))
    @router.get('/versions')
    def versions():
        from .resume_documents import version_summary
        with store.connect(False) as c:
            return dict(versions=[version_summary(v) for v in store._records(c,'editor_version')])
    @router.get('/versions/{vid}')
    def version(vid: str):
        with store.connect(False) as c:
            v=store._get(c,vid,'editor_version',True)
            a=store._get(c,v['artifact_id'],'artifact',True)
            return dict(v,document_hash=digest(v['document']),artifact_hash=a['sha256'])
    @router.api_route('', methods=['PUT','POST','DELETE'])
    @router.api_route('/{path:path}', methods=['PUT','POST','DELETE'])
    def retired(path: str = ''):
        raise Conflict('legacy_editor_read_only: 请选择机会自己的简历工作稿')
    return router
