"""Business identities and explicit references, independent of pages and AI claims."""
import json
from fastapi import APIRouter
from .core import Invalid, Conflict, required, uid, now, digest

KINDS={'company','org_unit','search_cycle','target_role'}


def expected(body):
    v=body.get('expected_revision')
    if type(v) is not int or v<0:raise Invalid('expected_revision 不合法')
    return v


def domain_router(store):
    router=APIRouter(prefix='/api/domain')

    def ref(c,id,kind):
        if not id:return None
        if not isinstance(id,str):raise Invalid('关联标识不合法')
        return store._get(c,id,'domain_'+kind)

    def replay(c,key,body):
        if not isinstance(key,str):raise Invalid('请求标识不能为空')
        key=required(key,'请求标识',200)
        rows=c.execute("SELECT body FROM records WHERE kind='domain_command' AND json_extract(body,'$.key')=?",(key,)).fetchall()
        if rows:
            old=json.loads(rows[0][0])
            if old['fingerprint']!=digest(body):raise Conflict('请求标识已用于不同操作')
            return old['result']

    def remember(c,key,body,result):
        store._record(c,'domain_command',dict(id=uid(),key=key,fingerprint=digest(body),result=result))
        return result

    @router.get('')
    def read():
        with store.connect(False) as c:
            return dict(objects=[o for k in sorted(KINDS) for o in store._current(c,'domain_'+k)],
                        opportunities=store._current(c,'opportunity_context'),resume_uses=store._records(c,'resume_use'))

    def save(body,id=None):
        with store.connect() as c:
            if not id:
                cached=replay(c,body.get('idempotency_key'),body)
                if cached:return cached
            kind=body.get('kind')
            if not isinstance(kind,str) or kind not in KINDS:raise Invalid('对象类型不支持')
            old=store._get(c,id,'domain_'+kind) if id else {}
            name=required(body.get('name'),'名称',500)
            description=body.get('description','')
            if not isinstance(description,str) or len(description)>10000:raise Invalid('说明过长')
            oid=id or uid()
            obj=dict(old,id=oid,kind=kind,name=name,description=description,created_at=old.get('created_at',now()))
            if kind=='org_unit':
                company=ref(c,body.get('company_id'),'company')
                if not company:raise Invalid('组织必须归属公司')
                if old and company['id']!=old['company_id']:raise Invalid('组织公司不能直接迁移，请新建组织后重新关联')
                parent=ref(c,body.get('parent_id'),'org_unit')
                seen={oid}
                while parent:
                    if parent['id'] in seen:raise Invalid('组织层级不能形成循环')
                    if parent['company_id']!=company['id']:raise Invalid('父组织属于另一家公司')
                    seen.add(parent['id']);parent=ref(c,parent.get('parent_id'),'org_unit')
                obj.update(company_id=company['id'],parent_id=body.get('parent_id') or None)
            result=store._save(c,'domain_'+kind,obj,expected(body) if id else 0)
            store._bump(c)
            return result if id else remember(c,body['idempotency_key'],body,result)

    @router.post('/objects')
    def create(body:dict):return save(body)

    @router.post('/objects/{id}')
    def update(id:str,body:dict):return save(body,id)

    @router.post('/opportunities/{job_id}')
    def assign(job_id:str,body:dict):
        with store.connect() as c:
            if job_id.startswith('opportunity:'):
                opportunity=store._get(c,job_id,'opportunity')
                job_id=opportunity['legacy_job_id']
            store._get(c,job_id,'job')
            company=ref(c,body.get('company_id'),'company');org=ref(c,body.get('org_unit_id'),'org_unit')
            if org and (not company or org['company_id']!=company['id']):raise Invalid('组织必须属于选中的公司')
            role=ref(c,body.get('target_role_id'),'target_role');cycle=ref(c,body.get('search_cycle_id'),'search_cycle')
            obj=dict(id='opportunity-context:'+job_id,job_id=job_id,company_id=company['id'] if company else None,
                     org_unit_id=org['id'] if org else None,target_role_id=role['id'] if role else None,search_cycle_id=cycle['id'] if cycle else None)
            result=store._save(c,'opportunity_context',obj,expected(body))
            store._bump(c)
            return result

    @router.post('/resume-uses')
    def use(body:dict):
        with store.connect() as c:
            cached=replay(c,body.get('idempotency_key'),body)
            if cached:return cached
            scope=body.get('scope_type');scope_id=required(body.get('scope_id'),'引用目标',500)
            if scope=='role':target=store._get(c,scope_id,'domain_target_role');name=target['name']
            elif scope in {'job','opportunity'}:
                if scope=='job':
                    target=store._get(c,scope_id,'job');scope_id='opportunity:'+scope_id
                else:target=store._get(c,scope_id,'opportunity')
                scope='opportunity';name=target['company']+' · '+target['title']
            else:raise Invalid('简历用途只能是方向通用版或具体机会')
            v=store._get(c,required(body.get('version_id'),'版本',500),'editor_version',True)
            a=store._get(c,v['artifact_id'],'artifact',True)
            obj=dict(id=uid(),scope_type=scope,scope_id=scope_id,target_name=name,version_id=v['id'],version_name=v['name'],
                     artifact_id=v['artifact_id'],artifact_hash=a['sha256'],created_at=now())
            store._record(c,'resume_use',obj)
            return remember(c,body['idempotency_key'],body,obj)
    return router
