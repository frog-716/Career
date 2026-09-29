"""Purpose-built Resume AI context; stored documents never cross this boundary."""
from copy import deepcopy

from .core import Invalid

PROFILE_FIELDS = ('name', 'contacts', 'phone', 'email', 'wechat', 'address', 'github', 'links')
ITEM_FIELDS = {
    'skills': ('id', 'content'),
    'experience': ('id', 'organization', 'role', 'date'),
    'projects': ('id', 'title', 'responsibility', 'date'),
    'education': ('id', 'school', 'major', 'date'),
}
RESEARCH_FIELDS = ('id', 'category', 'classification', 'content', 'evidence_status', 'status')


def _invalid():
    raise Invalid('Resume AI Context DTO 不符合字段白名单')


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        _invalid()


def _texts(value, fields):
    if not isinstance(value, dict):
        _invalid()
    result = {}
    for field in fields:
        text = value.get(field)
        if not isinstance(text, str):
            _invalid()
        result[field] = text
    return result


def _sections(sections):
    if not isinstance(sections, list):
        _invalid()
    result = []
    for section in sections:
        clean = _texts(section, ('id', 'type', 'title'))
        kind = clean['type']
        if kind not in ITEM_FIELDS or not isinstance(section.get('items'), list):
            _invalid()
        clean['items'] = []
        for item in section['items']:
            projected = _texts(item, ITEM_FIELDS[kind])
            if kind != 'skills':
                if not isinstance(item.get('bullets'), list):
                    _invalid()
                projected['bullets'] = [_texts(bullet, ('id', 'content')) for bullet in item['bullets']]
            clean['items'].append(projected)
        result.append(clean)
    return result


def resume_document_context(document):
    """Start empty; Profile contributes existence and fixed field names only."""
    if not isinstance(document, dict) or document.get('schemaVersion') != 1:
        _invalid()
    profile = document.get('profile')
    result = {'schemaVersion': 1}
    result['profile'] = {
        'present': isinstance(profile, dict),
        'fields': [field for field in PROFILE_FIELDS if isinstance(profile, dict) and field in profile],
    }
    result['sections'] = _sections(document.get('sections'))
    return result


def research_context(items):
    """Keep current research statements, never arbitrary stored metadata."""
    if not isinstance(items, list):
        _invalid()
    return [_texts(item, RESEARCH_FIELDS) for item in items]


def _validate_document(document):
    _keys(document, ('schemaVersion', 'profile', 'sections'))
    if type(document['schemaVersion']) is not int or document['schemaVersion'] != 1:
        _invalid()
    profile = document['profile']
    _keys(profile, ('present', 'fields'))
    fields = profile['fields']
    if type(profile['present']) is not bool or not isinstance(fields, list):
        _invalid()
    if any(not isinstance(field, str) or field not in PROFILE_FIELDS for field in fields):
        _invalid()
    if fields != [field for field in PROFILE_FIELDS if field in fields] or (not profile['present'] and fields):
        _invalid()
    if _sections(document['sections']) != document['sections']:
        _invalid()


def _validate_manifest(manifest):
    _keys(manifest, ('manifest_version', 'task_type', 'target', 'target_revision', 'dependencies', 'policy_version'))
    if manifest['manifest_version'] != 1 or manifest['task_type'] != 'resume_optimization' or type(manifest['target_revision']) is not int:
        _invalid()
    _texts(manifest, ('policy_version',))
    _keys(manifest['target'], ('kind', 'id', 'opportunity_id'))
    _texts(manifest['target'], ('kind', 'id', 'opportunity_id'))
    if manifest['target']['kind'] != 'resume_document' or not isinstance(manifest['dependencies'], list):
        _invalid()
    for dependency in manifest['dependencies']:
        _keys(dependency, ('kind', 'id', 'revision', 'content_hash', 'purpose'), ('owner_id', 'expected_absent'))
        _texts(dependency, ('kind', 'id', 'purpose'))
        if dependency['kind'] not in {'opportunity', 'resume_document', 'company_research', 'opportunity_research', 'wiki_knowledge', 'work_project', 'employment', 'raw_material', 'work_evidence'}:
            _invalid()
        if dependency['revision'] is not None and type(dependency['revision']) is not int:
            _invalid()
        if dependency['content_hash'] is not None and not isinstance(dependency['content_hash'], str):
            _invalid()
        if 'owner_id' in dependency and not isinstance(dependency['owner_id'], str):
            _invalid()
        if 'expected_absent' in dependency and type(dependency['expected_absent']) is not bool:
            _invalid()


def validate_packet(packet):
    """Fail closed on extensions, including on re-entry after preparation."""
    constants = {
        'schemaVersion': 1, 'task_type': 'resume_optimization',
        'required_context': ['opportunity', 'current_resume_document'],
        'optional_context': ['company_research', 'opportunity_research', 'career_project', 'career_employment', 'career_wiki', 'career_evidence'],
        'forbidden_context': ['other_opportunities', 'other_resume_documents', 'feedback', 'full_raw_archive'],
        'allowed_patch_targets': ['current_resume_document'],
        'confirmation_required': True, 'output_schema_version': 2,
    }
    _keys(packet, (*constants, 'instruction', 'target', 'sources', 'manifest'), ('policy_version', 'budget_used'))
    if any(packet[key] != value for key, value in constants.items()):
        _invalid()
    _texts(packet, ('instruction',))
    _keys(packet['target'], ('opportunity_id', 'resume_document_id'))
    _texts(packet['target'], ('opportunity_id', 'resume_document_id'))
    _validate_manifest(packet['manifest'])
    target = packet['target']
    manifest_target = packet['manifest']['target']
    if manifest_target['id'] != target['resume_document_id'] or manifest_target['opportunity_id'] != target['opportunity_id']:
        _invalid()
    sources = packet['sources']
    if not isinstance(sources, list) or not 2 <= len(sources) <= 22:
        _invalid()
    purposes = set()
    wiki_ids = set()
    wiki_refs = set()
    evidence = []
    for source in sources:
        _keys(source, ('id', 'revision', 'purpose', 'selected_content'))
        _texts(source, ('id', 'purpose'))
        if type(source['revision']) is not int or (source['purpose'] in purposes and source['purpose'] not in {'career_wiki', 'career_project', 'career_employment'}):
            _invalid()
        purpose = source['purpose']
        purposes.add(purpose)
        content = source['selected_content']
        if purpose == 'opportunity':
            if source['id'] != target['opportunity_id']:
                _invalid()
            _keys(content, ('company', 'title', 'jd'))
            _texts(content, ('company', 'title', 'jd'))
        elif purpose == 'current_resume_document':
            if source['id'] != target['resume_document_id']:
                _invalid()
            _validate_document(content)
        elif purpose in {'company_research', 'opportunity_research'}:
            if research_context(content) != content:
                _invalid()
        elif purpose == 'career_wiki':
            _keys(content, ('scope_type', 'scope_id', 'knowledge_type', 'content', 'source_refs'))
            _texts(content, ('scope_type', 'scope_id', 'knowledge_type', 'content'))
            if content['scope_type'] not in {'personal', 'cognition', 'project', 'employment', 'opportunity'}:
                _invalid()
            if content['scope_type'] == 'opportunity' and content['scope_id'] != target['opportunity_id']:
                _invalid()
            if content['knowledge_type'] not in {'fact', 'observation', 'hypothesis'}:
                _invalid()
            refs = content['source_refs']
            if not isinstance(refs, list) or len(refs) > 20:
                _invalid()
            for ref in refs:
                _keys(ref, ('kind', 'id', 'revision', 'hash'))
                _texts(ref, ('kind', 'id', 'hash'))
                if type(ref['revision']) is not int:
                    _invalid()
                wiki_refs.add((ref['kind'], ref['id'], ref['revision'], ref['hash']))
            if source['id'] in wiki_ids:
                _invalid()
            wiki_ids.add(source['id'])
        elif purpose == 'career_project':
            _keys(content, ('name', 'tags', 'status'))
            _texts(content, ('name', 'status'))
            if not isinstance(content['tags'], list) or any(not isinstance(tag, str) for tag in content['tags']):
                _invalid()
        elif purpose == 'career_employment':
            _keys(content, ('company', 'role', 'start_date', 'end_date'))
            _texts(content, ('company', 'role', 'start_date', 'end_date'))
        elif purpose == 'career_evidence':
            _keys(content, ('source_kind', 'title', 'content'))
            _texts(content, ('source_kind', 'title', 'content'))
            if len(content['content']) > 3000 or len(content['title']) > 200:
                _invalid()
            evidence.append(source)
        else:
            _invalid()
    if len(wiki_ids) > 8:
        _invalid()
    if len(evidence) > 2:
        _invalid()
    dependencies = packet['manifest']['dependencies']
    for source in evidence:
        if not any(
            kind in {'raw_material', 'work_evidence'} and identifier == source['id']
            and revision == source['revision']
            and any(
                dependency['kind'] == kind and dependency['id'] == identifier
                and dependency['revision'] == revision
                and dependency['content_hash'] == content_hash
                and dependency['purpose'] == 'career_evidence'
                for dependency in dependencies
            )
            for kind, identifier, revision, content_hash in wiki_refs
        ):
            _invalid()
    if not {'opportunity', 'current_resume_document'} <= purposes:
        _invalid()
    if 'policy_version' in packet:
        _texts(packet, ('policy_version',))
    if 'budget_used' in packet:
        _keys(packet['budget_used'], ('source_count', 'content_chars'))
        if any(type(value) is not int for value in packet['budget_used'].values()):
            _invalid()
    return deepcopy(packet)
