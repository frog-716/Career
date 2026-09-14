"""HTTP transport: browser calls services, never SQLite or arbitrary filesystem."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from .core import Store, Invalid, Conflict, Missing, ROOT, required
from .providers import ProviderError
from .artifacts import ArtifactError


def create_app(store=None):
    app=FastAPI(title='Career OS',docs_url=None,redoc_url=None,openapi_url=None)
    s=store or Store();app.state.store=s

    @app.middleware('http')
    async def local_only(request:Request,call_next):
        host=request.headers.get('host','')
        hostname=urlsplit('http://'+host).hostname
        if hostname not in ('localhost','127.0.0.1','testserver'):
            return JSONResponse({'detail':'仅允许本地访问'},403)
        origin=request.headers.get('origin')
        if origin and origin not in ('http://'+host,'https://'+host):
            return JSONResponse({'detail':'不允许跨站访问本地资料'},403)
        if request.headers.get('sec-fetch-site')=='cross-site':
            return JSONResponse({'detail':'不允许跨站访问本地资料'},403)
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
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"})
        return response

    for cls,code in [(Invalid,422),(Conflict,409),(Missing,404),(ProviderError,503),(ArtifactError,422)]:
        async def handle(request,exc,status=code):return JSONResponse({'detail':str(exc)},status_code=status)
        app.add_exception_handler(cls,handle)

    @app.get('/api/state')
    def state():return s.state()
    @app.post('/api/profile')
    def profile(b:dict):return s.save_profile(b.get('content'),b.get('expected_revision'))
    @app.post('/api/jobs')
    def jobs(b:dict):return s.save_job(b)
    @app.post('/api/jobs/{id}')
    def job(id:str,b:dict):return s.save_job(b,id)
    @app.post('/api/context')
    def context(b:dict):return s.context(b.get('job_id'),b.get('kind'),b.get('instruction',''))
    @app.post('/api/analysis')
    def analyze(b:dict):return s.analyze(b.get('job_id'),b.get('kind'),b.get('instruction',''),b.get('expected_epoch'),required(b.get('idempotency_key'),'请求标识',100))
    @app.post('/api/resumes')
    def resume(b:dict):return s.open_resume(b.get('job_id'))
    @app.post('/api/resumes/{id}')
    def edit_resume(id:str,b:dict):return s.save_resume(id,b.get('content'),b.get('expected_revision'))
    @app.post('/api/proposals/{id}/apply')
    def apply(id:str,b:dict):return s.apply_proposal(id)
    @app.post('/api/resumes/{id}/versions')
    def version(id:str,b:dict):return s.save_version(id,b.get('expected_revision'))
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
            text='# Career OS 反馈原始记录\n\n'
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

    dist=ROOT/'frontend/dist'
    if dist.exists():app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    else:
        @app.get('/')
        def missing_frontend():return Response('请先执行 cd frontend && npm ci && npm run build',status_code=503)
    return app
