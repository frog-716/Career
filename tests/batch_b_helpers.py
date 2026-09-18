"""Synthetic compatibility fixtures, never a runtime write bypass."""
import json
import uuid
from workbench.core import digest, dump, now


def save_job(store,body,id=None):
    return store.save_job(dict(body,idempotency_key=str(uuid.uuid4())),id)


def historical_application(store,body):
    """Seed an already-frozen v1 row; subsequent calls test actual v2 replay."""
    with store.connect() as c:
        if c.execute('SELECT 1 FROM applications WHERE idempotency_key=?',(body['idempotency_key'],)).fetchone():
            existing=True
        else:
            existing=False
            job=store.job_view(c,body['job_id'])
            v=store._get(c,body['version_id'],record=True)
            a=store._get(c,body['artifact_id'],'artifact',True)
            oid=body.get('opportunity_id') or job['opportunity_id']
            obj=dict(id=str(uuid.uuid4()),job_id=job['id'],opportunity_id=oid,version_id=v['id'],artifact_id=a['id'],
                     applied_at=body['applied_at'],channel=body.get('channel',''),status=body.get('status','applied'),
                     version_kind='editor_version' if 'document' in v else 'version',created_at=now(),
                     status_history=[dict(status=body.get('status','applied'),changed_at=now(),source='created')],
                     request_fingerprint=digest([body.get('opportunity_id') or body['job_id'],v['id'],a['id'],body['applied_at'],body.get('channel',''),body.get('status','applied')]),
                     job_snapshot=job,resume_snapshot=v,artifact_snapshot=a,
                     opportunity_snapshot=dict(opportunity=store._get(c,oid,'opportunity'),job_posting=job))
            from batch_c_helpers import insert_legacy_application
            insert_legacy_application(c,(obj['id'],job['id'],v['id'],a['id'],body['idempotency_key'],dump(obj)))
    return store.record_application(body) if existing else obj
