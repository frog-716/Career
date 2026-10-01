"""HTTP transport: browser calls services, never SQLite or arbitrary filesystem."""
import json
import os
import signal
import threading
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from .core import Store, Invalid, Conflict, Missing, ROOT, required
from .providers import ProviderError
from .artifacts import ArtifactError
from .editor import editor_router
from .profile import profile_router
from .journey import journey_router
from .domain import domain_router
from .knowledge import knowledge_router
from .wiki import raw_wiki_router, compiler_router
from .wiki.cognition import cognition_router
from .ai_activity import router as ai_activity_router
from .opportunity import router as opportunity_router
from .work import work_router
from .demo import demo_router
from .engagement import engagement_router
from .employment import employment_router
from .communication import router as communication_router
from .timeline import router as timeline_router
from .interview import router as interview_router
from .offer import router as offer_router
from .ai_config import create as create_ai_config, update as update_ai_config, delete as delete_ai_config, mark_cleanup_hold as mark_ai_cleanup_hold, set_default as set_ai_default, clear_default as clear_ai_default, settings as ai_settings, test_ephemeral as test_ai_ephemeral
from .model_gateway import ModelGateway
from .research import router as research_router
from . import research_search_config
from .local_runtime import LocalRuntimeManager, DEFAULT_BUILD_ID


def create_app(
    store=None, frontend_dir=None, *, runtime_dir=None,
    allow_retired_cognition_compiler=False, feishu_cli_path=None,
):
    app=FastAPI(title='Career',docs_url=None,redoc_url=None,openapi_url=None)
    s=store or Store();app.state.store=s

    def shutdown_store():
        s.shutdown()
    app.add_event_handler('shutdown', shutdown_store)

    runtime_root = Path(runtime_dir or os.environ.get('CAREER_RUNTIME_DIR') or (s.data_dir / '.runtime'))
    app.state.local_runtime = LocalRuntimeManager(
        runtime_root,
        data_dir=s.data_dir,
        build_id=os.environ.get('CAREER_BUILD_ID', DEFAULT_BUILD_ID),
        schema_version=6,
    )

    @app.middleware('http')
    async def local_only(request:Request,call_next):
        host=request.headers.get('host','')
        try:
            parsed_host = urlsplit('http://' + host)
            # Starlette versions before 1.0.1 could let malformed Host values
            # change request.url.path.  Reject such values before using any
            # host/path security decision, and validate the port eagerly.
            parsed_host.port
            hostname=parsed_host.hostname
        except ValueError:
            return JSONResponse({'detail':'不允许的本地 Host'},403)
        if (
            not host
            or any(char.isspace() for char in host)
            or parsed_host.username
            or parsed_host.password
            or parsed_host.path
            or parsed_host.query
            or parsed_host.fragment
        ):
            return JSONResponse({'detail':'不允许的本地 Host'},403)
        test_host = hostname == 'testserver' and os.environ.get('CAREER_TEST_MODE') == '1'
        if hostname not in ('localhost','127.0.0.1') and not test_host:
            return JSONResponse({'detail':'仅允许本地访问'},403)
        origin=request.headers.get('origin')
        if origin and origin not in ('http://'+host,'https://'+host):
            return JSONResponse({'detail':'不允许跨站访问本地资料'},403)
        if request.headers.get('sec-fetch-site')=='cross-site':
            return JSONResponse({'detail':'不允许跨站访问本地资料'},403)
        # Career does not need resumable local downloads.  Reject Range before
        # Starlette FileResponse/StaticFiles can enter their range parser.
        if request.headers.get('range'):
            return Response(status_code=416, headers={'Accept-Ranges':'none'})
        if request.method not in ('GET','HEAD'):
            if request.headers.get('x-career-request')!='1':return JSONResponse({'detail':'缺少同源请求标识'},403)
            if request.headers.get('content-type','').split(';')[0]!='application/json':return JSONResponse({'detail':'仅支持 JSON 请求'},415)
            chunks=[];size=0
            async for chunk in request.stream():
                size+=len(chunk)
                if size>8*1024*1024:return JSONResponse({'detail':'请求超过 8MB'},413)
                chunks.append(chunk)
            request._body=b''.join(chunks)
        response=await call_next(request)
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Career-Build-Id':app.state.local_runtime.build_id,'Content-Security-Policy':"default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'"})
        return response

    for cls,code in [(Invalid,422),(Conflict,409),(Missing,404),(ProviderError,503),(ArtifactError,422)]:
        async def handle(request,exc,status=code):
            body = {'detail':str(exc)}
            if getattr(exc, 'code', None):
                body['code'] = exc.code
            diagnostics = getattr(exc, 'diagnostics', None)
            if isinstance(diagnostics, dict):
                body['diagnostics'] = diagnostics
            return JSONResponse(body,status_code=status)
        app.add_exception_handler(cls,handle)

    @app.get('/healthz')
    def healthz():
        return {'status':'ok','build_id':app.state.local_runtime.build_id}

    @app.post('/api/local/stop')
    def local_stop(request:Request):
        if not app.state.local_runtime.authorize_control(request.headers.get('x-career-control')):
            return JSONResponse({'detail':'本实例控制凭据无效'}, status_code=403)
        threading.Timer(0.05, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
        return {'ok':True,'status':'stopping'}

    @app.get('/api/local/healthz')
    def local_healthz(request:Request):
        if not app.state.local_runtime.authorize_control(request.headers.get('x-career-control')):
            return JSONResponse({'detail':'本实例控制凭据无效'}, status_code=403)
        return app.state.local_runtime.diagnostics()

    @app.get('/api/state')
    def state(view: str = 'full', job_id: str | None = None):
        if view not in {'full', 'summary', 'profile', 'resume', 'feedback', 'opportunity'}:
            raise Invalid('state view 不合法')
        result = s.state(view, job_id)
        diagnostics = result.get('diagnostics', {})
        diagnostics.pop('data_dir', None)
        diagnostics.update(app.state.local_runtime.diagnostics())
        result['diagnostics'] = diagnostics
        return result
    @app.get('/api/ai/models')
    def ai_models():
        with s.connect(False) as c:return ai_settings(s, c)
    @app.post('/api/ai/models')
    def ai_model_create(b:dict):return create_ai_config(s, b)
    @app.post('/api/ai/test-connection')
    def ai_test_ephemeral(b:dict):return test_ai_ephemeral(s, b)
    @app.put('/api/ai/models/{config_id}')
    def ai_model_update(config_id:str,b:dict):return update_ai_config(s, config_id, b)
    @app.post('/api/ai/models/{config_id}/secret-cleanup-hold')
    def ai_model_cleanup_hold(config_id:str,b:dict):return mark_ai_cleanup_hold(s, config_id, b)
    @app.delete('/api/ai/models/{config_id}')
    def ai_model_delete(config_id:str,b:dict):return delete_ai_config(s, config_id, b.get('confirm') is True)
    @app.post('/api/ai/models/{config_id}/default')
    def ai_model_default(config_id:str,b:dict):return set_ai_default(s, config_id, b)
    @app.post('/api/ai/models/default/clear')
    def ai_model_clear_default():return clear_default(s)
    @app.post('/api/ai/models/{config_id}/test')
    def ai_model_test(config_id:str):return ModelGateway(s).test_connection(config_id)
    @app.get('/api/research/search-provider')
    def research_search_provider():return research_search_config.settings(s)
    @app.put('/api/research/search-provider')
    def research_search_provider_update(b:dict):return research_search_config.save(s, b)
    @app.post('/api/profile')
    def profile(b:dict):return s.save_profile(b.get('content'),b.get('expected_revision'))
    @app.post('/api/jobs')
    def jobs(b:dict):return s.save_job(b)
    @app.post('/api/jobs/{id}')
    def job(id:str,b:dict):return s.save_job(b,id)
    @app.post('/api/context')
    def context(b:dict):return s.context(b.get('job_id'),b.get('kind'),b.get('instruction',''),b.get('wiki_ids'))
    @app.post('/api/analysis')
    def analyze(b:dict):
        if b.get('kind')=='resume':raise Invalid('旧文字简历提案已停止写入，请在结构化简历工作台中编辑')
        key = required(b.get('idempotency_key'), '请求标识', 100)
        if not b.get('prepared_id') or b.get('confirm_outbound') is not True:
            from fastapi.responses import JSONResponse
            return JSONResponse(s.prepare_analysis(
                b.get('job_id'), b.get('kind'), b.get('instruction', ''),
                b.get('expected_epoch'), key, b.get('wiki_ids'), b.get('model_config_id'),
            ), status_code=409)
        return s.analyze(
            b.get('job_id'), b.get('kind'), b.get('instruction', ''),
            b.get('expected_epoch'), key, b.get('wiki_ids'),
            b.get('prepared_id'), b.get('payload_hash'), True, b.get('model_config_id'),
        )
    @app.post('/api/resumes')
    def resume(b:dict):
        job_id=required(b.get('job_id'),'机会',500)
        with s.connect(False) as c:
            s._get(c,job_id,'job')
            for item in s._current(c,'resume'):
                if item.get('job_id')==job_id:return dict(item,read_only=True)
        raise Missing('没有早期文字稿；请使用结构化简历工作台')
    @app.post('/api/resumes/{id}')
    def edit_resume(id:str,b:dict):raise Invalid('早期文字稿只读，请使用结构化简历工作台')
    @app.post('/api/proposals/{id}/apply')
    def apply(id:str,b:dict):raise Invalid('旧文字简历提案只读，请在结构化简历工作台中编辑')
    @app.post('/api/resumes/{id}/versions')
    def version(id:str,b:dict):raise Invalid('早期文字稿不能再创建版本，请使用结构化简历工作台')
    @app.post('/api/versions/{id}/pdf')
    def pdf(id:str,b:dict):return s.export_pdf(id)
    @app.get('/api/artifacts/{id}')
    def artifact(id:str,download:bool=False):
        p,a=s.artifact(id)
        return FileResponse(p,media_type=a['media_type'],filename=p.name,content_disposition_type='attachment' if download else 'inline')
    @app.post('/api/applications')
    def application(b:dict):return s.record_application(b)
    @app.post('/api/applications/{id}/status')
    def app_status(id:str,b:dict):return s.application_status(id,b.get('status'))
    @app.get('/api/feedback/export')
    def export(format:str='json'):
        feedback=s.state()['feedback']
        if format=='json':text=json.dumps({'schemaVersion':1,'feedback':feedback},ensure_ascii=False,indent=2);media='application/json';ext='json'
        elif format=='md':
            text='# Career 反馈原始记录\n\n'
            for f in feedback:
                text+='## '+f['created_at']+'\n\n'+f['text']+'\n\n'
                text+='页面：'+f['current_page']+' · 版本：'+f['app_version']+'\n\n'
                for n in f['notes']:text+='补充（'+n['created_at']+'）：\n\n'+n['text']+'\n\n'
            media='text/markdown';ext='md'
        else:raise Invalid('导出格式只能是 json 或 md')
        return Response(text,media_type=media,headers={'Content-Disposition':'attachment; filename="career-feedback.'+ext+'"'})
    @app.post('/api/feedback')
    def feedback(b:dict):return s.feedback(b)
    @app.post('/api/feedback/{id}/notes')
    def note(id:str,b:dict):return s.feedback_note(id,b.get('text'))
    @app.delete('/api/feedback/{id}')
    def delete_feedback(id:str,b:dict):return s.delete_feedback(id,b.get('confirm') is True)

    app.include_router(editor_router(s))
    from .resume_documents import router as resume_router
    from .submission import router as submission_router
    app.include_router(resume_router(s))
    app.include_router(submission_router(s))
    app.include_router(profile_router(s))
    app.include_router(journey_router(s))
    app.include_router(domain_router(s))
    app.include_router(knowledge_router(s))
    app.include_router(raw_wiki_router(s))
    from .feishu_read import router as feishu_read_router
    app.include_router(feishu_read_router(s, cli_path=feishu_cli_path))
    app.include_router(compiler_router(s))
    app.include_router(cognition_router(s, allow_compiler_start=allow_retired_cognition_compiler))
    app.include_router(ai_activity_router(s))
    app.include_router(opportunity_router(s))
    app.include_router(work_router(s))
    app.include_router(demo_router(s))
    app.include_router(engagement_router(s))
    app.include_router(employment_router(s))
    app.include_router(communication_router(s))
    app.include_router(timeline_router(s))
    app.include_router(interview_router(s))
    app.include_router(offer_router(s))
    app.include_router(research_router(s))

    dist=Path(frontend_dir) if frontend_dir else ROOT/'frontend/dist'
    if dist.exists():app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    else:
        @app.get('/')
        def missing_frontend():return Response('请先执行 cd frontend && npm ci && npm run build',status_code=503)
    return app
