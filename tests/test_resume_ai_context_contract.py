"""The outbound gateway rejects extensions to the purpose-built Resume DTO."""
from copy import deepcopy
import pytest
from workbench.core import Invalid
from workbench.resume_documents import _resume_ai_packet
from workbench.outbound_policy import sanitize_packet
from test_record_submitted import client_at, opportunity, start


def test_profile_projection_happens_before_outbound_policy(tmp_path):
    client, store = client_at(tmp_path)
    owner = opportunity(client, 'DTO 构造边界')
    draft = start(client, owner)
    draft['document']['profile']['name'] = 'PROFILE_VALUE_MUST_NOT_ENTER_PACKET'
    draft['document']['profile']['unknown'] = {'nested': 'UNKNOWN_PROFILE_VALUE'}
    with store.connect(False) as conn:
        packet = _resume_ai_packet(store, conn, draft, '只优化表达')
    current = next(s['selected_content'] for s in packet['sources'] if s['purpose']=='current_resume_document')
    assert current['profile'] == {'present': True, 'fields': ['name', 'contacts']}
    assert 'meta' not in current and 'formatting' not in current
    clean = sanitize_packet('resume_optimization', packet)
    assert sanitize_packet('resume_optimization', clean) == clean
    for target in ['packet', 'source', 'profile', 'manifest']:
        bad = deepcopy(clean)
        holder = {'packet':bad,'source':bad['sources'][0],
                  'profile':bad['sources'][1]['selected_content']['profile'],
                  'manifest':bad['manifest']}[target]
        holder['unknown_payload'] = {'name':'UNSAFE_CONTACT'}
        with pytest.raises(Invalid):
            sanitize_packet('resume_optimization', bad)
