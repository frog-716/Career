"""Revisioned current data and immutable evidence. Model adapters never receive Store."""
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .providers import get_provider, ProviderError
from .artifacts import write_pdf, write_screenshot, read_artifact

APP_VERSION = '0.1.0'
ROOT = Path(__file__).resolve().parents[2]

class Invalid(Exception): pass
class Conflict(Exception): pass
class Missing(Exception): pass

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
def dump(x): return json.dumps(x, ensure_ascii=False, sort_keys=True)
def digest(x): return hashlib.sha256(dump(x).encode()).hexdigest()
def required(x, name, limit=100000):
    if not isinstance(x,str) or not x.strip() or len(x)>limit: raise Invalid(name+'不能为空或超出长度限制')
    return x.strip()

class Store:
    def __init__(self, data_dir=None, provider=None):
        self.data_dir=Path(data_dir or os.environ.get('CAREER_DATA_DIR') or Path.home()/'Library/Application Support/CareerOS').expanduser().resolve()
        if self.data_dir==ROOT or ROOT in self.data_dir.parents: raise Invalid('数据目录必须在代码目录之外')
        self.data_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.chmod(self.data_dir,0o700)
        self.db=self.data_dir/'workspace.sqlite3'
        self.provider=provider or get_provider()
        with self.connect() as c:
            v=c.execute('PRAGMA user_version').fetchone()[0]
            if v>1: raise Invalid('数据库版本高于当前应用，请使用匹配版本')
            c.executescript('''
            CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL);
            INSERT OR IGNORE INTO meta VALUES(1,0);
            CREATE TABLE IF NOT EXISTS current (id TEXT PRIMARY KEY, kind TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS revisions (id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(id,revision));
            CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS current_kind ON current(kind);
            CREATE INDEX IF NOT EXISTS records_kind ON records(kind);
            CREATE UNIQUE INDEX IF NOT EXISTS run_request ON records(json_extract(body,'$.idempotency_key')) WHERE kind='run';
            CREATE UNIQUE INDEX IF NOT EXISTS version_pdf ON records(json_extract(body,'$.version_id')) WHERE kind='artifact';
            CREATE TABLE IF NOT EXISTS applications (id TEXT PRIMARY KEY, job_id TEXT NOT NULL, version_id TEXT NOT NULL REFERENCES records(id), artifact_id TEXT NOT NULL REFERENCES records(id), idempotency_key TEXT NOT NULL UNIQUE, body TEXT NOT NULL);
            PRAGMA user_version=1;
            ''')
            c.execute('INSERT OR IGNORE INTO current VALUES(?,?,?,?)',('profile','profile',0,dump(dict(id='profile',content='',revision=0,verified=False))))
            for r in self._records(c,'run'):
                if r['status']=='running':
                    r.update(status='failed',error='上次进程中断，请重新发起；不会自动重试收费调用')
                    self._record(c,'run',r)
        os.chmod(self.db,0o600)

    @contextmanager
    def connect(self, write=True):
        c=sqlite3.connect(str(self.db),timeout=15)
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA busy_timeout=15000')
        c.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback(); raise
        finally: c.close()

    def _get(self,c,id,kind=None,record=False):
        row=c.execute('SELECT kind,body FROM '+('records' if record else 'current')+' WHERE id=?',(id,)).fetchone()
        if not row or (kind and row[0]!=kind):raise Missing('记录不存在')
        return json.loads(row[1])
    def _records(self,c,kind):return [json.loads(r[0]) for r in c.execute('SELECT body FROM records WHERE kind=? ORDER BY rowid DESC',(kind,))]
    def _current(self,c,kind):return [json.loads(r[0]) for r in c.execute('SELECT body FROM current WHERE kind=? ORDER BY rowid DESC',(kind,))]
    def _record(self,c,kind,obj):c.execute('INSERT INTO records VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',(obj['id'],kind,dump(obj)))
    def _epoch(self,c):return c.execute('SELECT epoch FROM meta WHERE id=1').fetchone()[0]
    def _bump(self,c):
        c.execute('UPDATE meta SET epoch=epoch+1 WHERE id=1')
        for r in self._records(c,'run'):
            if r['status']=='succeeded':r['status']='stale';self._record(c,'run',r)
    def _save(self,c,kind,obj,expected):
        row=c.execute('SELECT revision FROM current WHERE id=?',(obj['id'],)).fetchone()
        rev=row[0] if row else 0
        if expected!=rev:raise Conflict('资料已在其它窗口更新，请保留输入并重新载入比较后保存')
        obj=dict(obj,revision=rev+1,updated_at=now())
        c.execute('INSERT INTO current VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,body=excluded.body',(obj['id'],kind,obj['revision'],dump(obj)))
        c.execute('INSERT INTO revisions VALUES(?,?,?,?)',(obj['id'],obj['revision'],dump(obj),now()))
        return obj

    def state(self):
        with self.connect(False) as c:
            return dict(profile=self._get(c,'profile'),jobs=self._current(c,'job'),resumes=self._current(c,'resume'),versions=self._records(c,'version'),artifacts=self._records(c,'artifact'),applications=[json.loads(r[0]) for r in c.execute('SELECT body FROM applications ORDER BY rowid DESC')],feedback=self._records(c,'feedback'),runs=self._records(c,'run'),diagnostics=dict(app_version=APP_VERSION,data_dir=str(self.data_dir),provider=self.provider.diagnostics()))

    def save_profile(self,content,expected):
        if not isinstance(content,str) or len(content)>100000:raise Invalid('资料内容过长')
        with self.connect() as c:
            obj=self._save(c,'profile',dict(id='profile',content=content,verified=False,source='user-edit'),expected)
            self._bump(c);return obj

    def save_job(self,body,id=None):
        with self.connect() as c:
            old=self._get(c,id,'job') if id else {}
            obj=dict(id=id or uid(),company=required(body.get('company'),'公司',500),title=required(body.get('title'),'岗位',500),jd=required(body.get('jd'),'JD'),url=body.get('url',''),status=body.get('status','active'),source='manual',created_at=old.get('created_at',now()))
            if not isinstance(obj['url'],str) or len(obj['url'])>2000:raise Invalid('URL 不合法')
            if obj['url'] and not obj['url'].startswith(('http://','https://')):raise Invalid('URL 仅支持 http/https')
            if obj['status'] not in ('active','excluded','deleted'):raise Invalid('岗位状态不合法')
            obj=self._save(c,'job',obj,body.get('expected_revision') if id else 0)
            self._bump(c);return obj

    def _packet(self,c,job_id,kind,instruction):
        if kind not in ('job','resume'):raise Invalid('分析任务不支持')
        if not isinstance(instruction,str) or len(instruction)>10000:raise Invalid('指令过长')
        p=self._get(c,'profile','profile');j=self._get(c,job_id,'job')
        if j['status']!='active':raise Invalid('岗位已删除或排除，请先恢复再分析')
        if not p['content'].strip():raise Invalid('请先保存个人资料')
        sources=[]
        for o,content,purpose in [(p,p['content'],'current_fact'),(j,{k:j[k] for k in ('company','title','jd','url')},'target_jd')]:
            sources.append(dict(id=o['id'],revision=o['revision'],hash=digest(content),purpose=purpose,content=content))
        return dict(schemaVersion=1,taskKind=kind,taskId=job_id,epoch=self._epoch(c),instruction=instruction,sources=sources)
    def context(self,job_id,kind,instruction=''):
        with self.connect(False) as c:return self._packet(c,job_id,kind,instruction)

    def _resume(self,c,job_id):
        self._get(c,job_id,'job')
        for r in self._current(c,'resume'):
            if r['job_id']==job_id:return r
        r=dict(id=uid(),job_id=job_id,content='',revision=0,created_at=now())
        c.execute('INSERT INTO current VALUES(?,?,?,?)',(r['id'],'resume',0,dump(r)))
        return r
    def open_resume(self,job_id):
        with self.connect() as c:return self._resume(c,job_id)
    def save_resume(self,id,content,expected):
        if not isinstance(content,str) or len(content)>100000:raise Invalid('简历内容过长')
        with self.connect() as c:
            r=self._get(c,id,'resume');r['content']=content
            saved=self._save(c,'resume',r,expected)
            for run in self._records(c,'run'):
                proposal=run.get('proposal',{})
                if proposal.get('target_id')==id and proposal.get('status')=='pending':
                    run['status']='stale';proposal['status']='stale'
                    self._record(c,'run',run);self._record(c,'proposal',proposal)
            return saved

    def _validate_result(self,result,packet):
        if not isinstance(result,dict):raise Invalid('模型输出不是对象')
        keys=('draft',) if packet['taskKind']=='resume' else ('core_goal','requirements','hard_gates','evidence','gaps','expression_issues','priorities','investment')
        if any(k not in result or not isinstance(result[k],(str,list,dict)) for k in keys):raise Invalid('模型结果缺少必需字段')
        if packet['taskKind']=='resume' and (not isinstance(result['draft'],str) or not result['draft'].strip() or len(result['draft'])>100000):raise Invalid('简历草稿格式不正确')
        claims=result.get('claims'); ids={s['id'] for s in packet['sources']}
        if not isinstance(claims,list) or not claims:raise Invalid('模型结果缺少判断来源')
        for claim in claims:
            if not isinstance(claim,dict) or claim.get('kind') not in ('Fact','Inference','Recommendation') or not isinstance(claim.get('text'),str) or not isinstance(claim.get('source_ids'),list):raise Invalid('模型判断结构不正确')
            if any(not isinstance(s,str) or s not in ids for s in claim['source_ids']):raise Invalid('模型引用了本轮资料之外的来源')
            if claim['kind']=='Fact' and not claim['source_ids']:raise Invalid('事实判断缺少来源')

    def analyze(self,job_id,kind,instruction='',expected_epoch=None,idempotency_key=None):
        key=required(idempotency_key or uid(),'请求标识',100)
        fingerprint=digest([job_id,kind,instruction,expected_epoch])
        with self.connect() as c:
            previous=c.execute("SELECT body FROM records WHERE kind='run' AND json_extract(body,'$.idempotency_key')=?",(key,)).fetchone()
            if previous:
                run=json.loads(previous[0])
                if run.get('request_fingerprint')!=fingerprint:raise Conflict('请求标识已用于不同分析')
                return run
            packet=self._packet(c,job_id,kind,instruction)
            if expected_epoch is not None and packet['epoch']!=expected_epoch:raise Conflict('预览后的资料已更新，请重新查看本次发送范围')
            draft=self._resume(c,job_id) if kind=='resume' else None
            payload=self.provider.build_payload(packet)
            run=dict(id=uid(),idempotency_key=key,request_fingerprint=fingerprint,kind=kind,job_id=job_id,status='running',packet=packet,payload=payload,result=None,created_at=now(),provider=self.provider.diagnostics())
            self._record(c,'run',run)
        try:
            result=self.provider.complete(payload)
            self._validate_result(result,packet)
            with self.connect() as c:
                stale=self._epoch(c)!=packet['epoch']
                if draft and self._get(c,draft['id'],'resume')['revision']!=draft['revision']:stale=True
                run.update(status='stale' if stale else 'succeeded',result=result)
                if draft and not stale:
                    p=dict(id=uid(),target_id=draft['id'],expected_revision=draft['revision'],before=draft['content'],after=result['draft'],epoch=packet['epoch'],status='pending',basis=result['claims'],created_at=now())
                    self._record(c,'proposal',p);run['proposal']=p
                self._record(c,'run',run)
            return run
        except Exception as e:
            with self.connect() as c:
                run.update(status='failed',error=str(e) if isinstance(e,(Invalid,ProviderError)) else '分析失败，请检查配置或稍后重试')
                self._record(c,'run',run)
            if isinstance(e,(Invalid,ProviderError)):raise
            raise ProviderError('分析失败，请检查配置或稍后重试') from None

    def apply_proposal(self,id):
        with self.connect() as c:
            p=self._get(c,id,'proposal',True)
            if p['status']=='applied':return p['applied_result']
            if self._epoch(c)!=p['epoch']:raise Conflict('建议已过期，请重新分析')
            r=self._get(c,p['target_id'],'resume')
            if r['revision']!=p['expected_revision']:raise Conflict('简历已修改，请重新分析；旧建议不会覆盖当前稿')
            r['content']=p['after'];r=self._save(c,'resume',r,p['expected_revision'])
            p.update(status='applied',applied_result=r);self._record(c,'proposal',p)
            for run in self._records(c,'run'):
                if run.get('proposal',{}).get('id')==id:run['proposal']=p;self._record(c,'run',run)
            return r

    def save_version(self,id,expected):
        with self.connect() as c:
            r=self._get(c,id,'resume')
            if r['revision']!=expected:raise Conflict('草稿已更新，请重新载入')
            required(r['content'],'简历')
            for v in self._records(c,'version'):
                if v['resume_id']==id and v['draft_revision']==expected:return v
            v=dict(id=uid(),resume_id=id,job_id=r['job_id'],content=r['content'],draft_revision=expected,created_at=now())
            self._record(c,'version',v);return v

    def export_pdf(self,id):
        with self.connect(False) as c:
            v=self._get(c,id,'version',True)
            for a in self._records(c,'artifact'):
                if a.get('version_id')==id:
                    p=read_artifact(self.data_dir,a['path'])
                    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=a['sha256']:raise Invalid('历史 PDF 丢失或损坏，请从备份恢复')
                    return a
        aid=uid();meta=write_pdf(self.data_dir,aid,v['content'])
        a=dict(meta,id=aid,version_id=id,created_at=now())
        with self.connect() as c:
            # A second request may have generated the same version while we rendered.
            for existing in self._records(c,'artifact'):
                if existing.get('version_id')==id:
                    read_artifact(self.data_dir,a['path']).unlink()
                    return existing
            self._record(c,'artifact',a)
        return a

    def artifact(self,id):
        with self.connect(False) as c:a=self._get(c,id,'artifact',True)
        p=read_artifact(self.data_dir,a['path'])
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=a['sha256']:raise Invalid('附件丢失或哈希校验失败')
        return p,a

    def record_application(self,b):
        key=required(b.get('idempotency_key'),'请求标识',100)
        try:
            time=datetime.fromisoformat(b.get('applied_at','').replace('Z','+00:00'))
            if time.tzinfo is None:raise ValueError()
        except (ValueError,TypeError):raise Invalid('投递时间必须包含时区')
        status=b.get('status','applied');self._status(status)
        with self.connect() as c:
            existing=c.execute('SELECT body FROM applications WHERE idempotency_key=?',(key,)).fetchone()
            if existing:
                obj=json.loads(existing[0])
                if any(obj[k]!=b.get(k) for k in ('job_id','version_id','artifact_id','applied_at')):raise Conflict('请求标识已用于不同投递')
                return obj
            j=self._get(c,b.get('job_id'),'job');v=self._get(c,b.get('version_id'),'version',True);a=self._get(c,b.get('artifact_id'),'artifact',True)
            if v['job_id']!=j['id'] or a.get('version_id')!=v['id']:raise Invalid('岗位、简历版本与 PDF 不匹配')
            p=read_artifact(self.data_dir,a['path'])
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=a['sha256']:raise Invalid('PDF 不存在或已损坏')
            obj=dict(id=uid(),job_id=j['id'],version_id=v['id'],artifact_id=a['id'],applied_at=b['applied_at'],status=status,created_at=now(),job_snapshot=j,resume_snapshot=v,artifact_snapshot=a)
            c.execute('INSERT INTO applications VALUES(?,?,?,?,?,?)',(obj['id'],j['id'],v['id'],a['id'],key,dump(obj)))
            return obj
    def _status(self,s):
        if s not in ('applied','interviewing','rejected','offer','closed'):raise Invalid('投递状态不合法')
    def application_status(self,id,status):
        self._status(status)
        with self.connect() as c:
            row=c.execute('SELECT body FROM applications WHERE id=?',(id,)).fetchone()
            if not row:raise Missing('投递不存在')
            obj=json.loads(row[0]);obj['status']=status
            c.execute('UPDATE applications SET body=? WHERE id=?',(dump(obj),id));return obj

    def feedback(self,b):
        required(b.get('text'),'反馈',20000)
        text=b['text']
        f=dict(id=uid(),text=text,created_at=now(),app_version=APP_VERSION,current_page=str(b.get('current_page',''))[:100],entity_id=str(b.get('entity_id') or '')[:100],notes=[])
        a=None
        if b.get('screenshot'):
            aid=uid();a=dict(write_screenshot(self.data_dir,aid,b['screenshot']),id=aid,created_at=now());f['screenshot_id']=aid
        with self.connect() as c:
            if a:self._record(c,'artifact',a)
            self._record(c,'feedback',f)
        return f
    def feedback_note(self,id,text):
        required(text,'补充',20000)
        with self.connect() as c:
            f=self._get(c,id,'feedback',True);f['notes'].append(dict(text=text,created_at=now()));self._record(c,'feedback',f);return f
