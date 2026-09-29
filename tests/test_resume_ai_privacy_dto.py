"""Resume AI sends an explicit DTO, never the editable document's arbitrary fields."""
from copy import deepcopy
import json

import pytest

from test_t08_resume_suggestions import resume_fixture
from workbench import research_store
from workbench.providers import TestProvider
from workbench.model_gateway import ModelGateway, OpenAICompatibleAdapter
from workbench.runtime_mode import resolve_runtime_mode


class CaptureResumeProvider(TestProvider):
    def __init__(self):
        super().__init__()
        self.payloads = []

    def complete(self, payload):
        # This is the actual dispatch boundary; no context construction is mocked.
        self.payloads.append(deepcopy(payload))
        return {'changes': [], 'suggestions': [], 'claims': []}


def post(client, path, body):
    response = client.post('/api' + path, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def seed_research(store, opportunity, scope, marker, *, hostile=False):
    kind = 'company_research' if scope == 'company' else 'opportunity_research'
    owner = opportunity['company_id'] if scope == 'company' else opportunity['id']
    item = {'id': 'privacy-research-' + scope, 'category': 'role',
            'classification': 'fact', 'content': marker, 'status': 'active',
            'evidence_status': 'unknown'}
    if hostile:
        # Stored legacy/future fields must not become outbound fields by accident.
        item.update(source_refs=[{'private_reference': 'PRIVATE_RESEARCH_REFERENCE'}],
                    private_research_extra={'nested': 'PRIVATE_RESEARCH_EXTRA'},
                    verification={'user_confirmed': False, 'independently_verified': False},
                    updated_at='PRIVATE_RESEARCH_DATE')
    with store.connect() as connection:
        research_store.save(store, connection, kind, owner, {'items': [item]}, 0)


@pytest.mark.parametrize('transport', ['test-provider', 'openai-compatible-adapter'])
@pytest.mark.parametrize('person_name', ['虚构隐私姓名赵岚', 'Synthetic Person Eleanor Privacy'])
def test_preview_and_dispatched_payload_exclude_profile_and_unknown_nested_values(tmp_path, monkeypatch, person_name, transport):
    provider = CaptureResumeProvider()
    client, store, current = resume_fixture(tmp_path, provider)
    opportunity = client.get('/api/opportunities/' + current['opportunity_id']).json()
    document = deepcopy(current['document'])
    private_values = [person_name, 'PRIVATE_PROFILE_ID', '13800138077', '13900139088',
                      'tagged-private@example.test', 'bare-private@example.test',
                      'PRIVATE_WECHAT_TAGGED', 'PRIVATE_WECHAT_BARE',
                      '虚构隐私地址云杉路七十七号', 'PRIVATE_CONTACT_NAME',
                      'PRIVATE_CONTACT_ID', 'https://private-contact.example.test/me',
                      'PRIVATE_PROFILE_NESTED', 'PRIVATE_UNKNOWN_PAYLOAD']
    document['profile'] = {
        'id': 'PRIVATE_PROFILE_ID', 'name': person_name,
        'contacts': [
            {'id': 'PRIVATE_CONTACT_ID', 'kind': 'identity', 'content': 'phone：13800138077', 'href': ''},
            {'id': 'private-bare-phone', 'kind': 'identity', 'content': '13900139088', 'href': ''},
            {'id': 'private-tagged-email', 'kind': 'identity', 'content': 'email：tagged-private@example.test', 'href': ''},
            {'id': 'private-bare-email', 'kind': 'identity', 'content': 'bare-private@example.test', 'href': ''},
            {'id': 'private-tagged-wechat', 'kind': 'identity', 'content': 'WeChat：PRIVATE_WECHAT_TAGGED', 'href': ''},
            {'id': 'private-bare-wechat', 'kind': 'identity', 'content': 'PRIVATE_WECHAT_BARE', 'href': ''},
            {'id': 'private-cn-wechat', 'kind': 'identity', 'content': '微信：PRIVATE_WECHAT_TAGGED', 'href': ''},
            {'id': 'private-address', 'kind': 'identity', 'content': '虚构隐私地址云杉路七十七号', 'href': ''},
            {'id': 'private-link', 'kind': 'link', 'content': '个人网页',
             'href': 'https://private-contact.example.test/me', 'name': 'PRIVATE_CONTACT_NAME',
             'unknown_contact': {'nested': 'PRIVATE_PROFILE_NESTED'}},
        ],
        'phone': '13900139088', 'email': 'bare-private@example.test',
        'wechat': 'PRIVATE_WECHAT_BARE', 'address': '虚构隐私地址云杉路七十七号',
        'github': 'https://private-contact.example.test/me',
        'links': [{'url': 'https://private-contact.example.test/me'}],
        'unknown_profile': {'nested': ['PRIVATE_PROFILE_NESTED']},
        'PRIVATE_MALICIOUS_FIELD_微信': {'value': 'PRIVATE_UNKNOWN_PAYLOAD'},
    }
    unknown = {'nested': [{'phone': 'PRIVATE_UNKNOWN_PAYLOAD'}]}
    document['PRIVATE_MALICIOUS_FIELD_document'] = deepcopy(unknown)
    document['formatting']['PRIVATE_MALICIOUS_FIELD_formatting'] = deepcopy(unknown)
    document['meta']['PRIVATE_MALICIOUS_FIELD_meta'] = deepcopy(unknown)
    for section in document['sections']:
        section['PRIVATE_MALICIOUS_FIELD_section'] = deepcopy(unknown)
        for item in section['items']:
            item['PRIVATE_MALICIOUS_FIELD_item'] = deepcopy(unknown)
            for bullet in item.get('bullets', []):
                bullet['PRIVATE_MALICIOUS_FIELD_bullet'] = deepcopy(unknown)
    saved = client.put('/api/resume-documents/' + current['document_id'], json={
        'document': document, 'expected_revision': current['revision'],
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()['document']['PRIVATE_MALICIOUS_FIELD_document'] == unknown
    seed_research(store, opportunity, 'company', 'ALLOWED_COMPANY_RESEARCH', hostile=True)
    seed_research(store, opportunity, 'opportunity', 'ALLOWED_OPPORTUNITY_RESEARCH', hostile=True)

    other = post(client, '/opportunities', {'company_name': 'OTHER_PRIVATE_COMPANY',
        'title': 'OTHER_PRIVATE_ROLE', 'jd': 'OTHER_PRIVATE_JD', 'idempotency_key': 'other-opportunity'})
    other_resume = post(client, f"/opportunities/{other['id']}/resume/start", {
        'source': {'kind': 'blank'}, 'expected_opportunity_revision': other['revision'],
        'idempotency_key': 'other-resume'})
    other_doc = deepcopy(other_resume['document'])
    other_doc['sections'] = [{'id': 'other-private-section', 'type': 'skills', 'title': 'OTHER_PRIVATE_RESUME',
                             'items': [{'id': 'other-private-skill', 'content': 'OTHER_PRIVATE_SKILL'}]}]
    assert client.put('/api/resume-documents/' + other_resume['document_id'], json={
        'document': other_doc, 'expected_revision': other_resume['revision'],
    }).status_code == 200
    seed_research(store, other, 'opportunity', 'OTHER_PRIVATE_RESEARCH')
    seed_research(store, other, 'company', 'OTHER_PRIVATE_COMPANY_RESEARCH')

    if transport == 'openai-compatible-adapter':
        config = {'id': 'synthetic-model', 'provider': 'deepseek',
                  'base_url': 'https://provider.example.test', 'model': 'synthetic-model'}
        adapter = OpenAICompatibleAdapter(config, 'synthetic-key', runtime_mode=resolve_runtime_mode('AI_ENABLED'))
        # Capture the final real-adapter request instead of opening any connection.
        monkeypatch.setattr(adapter, '_request', provider.complete)
        monkeypatch.setattr(ModelGateway, '_provider', lambda self, connection, model_config_id=None: (adapter, config))

    seed = {'instruction': '只优化当前虚构简历表达', 'idempotency_key': 'privacy-payload'}
    path = '/api/resume-documents/' + current['document_id'] + '/ai-suggest'
    response = client.post(path, json=seed)
    assert response.status_code == 409, response.text
    preparation = response.json()
    assert preparation['status'] == 'context_confirmation_required'
    assert provider.payloads == [], 'Preview 不得调用 Provider'
    executed = client.post(path, json={**seed, 'prepared_id': preparation['prepared_id'],
        'payload_hash': preparation['payload_hash'], 'confirm_outbound': True})
    assert executed.status_code == 200, executed.text
    assert len(provider.payloads) == 1
    assert preparation['payload_preview'] == provider.payloads[0], '确认的 Preview 必须与实际 Provider-ready payload 相同'

    for payload in (preparation['payload_preview'], provider.payloads[0]):
        encoded = json.dumps(payload, ensure_ascii=False)
        for private in private_values:
            assert private not in encoded, f'Privacy value leaked: {private}'
        for marker in ['PRIVATE_MALICIOUS_FIELD_', 'unknown_profile', 'unknown_contact',
                       'PRIVATE_RESEARCH_REFERENCE', 'PRIVATE_RESEARCH_EXTRA', 'PRIVATE_RESEARCH_DATE',
                       'OTHER_PRIVATE_', 'other-private-section', 'other-private-skill']:
            assert marker not in encoded, f'Unknown or other-owner material leaked: {marker}'
        packet = json.loads(payload['messages'][1]['content'])
        sources = {source['purpose']: source for source in packet['sources']}
        resume = sources['current_resume_document']['selected_content']
        assert set(resume) == {'schemaVersion', 'profile', 'sections'}
        assert resume['schemaVersion'] == 1
        assert set(resume['profile']) == {'present', 'fields'}
        assert resume['profile']['present'] is True
        assert isinstance(resume['profile']['fields'], list)
        assert set(resume['profile']['fields']) == {'name', 'contacts', 'phone', 'email', 'wechat', 'address', 'github', 'links'}
        assert 'name' in resume['profile']['fields']
        assert sources['opportunity']['id'] == opportunity['id']
        assert sources['current_resume_document']['id'] == current['document_id']
        assert 'Python' in json.dumps(resume, ensure_ascii=False)
        assert '维护内部工具' in json.dumps(resume, ensure_ascii=False)
        assert 't08-skill' in json.dumps(resume) and 't08-bullet' in json.dumps(resume)
        allowed_item = {'skills': {'id', 'content'}, 'experience': {'id', 'organization', 'role', 'date', 'bullets'},
                        'projects': {'id', 'title', 'responsibility', 'date', 'bullets'},
                        'education': {'id', 'school', 'major', 'date', 'bullets'}}
        for section in resume['sections']:
            assert set(section) == {'id', 'type', 'title', 'items'}
            for item in section['items']:
                assert set(item) == allowed_item[section['type']]
                for bullet in item.get('bullets', []):
                    assert set(bullet) == {'id', 'content'}
        for purpose, marker in [('company_research', 'ALLOWED_COMPANY_RESEARCH'),
                                ('opportunity_research', 'ALLOWED_OPPORTUNITY_RESEARCH')]:
            items = sources[purpose]['selected_content']
            assert items[0]['content'] == marker
            assert set(items[0]) == {'id', 'category', 'classification', 'content', 'evidence_status', 'status'}
    assert client.get('/api/resume-documents/' + current['document_id']).json() == saved.json(), '构造出站DTO不得改写工作稿'
