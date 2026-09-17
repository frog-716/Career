"""One profile owner: structured identity, explicit archival of legacy mixed text."""
from fastapi import APIRouter
from urllib.parse import urlsplit
from .core import Conflict, Invalid, digest, now, uid
from .knowledge import _entry_values, _expected, _request, _remember
from .editor import sync_profile_to_draft


def _web_url(value):
    if not isinstance(value, str) or len(value) > 2000:
        raise Invalid('网页链接格式或长度不合法')
    value = value.strip()
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username and not parsed.password
    except ValueError:
        valid = False
    if not valid or any(ch.isspace() for ch in value): raise Invalid('请填写完整的 http:// 或 https:// 网页链接')
    return value


def _basics(value):
    if not isinstance(value, dict) or not {'name','phone','email'} <= set(value) or set(value) - {'name','phone','email','wechat','github','links'}:
        raise Invalid('基础资料字段不合法')
    result = {}
    for k in ('name','phone','email','wechat','github'):
        if k not in value: continue
        if not isinstance(value[k], str) or len(value[k]) > 500: raise Invalid('基础字段超出长度限制')
        result[k] = value[k].strip()
    if result.get('github'): result['github'] = _web_url(result['github'])
    if 'links' in value:
        links = value['links']
        if not isinstance(links, list) or len(links) > 10: raise Invalid('个人网页最多10条')
        result['links'] = []
        for link in links:
            if not isinstance(link, dict) or set(link) != {'label','url'} or not isinstance(link['label'],str) or len(link['label']) > 100:
                raise Invalid('网页名称或链接格式不合法')
            result['links'].append(dict(label=link['label'].strip(), url=_web_url(link['url'])))
    return result


def _save(store, c, old, basics, expected):
    basics = {**old.get('basics', {}), **basics}
    content = '\n'.join(label + '：' + basics[k] for k, label in [('name','姓名'),('phone','电话'),('email','邮箱'),('wechat','微信'),('github','GitHub')] if basics.get(k))
    content += ''.join('\n' + (link['label'] or '个人网页') + '：' + link['url'] for link in basics.get('links', []))
    result = store._save(c, 'profile', dict(old, mode='structured', basics=basics, content=content,
                                           verified=False, source='user-edit'), expected)
    store._bump(c)
    sync_profile_to_draft(c, store, result)
    return result


def profile_router(store):
    router = APIRouter(prefix='/api/profile')

    @router.post('/basics')
    def save_basics(body: dict):
        basics = _basics(body.get('basics')); expected = _expected(body.get('expected_revision'))
        with store.connect() as c:
            old = store._get(c, 'profile', 'profile')
            if old.get('mode') != 'structured' and old['content'].strip():
                raise Conflict('旧基础资料包含自由文本，请先明确整理，原文会完整保留')
            return _save(store, c, old, basics, expected)

    @router.post('/organize')
    def organize(body: dict):
        basics = _basics(body.get('basics')); expected = _expected(body.get('expected_revision'))
        if body.get('confirmed') is not True: raise Invalid('请确认已核对原文及整理后的资料边界')
        entries = body.get('entries', [])
        if not isinstance(entries, list) or len(entries) > 30: raise Invalid('一次最多整理30条候选')
        values = []
        for e in entries:
            if not isinstance(e, dict): raise Invalid('候选结构不合法')
            values.append(_entry_values(e))
        with store.connect() as c:
            previous, key, fingerprint = _request(store, c, body.get('idempotency_key'), 'organize_profile', body)
            if previous is not None: return previous
            old = store._get(c, 'profile', 'profile')
            if old['revision'] != expected: raise Conflict('资料已更新，请核对当前版本再整理')
            if old.get('mode') == 'structured': raise Conflict('基础资料已经整理，请直接编辑基础字段')
            source = dict(id=uid(), title='整理前的基础资料', content=old['content'], source_type='text', locator='',
                          scope_type='personal', scope_id='', created_at=now(),
                          origin=dict(kind='profile', id='profile', revision=old['revision'], hash=digest(old)))
            store._record(c, 'knowledge_source', source)
            for kind, title, content in values:
                store._save(c, 'knowledge_candidate', dict(id=uid(), title=title, content=content,
                    entry_type=kind, scope_type='personal', scope_id='', source_ids=[source['id']],
                    status='pending', entry_id=None, created_at=now()), 0)
            result = _save(store, c, old, basics, expected)
            _remember(store, c, key, fingerprint, result)
            return result

    return router
