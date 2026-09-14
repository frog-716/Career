# MVP 执行批次

目标：当前资料 → 手动 JD → 可审计 AI → 简历提案确认/编辑 → 版本/PDF → 显式投递，附全局反馈。仅用 fixtures 合成资料验收。
主控负责 core.py、app.py、核心测试、接口与验收；Luna UI 仅 frontend/；Luna Provider/Artifact 仅 providers.py、artifacts.py、对应 tests 与模块说明。禁止新任务/分支/worktree。

## 固定 Interface（schemaVersion 1）
Python 3.9 + FastAPI + SQLite 单库（逻辑隔离正本/分析），原子附件；TypeScript + Vite vanilla UI，无云部署。生产默认 ~/Library/Application Support/CareerOS，CAREER_DATA_DIR 必须在代码目录外。测试使用临时目录。服务仅 127.0.0.1:8765。

所有 API 前缀 /api，JSON；失败 {detail:中文说明}，冲突 409，未配置 Provider 503。GET /state 返回 {profile,jobs,resumes,versions,artifacts,applications,feedback,runs,diagnostics}。profile={id:'profile',revision,content,verified:false}，内容自由文本。其它实体均 id 字符串。日期 ISO，revision 整数。诊断 {app_version,data_dir,provider:{mode,configured,model,base_url}}。
POST /profile {content,expected_revision} 保存资料。
POST /jobs {company,title,jd,url?}；POST /jobs/{id} {company,title,jd,url,status,expected_revision}；status active/excluded/deleted。jobs 字段含 revision。
POST /context {job_id,kind:'job'|'resume',instruction?} 预览包；POST /analysis 同参数（额外 expected_epoch 可锁定预览，idempotency_key 必填并在相同动作重试时复用）。返回 run {id,kind,job_id,status,packet,payload,result,created_at,proposal?}，status succeeded/stale/failed。Context 只当前 profile+当前 job，无任何旧 AI/反馈/历史/草稿。用户每次输入独立 instruction；包 sources [{id,revision,hash,purpose,content}]，epoch。
job result={core_goal,requirements,hard_gates,evidence,gaps,expression_issues,priorities,investment,claims:[{kind:'Fact'|'Inference'|'Recommendation',text,source_ids:[]}]}。resume result={draft,claims:[...]}; 每个结果需要至少一个 claim，引用必须来自 sources。
POST /resumes {job_id} 创建或返回当前草稿 {id,job_id,content,revision}。
POST /resumes/{id} {content,expected_revision} 手改保存草稿。
分析 kind resume 自动产生 proposal={id,target_id,expected_revision,before,after,epoch,status,basis}，不自动改资料/草稿。
POST /proposals/{id}/apply {} 用户确认；检查 epoch/草稿 revision；重复应用幂等。
POST /resumes/{id}/versions {expected_revision} 保存不可变版本 {id,resume_id,job_id,content,created_at}。
POST /versions/{id}/pdf {} 生成 artifact {id,version_id,path,sha256,media_type,created_at}。
GET /artifacts/{id} 下载/打开文件。
POST /applications {job_id,version_id,artifact_id,applied_at,status,idempotency_key} 显式记录；状态 applied/interviewing/rejected/offer/closed。不可变材料快照，状态独立可更新 POST /applications/{id}/status {status}。
POST /feedback {text,current_page,entity_id?,screenshot?:{name,media_type,data_base64}} 仅显式输入及元数据，无页面正文采集；POST /feedback/{id}/notes {text} 补充不覆盖原话。GET /feedback/export?format=json|md 下载。
前端所有 POST 带 X-Career-Request: 1；仅同源请求。无密钥前端入口，诊断给环境变量配置步骤。页面必须显示未配置或测试模式。

## Provider / Artifact Python Interface
providers.py: ProviderError(Exception); get_provider() 返回 TestProvider 或 RealProvider（默认 real 未配置）；provider.diagnostics() 安全字典；provider.build_payload(packet:dict)->dict 为实际发送 JSON，fresh messages、无远程 conversation；provider.complete(payload:dict)->dict。Test 明确模式、确定性，仅从包摘取当前文字；Real 环境 CAREER_AI_BASE_URL（默认 https://api.openai.com/v1）、CAREER_AI_MODEL（必填）、CAREER_AI_API_KEY / OPENAI_API_KEY。CAREER_AI_PROVIDER=test 显式测试；默认 real。不得回显凭据或原始错误响应。build_payload 的 user content JSON 即 packet，system 指示 JSON 输出上述结构、引用 sources、不编造，恶意资料无工具权限。Real POST /chat/completions，timeout、有尺寸限制，不自动重试计费；界面保存的 payload 就是实际发送对象。
artifacts.py: ArtifactError(Exception); write_pdf(data_dir:Path, artifact_id:str, content:str)->dict {path:相对路径,sha256,media_type:'application/pdf',size}，实际中文 PDF、本地字体或内建 CJK 字体、分页、转义；read_artifact(data_dir:Path,relative_path:str)->Path 严格根目录内；write_screenshot(data_dir:Path,artifact_id:str,screenshot:dict)->dict，同上，PNG/JPEG 验证+限制 5MB。文件先临时后原子 rename。不写数据库。

## 验收
C01-C08 适用当前文本正本与提案；D01/D03/D05；MVP J01/J03；R01/R02/R04/R05。实际请求排除旧事实/分析/反馈，revision 竞争、proposal 幂等、PDF 文件和投递不可变、重启持久化、反馈原话保留和导出。R03 用隔离备份恢复。真实 AI 缺凭据待验收，禁止 Mock 冒充。

## 本批结果

本地独立链路已验收，真实 AI 因运行时配置缺失待验收。详情见 EVIDENCE.md，当前状态与下一步只见 STATUS.md。`GET /artifacts/{id}?download=true` 为浏览器不支持 PDF 预览时的下载路径。前端完整主链由主控接手整合；Luna完成Provider/Artifact、CSS及独立审查。
