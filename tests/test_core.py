import json
from pathlib import Path
import pytest
from workbench.core import Store, Conflict, Invalid
from workbench.providers import TestProvider

F = json.loads((Path(__file__).parents[1] / 'fixtures/scenarios.json').read_text())

@pytest.fixture
def store(tmp_path):
    return Store(tmp_path, TestProvider())

def setup(s):
    s.save_profile(F['candidate']['experience']['revision1'], 0)
    return s.save_job({k:F['job'][k] for k in ('company','title','jd')})

def test_current_payload_no_history_or_feedback(store):
    j=setup(store)
    store.feedback({'text':F['workEpisode']['chat'],'current_page':'feedback'})
    store.analyze(j['id'],'job','')
    store.save_profile(F['candidate']['experience']['revision2'],1)
    run=store.analyze(j['id'],'job','')
    payload=json.dumps(run['payload'],ensure_ascii=False)
    assert F['candidate']['experience']['revision1'] not in payload
    assert F['candidate']['experience']['revision2'] in payload
    assert F['workEpisode']['chat'] not in payload
    assert len(run['payload']['messages'])==2
    assert store.state()['runs'][-1]['status']=='stale'

def test_revision_race_and_patch_idempotence(store):
    j=setup(store)
    run=store.analyze(j['id'],'resume','')
    p=run['proposal']
    first=store.apply_proposal(p['id'])
    assert store.apply_proposal(p['id'])==first
    with pytest.raises(Conflict): store.save_profile('x',0)
    run2=store.analyze(j['id'],'resume','')
    store.save_resume(first['id'],F['candidate']['experience']['revision2'],first['revision'])
    with pytest.raises(Conflict):store.apply_proposal(run2['proposal']['id'])

def test_during_provider_update_stale(store):
    j=setup(store)
    original=store.provider.complete
    def change(payload):
        store.save_profile(F['candidate']['experience']['revision2'],1)
        return original(payload)
    store.provider.complete=change
    result=store.analyze(j['id'],'resume','')
    assert result['status']=='stale'
    assert result.get('proposal') is None

def test_immutable_application_pdf_restart_and_exclude(store):
    j=setup(store)
    r=store.open_resume(j['id'])
    r=store.save_resume(r['id'],F['historicalApplication']['usedResumeText'],r['revision'])
    v=store.save_version(r['id'],r['revision'])
    a=store.export_pdf(v['id'])
    body=dict(job_id=j['id'],version_id=v['id'],artifact_id=a['id'],applied_at='2026-09-14T10:00:00+08:00',status='applied',idempotency_key='fixture-event')
    event=store.record_application(body)
    assert store.record_application(body)==event
    store.save_resume(r['id'],F['candidate']['experience']['revision2'],r['revision'])
    store.save_job(dict(j,status='deleted',expected_revision=j['revision']),j['id'])
    new=Store(store.data_dir,TestProvider())
    state=new.state()
    assert state['applications'][0]==event
    assert state['versions'][0]['content']==F['historicalApplication']['usedResumeText']
    assert (store.data_dir/a['path']).read_bytes().startswith(b'%PDF')
    with pytest.raises(Invalid):new.context(j['id'],'job','')

def test_feedback_append_export_excluded_from_context(store):
    j=setup(store)
    f=store.feedback({'text':F['workEpisode']['workItem'],'current_page':'job','entity_id':j['id']})
    store.feedback_note(f['id'],F['workEpisode']['experiment'])
    saved=store.state()['feedback'][0]
    assert saved['text']==f['text'] and len(saved['notes'])==1
    assert f['text'] not in json.dumps(store.context(j['id'],'resume',''),ensure_ascii=False)

def test_preview_epoch_and_wrong_version_rejected(store):
    j=setup(store)
    packet=store.context(j['id'],'job','')
    store.save_profile(F['candidate']['experience']['revision2'],1)
    with pytest.raises(Conflict):store.analyze(j['id'],'job','',packet['epoch'])
    j2=store.save_job(dict(company=F['job']['company'],title=F['job']['title'],jd=F['adversarialMaterial']['text']))
    r=store.open_resume(j['id']); r=store.save_resume(r['id'],F['historicalApplication']['usedResumeText'],0)
    v=store.save_version(r['id'],1); a=store.export_pdf(v['id'])
    with pytest.raises(Invalid):store.record_application(dict(job_id=j2['id'],version_id=v['id'],artifact_id=a['id'],applied_at='2026-09-14T10:00:00Z',status='applied',idempotency_key='wrong'))

def test_analysis_idempotency_and_draft_stale(store):
    j=setup(store);calls=[];original=store.provider.complete
    def spy(payload):calls.append(payload);return original(payload)
    store.provider.complete=spy
    run=store.analyze(j['id'],'resume','',idempotency_key='fixture-run')
    replay=store.analyze(j['id'],'resume','',idempotency_key='fixture-run')
    assert run==replay and len(calls)==1
    r=store.open_resume(j['id']);store.save_resume(r['id'],F['candidate']['experience']['revision2'],0)
    assert store.state()['runs'][0]['status']=='stale'

def test_concurrent_pdf_exports_reuse_one_artifact(store):
    from concurrent.futures import ThreadPoolExecutor
    j=setup(store);r=store.open_resume(j['id']);r=store.save_resume(r['id'],F['historicalApplication']['usedResumeText'],0)
    v=store.save_version(r['id'],1)
    with ThreadPoolExecutor(max_workers=4) as pool:
        artifacts=list(pool.map(lambda _:store.export_pdf(v['id']),range(4)))
    assert len({a['id'] for a in artifacts})==1
    assert len(list((store.data_dir/'artifacts').glob('*.pdf')))==1

def test_feedback_original_whitespace_preserved(store):
    original='  '+F['workEpisode']['workItem']+'\n'
    f=store.feedback({'text':original,'current_page':'profile'})
    assert f['text']==original
    note='\n'+F['workEpisode']['experiment']+'  '
    assert store.feedback_note(f['id'],note)['notes'][0]['text']==note

def test_output_outside_sources_fails_without_writing_current(store):
    j=setup(store)
    before=store.state()['profile']
    store.provider.complete=lambda _: {'draft':F['historicalApplication']['usedResumeText'],'claims':[{'kind':'Fact','text':F['historicalApplication']['usedResumeText'],'source_ids':['archive-not-permitted']}]}
    with pytest.raises(Invalid):store.analyze(j['id'],'resume','')
    assert store.state()['profile']==before
    assert store.state()['resumes'][0]['content']==''
    assert store.state()['runs'][0]['status']=='failed'
