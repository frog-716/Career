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


def _save_document(c, store, document, expected):
    _, revision, _ = _draft(c, store)
    if expected != revision:
        raise Conflict("编辑稿已在其它窗口更新，请重新载入比较后保存")
    saved_at = now()
    obj = {"id": "editor-main", "document": document, "savedAt": saved_at}
    c.execute("INSERT INTO current VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,revision=excluded.revision,body=excluded.body", ("editor-main", "editor_draft", revision + 1, dump(obj)))
    c.execute("INSERT INTO revisions VALUES(?,?,?,?)", ("editor-main", revision + 1, dump(obj), saved_at))
    return _result(document, revision + 1, saved_at)


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


def sync_profile_to_draft(c, store, profile):
    """Keep the current draft in sync when the user saves basic profile data."""
    document, revision, _ = _draft(c, store)
    document = _apply_profile(document, profile)
    return _save_document(c, store, _document(document), revision)


def editor_router(store):
    router = APIRouter(prefix="/api/editor")

    @router.get("")
    def get_editor():
        with store.connect(False) as c:
            document, revision, saved_at = _draft(c, store)
            return _result(document, revision, saved_at)

    @router.put("")
    def put_editor(body: dict):
        document = _document(body.get("document"))
        expected = body.get("expected_revision")
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
            raise Invalid("expected_revision 不合法")
        with store.connect() as c:
            old, _, _ = _draft(c, store)
            if document['meta'].get('source_refs', []) != old['meta'].get('source_refs', []):
                raise Conflict("材料来源不可改写，请保留当前来源信息；恢复历史请使用恢复版本")
            return _save_document(c, store, document, expected)

    @router.get('/materials')
    def materials(job_id: str = ''):
        with store.connect(False) as c:
            if job_id: store._get(c, job_id, 'job')
            return dict(entries=[e for e in store._current(c, 'wiki_entry') if _fact_allowed(e, job_id)],
                        profile=store._get(c, 'profile', 'profile'))

    @router.get('/sources')
    def sources():
        with store.connect(False) as c:
            document, _, _ = _draft(c, store)
            ids = _item_ids(document)
            results = []
            for ref in document['meta'].get('source_refs', []):
                row = c.execute('SELECT body FROM current WHERE id=? AND kind=?', (ref['source_id'], ref['source_kind'])).fetchone()
                current = json.loads(row[0]) if row else None
                status = 'current'
                if ref['item_id'] not in ids: status = 'removed'
                elif not current or current.get('status') == 'withdrawn': status = 'withdrawn'
                elif current['revision'] != ref['revision']: status = 'updated'
                results.append(dict(ref, status=status))
            return dict(sources=results)

    @router.post('/select-facts')
    def select_facts(body: dict):
        from .knowledge import _request, _remember, _expected
        expected = _expected(body.get('expected_revision'))
        selections = body.get('selections', [])
        include_profile = body.get('include_profile', False)
        if type(include_profile) is not bool: raise Invalid('基础信息选择不合法')
        if not isinstance(selections, list) or len(selections) > 30 or (not selections and not include_profile):
            raise Invalid('请明确选择不超过30条已确认资料')
        job_id = body.get('job_id') or ''
        if not isinstance(job_id, str): raise Invalid('岗位不合法')
        with store.connect() as c:
            previous, key, fingerprint = _request(store, c, body.get('idempotency_key'), 'resume_select_facts', body)
            if previous is not None: return previous
            if job_id: store._get(c, job_id, 'job')
            document, revision, _ = _draft(c, store)
            if revision != expected: raise Conflict('工作稿已更新，请保存并重新选择材料')
            document = deepcopy(document)
            refs = document['meta'].setdefault('source_refs', [])
            present = _item_ids(document)
            imported = {ref['source_id'] for ref in refs if ref['item_id'] in present}
            for selection in selections:
                if not isinstance(selection, dict) or not isinstance(selection.get('id'), str): raise Invalid('选材不合法')
                e = store._get(c, selection['id'], 'wiki_entry')
                if not _fact_allowed(e, job_id): raise Invalid('只能选择个人或当前机会的有效Wiki；任职资料须先确认允许复用的个人事实')
                if type(selection.get('revision')) is not int or selection['revision'] != e['revision']: raise Conflict('所选事实已更新，请重新检查材料')
                if e['id'] in imported: raise Conflict('此事实已选入当前稿，请编辑已有表达或移除条目后重选')
                kind = selection.get('section_type')
                if kind not in {'skills','experience','projects','education'}: raise Invalid('简历分区不合法')
                section = next((x for x in document['sections'] if x['type'] == kind), None)
                if section is None:
                    section = dict(id='section-'+kind, type=kind, title={'skills':'专业技能','experience':'工作经历','projects':'项目经历','education':'教育背景'}[kind], items=[])
                    document['sections'].append(section)
                item_id = uid()
                title = html.escape(e['title']); content = html.escape(e['content']).replace('\n','<br>')
                if kind == 'skills': item = dict(id=item_id, content=title+'：'+content)
                else:
                    fields = {'experience':dict(organization='', role=title, date=''), 'projects':dict(title=title, responsibility='', date=''), 'education':dict(school=title, major='', date='')}[kind]
                    item = dict(id=item_id, bullets=[dict(id=uid(), content=content)], **fields)
                section['items'].append(item)
                refs.append(dict(item_id=item_id, source_kind='wiki_entry', source_id=e['id'], revision=e['revision'], hash=digest(e), title=e['title'], scope_type=e['scope_type'], scope_id=e['scope_id']))
                imported.add(e['id'])
            if include_profile:
                p = store._get(c, 'profile', 'profile')
                if p.get('mode') != 'structured': raise Invalid('请先在基础资料中明确整理姓名和联系方式')
                if type(body.get('profile_revision')) is not int or body['profile_revision'] != p['revision']: raise Conflict('基础资料已更新，请重新检查')
                # Explicit reselection refreshes the identity expression; old draft revisions and versions retain old refs.
                document = _apply_profile(document, p)
            result = _save_document(c, store, _document(document), expected)
            _remember(store, c, key, fingerprint, result)
            return result

    @router.get("/versions")
    def list_versions():
        with store.connect(False) as c:
            versions = []
            for row in c.execute("SELECT body FROM records WHERE kind='editor_version' ORDER BY rowid DESC"):
                v = json.loads(row[0])
                versions.append({"id": v["id"], "name": v["name"], "createdAt": v["createdAt"], "artifact_id": v["artifact_id"]})
            return {"versions": versions}

    @router.post("/versions")
    def create_version(body: dict):
        name = body.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
            raise Invalid("版本名称不能为空或超出长度限制")
        document = _document(body.get("document"))
        expected = body.get("expected_revision")
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
            raise Invalid("expected_revision 不合法")
        key = body.get("idempotency_key")
        if not isinstance(key, str) or not key.strip() or len(key) > 100:
            raise Invalid("请求标识不能为空或超出长度限制")
        raw = _pdf(body.get("pdf_base64"))
        fingerprint = digest([name.strip(), document, expected, hashlib.sha256(raw).hexdigest()])
        written = None
        try:
            with store.connect() as c:
                existing = c.execute("SELECT body FROM records WHERE kind='editor_version' AND json_extract(body,'$.idempotency_key')=?", (key.strip(),)).fetchone()
                if existing:
                    version = json.loads(existing[0])
                    if version.get("request_fingerprint") != fingerprint:
                        raise Conflict("请求标识已用于不同版本")
                    return {"id": version["id"], "name": version["name"], "createdAt": version["createdAt"], "document": version["document"], "artifact_id": version["artifact_id"]}
                current = c.execute("SELECT revision,body FROM current WHERE id=? AND kind='editor_draft'", ("editor-main",)).fetchone()
                if not current or current[0] != expected:
                    raise Conflict("编辑稿版本不匹配，请先保存并重新载入")
                persisted = json.loads(current[1])["document"]
                if persisted != document:
                    raise Conflict("版本文档必须与已保存编辑稿一致")
                aid, vid = uid(), uid()
                target = _target(store.data_dir, aid, ".pdf")
                _atomic_write(target, raw)
                written = target
                meta = {"path": str(target.relative_to(Path(store.data_dir).resolve())), "sha256": hashlib.sha256(raw).hexdigest(), "media_type": "application/pdf", "size": len(raw)}
                created = now()
                artifact = dict(meta, id=aid, version_id=vid, created_at=created)
                version = {"id": vid, "name": name.strip(), "createdAt": created, "document": document, "artifact_id": aid, "idempotency_key": key.strip(), "request_fingerprint": fingerprint}
                store._record(c, "artifact", artifact)
                store._record(c, "editor_version", version)
                return {"id": vid, "name": version["name"], "createdAt": created, "document": document, "artifact_id": aid}
        except Exception:
            if written is not None:
                try: written.unlink()
                except OSError: pass
            raise

    @router.get("/versions/{version_id}")
    def get_version(version_id: str):
        with store.connect(False) as c:
            row = c.execute("SELECT body FROM records WHERE id=? AND kind='editor_version'", (version_id,)).fetchone()
            if not row:
                raise Missing("版本不存在")
            v = json.loads(row[0])
            return {"id": v["id"], "name": v["name"], "createdAt": v["createdAt"], "document": v["document"], "artifact_id": v["artifact_id"]}

    @router.delete("/versions/{version_id}")
    def delete_version(version_id: str):
        if not isinstance(version_id, str) or not _ID.fullmatch(version_id):
            raise Invalid("version_id 不合法")
        artifact_path = None
        with store.connect() as c:
            row = c.execute("SELECT body FROM records WHERE id=? AND kind='editor_version'", (version_id,)).fetchone()
            if not row:
                raise Missing("版本不存在")
            version = json.loads(row[0])
            application = c.execute("SELECT 1 FROM applications WHERE version_id=? LIMIT 1", (version_id,)).fetchone()
            if application:
                raise Conflict("该版本已经用于投递，不能删除")
            use = c.execute(
                "SELECT 1 FROM records WHERE kind='resume_use' AND json_extract(body,'$.version_id')=? LIMIT 1",
                (version_id,),
            ).fetchone()
            if use:
                raise Conflict("该版本已经关联岗位或方向，不能删除")
            artifact_id = version.get("artifact_id")
            artifact_row = c.execute("SELECT body FROM records WHERE id=? AND kind='artifact'", (artifact_id,)).fetchone()
            if artifact_row:
                artifact = json.loads(artifact_row[0])
                if isinstance(artifact.get("path"), str):
                    artifact_path = read_artifact(store.data_dir, artifact["path"])
                c.execute("DELETE FROM records WHERE id=? AND kind='artifact'", (artifact_id,))
            c.execute("DELETE FROM records WHERE id=? AND kind='editor_version'", (version_id,))
        if artifact_path is not None:
            artifact_path.unlink(missing_ok=True)
        return {"deleted": version_id}

    @router.post("/restore")
    def restore(body: dict):
        version_id, expected = body.get("version_id"), body.get("expected_revision")
        if not isinstance(version_id, str) or not _ID.fullmatch(version_id):
            raise Invalid("version_id 不合法")
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
            raise Invalid("expected_revision 不合法")
        with store.connect() as c:
            row = c.execute("SELECT body FROM records WHERE id=? AND kind='editor_version'", (version_id,)).fetchone()
            if not row: raise Missing("版本不存在")
            version = json.loads(row[0])
            current = c.execute("SELECT revision,body FROM current WHERE id=?", ("editor-main",)).fetchone()
            revision = current[0] if current else 0
            if expected != revision: raise Conflict("编辑稿已更新，请重新载入后恢复")
            saved_at = now(); new_revision = revision + 1
            obj = {"id":"editor-main", "document":version["document"], "savedAt":saved_at}
            c.execute("INSERT INTO current VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,revision=excluded.revision,body=excluded.body", ("editor-main", "editor_draft", new_revision, dump(obj)))
            c.execute("INSERT INTO revisions VALUES(?,?,?,?)", ("editor-main", new_revision, dump(obj), saved_at))
            before = json.loads(current[1])["document"] if current else _blank()
            recovery = {"id":uid(), "version_id":version_id, "revision":new_revision, "previous_revision":revision, "createdAt":saved_at, "before":before, "document":version["document"]}
            store._record(c, "editor_recovery", recovery)
            return _result(version["document"], new_revision, saved_at)

    return router
