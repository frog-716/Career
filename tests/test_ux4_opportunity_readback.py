"""Cold opportunity reads use its canonical owner and immutable submission."""
from test_record_submitted import client_at, opportunity, start, save, submit


def test_canonical_and_alias_reads_keep_frozen_material_scoped(tmp_path):
    c, _ = client_at(tmp_path)
    own = opportunity(c, '回读机会')
    other = opportunity(c, '其他机会')
    draft = save(c, start(c, own), '投递时虚构姓名')
    response = submit(c, own, dict(mode='draft', document_id=draft['document_id'], expected_document_revision=draft['revision']))
    assert response.status_code == 200, response.text
    frozen = response.json()['submission']
    assert submit(c, other, {'mode': 'none'}).status_code == 200
    pdf = c.get('/api/artifacts/' + frozen['artifact_id']).content
    save(c, draft, '投递后虚构姓名')
    for identifier in (own['id'], own['id'].split(':', 1)[1]):
        response = c.get('/api/state', params={'view': 'opportunity', 'job_id': identifier})
        assert response.status_code == 200
        assert response.json()['applications'] == [frozen]
    assert c.get('/api/artifacts/' + frozen['artifact_id']).content == pdf
    assert c.get('/api/state', params={'view': 'opportunity', 'job_id': 'opportunity:unknown'}).json()['applications'] == []
