import './style.css';

type Obj = Record<string, any>;
type Page = 'home' | 'jobs' | 'resume' | 'profile' | 'feedback' | 'diagnostics';
const root = document.querySelector<HTMLDivElement>('#app')!;
let state: Obj = { profile: { content: '', revision: 0 }, jobs: [], resumes: [], versions: [], artifacts: [], applications: [], feedback: [], runs: [], diagnostics: {} };
let page: Page = 'home';
let jobId = '';
let notice = '';
let profileBuffer: Obj | null = null;
const jobBuffers = new Map<string, Obj>();
const resumeBuffers = new Map<string, Obj>();
let saveTimer: ReturnType<typeof setTimeout> | undefined;
let saving: Promise<boolean> | null = null;
const statusNames: Obj = { active: '进行中', excluded: '已排除', deleted: '已删除', applied: '已投递', interviewing: '面试中', rejected: '已拒绝', offer: '收到 Offer', closed: '已结束', succeeded: '已返回 · 待审阅', stale: '已过期，请重新分析', failed: '失败', running: '处理中', pending: '待确认' };
const fieldNames: Obj = { core_goal: '岗位核心目标', requirements: '关键要求', hard_gates: '硬门槛', evidence: '当前证据', gaps: '缺口与未知', expression_issues: '表达问题', priorities: '建议优先级', investment: '是否值得继续投入', draft: '建议草稿' };
const esc = (value: any): string => String(value ?? '').replace(/[&<>"']/g, x => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[x]!));
const date = (value: string) => new Date(value).toLocaleString('zh-CN');
const $ = <T extends HTMLElement = HTMLElement>(selector: string) => document.querySelector<T>(selector);
const activeJobs = () => state.jobs.filter((j: Obj) => j.status === 'active');
const currentJob = () => state.jobs.find((j: Obj) => j.id === jobId);
const currentResume = () => state.resumes.find((r: Obj) => r.job_id === jobId);
const modeText = () => state.diagnostics?.provider?.mode === 'test' ? '测试模式 · 非真实 AI' : state.diagnostics?.provider?.configured ? '真实 AI · 已配置，调用结果待核验' : '真实 AI · 未配置';

class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
async function api(path: string, body?: Obj): Promise<any> {
  const response = await fetch('/api' + path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Career-Request': '1' }, body: JSON.stringify(body) });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(typeof result.detail === 'string' ? result.detail : '输入格式不正确，请检查后重试', response.status);
  return result;
}
async function load() { state = await api('/state'); }
function inform(text: string) { notice = text; const el = $('#notice'); if (el) { el.textContent = text; el.hidden = !text; } }
function failure(error: unknown) { inform(error instanceof Error ? error.message : '操作失败，请重试'); }
function isDirty() { return !!profileBuffer || jobBuffers.size > 0 || [...resumeBuffers.values()].some(b => b.dirty); }
window.addEventListener('beforeunload', event => { if (isDirty()) { event.preventDefault(); event.returnValue = ''; } });

function modal(title: string, content: string, onReady?: (dialog: HTMLDialogElement) => void): HTMLDialogElement {
  $('#modal')?.remove();
  const dialog = document.createElement('dialog'); dialog.id = 'modal';
  dialog.innerHTML = `<div class="modal-head"><h2>${esc(title)}</h2><button class="ghost" type="button" id="close-modal" aria-label="关闭弹窗">关闭</button></div><div id="modal-error" class="notice" hidden></div>${content}`;
  document.body.appendChild(dialog);
  dialog.querySelector('#close-modal')!.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => dialog.remove());
  dialog.showModal(); onReady?.(dialog); return dialog;
}
function modalError(error: unknown) { const el = $('#modal-error'); if (el) { el.textContent = error instanceof Error ? error.message : '操作失败'; el.hidden = false; } else failure(error); }
function comparison(title: string, mine: string, latest: string, resolve: () => void) {
  if ($('#modal')) { modalError(new Error('另有编辑发生版本冲突。当前弹窗内容仍保留，关闭后请再次保存并比较版本。')); return; }
  modal(title, `<p>当前输入已保留。请比较内容，再决定如何合并；不会自动覆盖服务器版本。</p><div class="diff"><section><h3>你的未保存内容</h3><pre>${esc(mine)}</pre></section><section><h3>服务器当前内容</h3><pre>${esc(latest)}</pre></section></div><button class="primary" id="resolve-conflict">基于最新版本继续编辑</button>`, dialog => {
    $('#resolve-conflict')!.onclick = () => { resolve(); dialog.close(); render(); inform('已保留你的内容并更新版本基线，请检查、合并后再保存。'); };
  });
}
function nav() {
  return `<aside><div class="brand"><span>✦</span> Career OS</div><div class="mode">${esc(modeText())}</div><nav>${(['home', 'jobs', 'resume', 'profile', 'feedback'] as Page[]).map((p, i) => `<button class="nav ${page === p ? 'active' : ''}" data-page="${p}">${['现在', '求职', '简历', '我的资料', '反馈记录'][i]}</button>`).join('')}</nav><div class="aside-foot"><button class="ghost" data-page="diagnostics">诊断与配置</button></div></aside>`;
}
function home() {
  const next = state.profile.content ? 'jobs' : 'profile';
  return `<section class="hero"><div><p class="eyebrow">CAREER OS · 个人职场工作台</p><h1>把下一步，做得<br><em>更有把握。</em></h1><p class="lede">从当前资料到目标岗位，再到一份可用的简历。每一步都由你掌握。</p><button class="primary" data-page="${next}">${next === 'profile' ? '填写个人资料' : '继续准备目标岗位'} →</button></div><div class="hero-art" aria-hidden="true"><div class="orb"></div><div class="orbit o1"></div><div class="orbit o2"></div><span class="float f1">当前任务</span><span class="float f2">有据可循</span></div></section><div class="section-head"><h2>你的工作台</h2><span class="muted">流程可以跳步，也可以回到任何一步</span></div><div class="cards"><article class="card accent"><small>当前目标</small><h3>${activeJobs().length} 个进行中岗位</h3><p>添加公司、岗位和 JD，先判断是否值得投入。</p><button class="text-btn" data-page="jobs">管理岗位 →</button></article><article class="card"><small>我的资料</small><h3>${state.profile.content ? '资料已保存' : '从你的经历开始'}</h3><p>保留职责、证据、目标与未知，随时编辑当前版本。</p><button class="text-btn" data-page="profile">查看资料 →</button></article><article class="card"><small>行动记录</small><h3>${state.applications.length} 次投递记录</h3><p>保存当时使用的简历版本和 PDF，方便后续回看。</p><button class="text-btn" data-page="resume">打开简历工作台 →</button></article></div>`;
}
function profilePage() {
  const p = profileBuffer || state.profile;
  return `<div class="page-title"><div><p class="eyebrow">我的资料</p><h1>当前职业资料</h1><p>填写经历、目标、技能、硬约束和未知。简历 AI 不会修改这里的正本。</p></div><span class="revision">当前版本 ${state.profile.revision}</span></div><div class="editor-card"><label for="profile-text">职业资料</label><textarea id="profile-text" placeholder="写下你的真实经历、本人职责、证据和职业目标；不确定的内容请注明。">${esc(p.content)}</textarea><div class="form-actions"><span class="muted">${profileBuffer ? '有未保存修改，离开页面仍会保留在本页会话' : '手动保存后在本机持久化'}</span><button class="primary" id="save-profile">保存资料</button></div></div>`;
}
function jobForm(j: Obj, prefix: string) {
  return `<label>公司<input id="${prefix}-company" name="company" required maxlength="500" value="${esc(j.company)}"></label><label>岗位名称<input id="${prefix}-title" name="title" required maxlength="500" value="${esc(j.title)}"></label><label>JD 正文<textarea id="${prefix}-jd" name="jd" required>${esc(j.jd)}</textarea></label><label>原始链接（可选）<input id="${prefix}-url" name="url" type="url" value="${esc(j.url)}" placeholder="https://..."></label>`;
}
function jobRow(j: Obj) { return `<button class="job-row ${jobId === j.id ? 'chosen' : ''}" data-job="${j.id}"><span class="job-icon">${esc(j.company.slice(0, 1))}</span><span><b>${esc(j.title)}</b><small>${esc(j.company)}</small></span><i>${statusNames[j.status]}</i></button>`; }
function jobsPage() {
  const archived = state.jobs.filter((j: Obj) => j.status !== 'active');
  return `<div class="page-title"><div><p class="eyebrow">求职</p><h1>目标岗位</h1><p>可以同时准备多个岗位，每份简历单独保存。</p></div><button class="primary" id="add-job">添加岗位</button></div><div class="job-layout"><section><div class="job-list">${activeJobs().map(jobRow).join('') || '<div class="empty">添加第一份 JD，开始准备。</div>'}</div>${archived.length ? `<details><summary>已排除 / 已删除（${archived.length}）</summary><div class="job-list">${archived.map(jobRow).join('')}</div></details>` : ''}</section><section class="job-detail">${jobDetail()}</section></div>`;
}
function jobDetail() {
  const j = currentJob(); if (!j) return '<div class="empty large">选择或添加一个岗位</div>';
  const b = jobBuffers.get(j.id) || j;
  return `<div class="detail-head"><div><span class="pill">${statusNames[j.status]}</span><h2>${esc(j.title)}</h2><p>${esc(j.company)}</p></div><div>${j.status === 'active' ? '<button class="ghost" data-job-status="excluded">排除</button><button class="danger" data-job-status="deleted">删除</button>' : '<button class="secondary" data-job-status="active">恢复岗位</button>'}</div></div><form id="edit-job">${jobForm(b, 'job')}<div class="form-actions"><span class="muted">当前版本 ${j.revision}</span><button class="secondary" type="submit">保存岗位</button></div></form>${j.status === 'active' ? '<div class="form-actions"><button class="primary" id="analyze-job">分析岗位</button><button class="secondary" id="open-resume">准备简历 →</button></div>' : '<p class="muted">该岗位已归档，历史投递材料仍可回看。</p><button class="secondary" id="open-resume">查看历史简历与投递</button>'}${runsHtml('job', j.id)}`;
}
function bufferFor(r: Obj): Obj {
  if (!resumeBuffers.has(r.id)) resumeBuffers.set(r.id, { content: r.content, revision: r.revision, dirty: false });
  return resumeBuffers.get(r.id)!;
}
function resumePage() {
  const r = currentResume(); const b = r ? bufferFor(r) : null;
  return `<div class="page-title"><div><p class="eyebrow">简历工作台</p><h1>准备一份有依据的简历</h1><p>AI 提案经你确认后进入工作稿，正式版本与历史投递单独保存。</p></div><label>目标岗位<select id="resume-job"><option value="">请选择岗位</option>${state.jobs.map((j: Obj) => `<option value="${j.id}" ${j.id === jobId ? 'selected' : ''}>${esc(j.title)} · ${esc(j.company)}${j.status !== 'active' ? '（已归档）' : ''}</option>`).join('')}</select></label></div>${!r ? '<div class="empty">请先添加或选择一个岗位，再开始编辑。</div><button class="primary" data-page="jobs">前往目标岗位</button>' : `<div class="resume-grid"><section class="editor-card"><div class="editor-label"><span>当前工作稿</span><small id="draft-version">版本 ${b!.revision}</small></div><label for="resume-text">简历正文</label><textarea id="resume-text" placeholder="可直接手动填写简历，无需先运行 AI。">${esc(b!.content)}</textarea><div class="form-actions"><span class="muted" id="autosave">${b!.dirty ? '有未保存修改' : '已保存；输入后自动保存'}</span><button class="secondary" id="save-resume">保存手改</button></div><button class="primary full" id="save-version">保存正式版本</button></section><section class="side-card"><h3>AI 简历适配</h3><p class="muted">每轮使用当前职业资料、目标 JD 与本轮指令。当前手改草稿不自动发送；可用新的指令重新生成提案。</p><button class="primary full" id="analyze-resume" ${currentJob()?.status !== 'active' ? 'disabled' : ''}>生成简历提案</button><h3>正式版本与 PDF</h3>${versionsHtml(r.id)}</section></div>${runsHtml('resume', jobId)}<section class="side-card applications"><h2>实际投递记录</h2><p class="muted">这里只登记已经发生的投递，不会对外发送任何材料。</p>${applicationsHtml(jobId)}</section>`}`;
}
function versionsHtml(resumeId: string) {
  return state.versions.filter((v: Obj) => v.resume_id === resumeId).map((v: Obj, i: number) => {
    const a = state.artifacts.find((a: Obj) => a.version_id === v.id);
    return `<div class="version"><div><b>${date(v.created_at)}</b><small>工作稿版本 ${v.draft_revision}</small><details><summary>查看保存的正文</summary><pre>${esc(v.content)}</pre></details></div><div>${a ? `<a href="/api/artifacts/${a.id}" target="_blank" rel="noopener" class="text-btn">预览 PDF</a><a href="/api/artifacts/${a.id}?download=true" class="text-btn">下载 PDF</a>` : `<button class="text-btn" data-pdf="${v.id}">生成 PDF</button>`}<button class="secondary" data-application="${v.id}" ${a ? '' : 'disabled'}>记录投递</button></div></div>`;
  }).join('') || '<p class="muted">先保存正式版本，再生成 PDF。保存版本不会自动记录投递。</p>';
}
function applicationsHtml(id: string) {
  return state.applications.filter((a: Obj) => a.job_id === id).map((a: Obj) => `<article class="application-row"><b>${esc(a.job_snapshot.company)} · ${esc(a.job_snapshot.title)}</b><p>${date(a.applied_at)} · 使用工作稿版本 ${a.resume_snapshot.draft_revision}</p><a href="/api/artifacts/${a.artifact_id}" target="_blank" rel="noopener">预览实际投递 PDF</a> <a href="/api/artifacts/${a.artifact_id}?download=true">下载实际投递 PDF</a><label>当前状态<select data-application-status="${a.id}">${['applied', 'interviewing', 'rejected', 'offer', 'closed'].map(s => `<option value="${s}" ${a.status === s ? 'selected' : ''}>${statusNames[s]}</option>`).join('')}</select></label><details><summary>当时的简历正文</summary><pre>${esc(a.resume_snapshot.content)}</pre></details></article>`).join('') || '<p class="muted">还没有投递记录。从上方已导出 PDF 的版本登记。</p>';
}
function renderResult(result: Obj) {
  return `<div class="result">${Object.entries(result).filter(([key]) => key !== 'claims').map(([key, value]) => `<div><b>${esc(fieldNames[key] || key)}</b><p class="preserve">${esc(Array.isArray(value) ? value.join('\n') || '未提供 / 待核实' : typeof value === 'object' ? JSON.stringify(value) : value)}</p></div>`).join('')}</div><details><summary>判断类型与依据</summary>${(result.claims || []).map((c: Obj) => `<p><b>${({ Fact: '事实', Inference: '推断', Recommendation: '建议' } as Obj)[c.kind]}</b> ${esc(c.text)}<small>来源：${esc(c.source_ids.map((id: string) => id === 'profile' ? '当前职业资料' : '目标 JD').join('、'))}</small></p>`).join('')}</details>`;
}
function runsHtml(kind: string, id: string) {
  const runs = state.runs.filter((r: Obj) => r.kind === kind && r.job_id === id);
  return runs.length ? `<section class="runs"><h2>${kind === 'job' ? '岗位分析' : '简历建议'}</h2>${runs.map((r: Obj, i: number) => `<details class="analysis-box" ${i === 0 ? 'open' : ''}><summary>${date(r.created_at)} · ${statusNames[r.status] || r.status} · ${r.provider?.mode === 'test' ? '测试结果' : '真实 Provider'}</summary>${r.error ? `<p class="notice">${esc(r.error)}</p>` : ''}${r.status === 'stale' ? '<p class="notice">资料或草稿已变化，本结果仅供历史查看，不能应用。</p>' : ''}${r.result ? renderResult(r.result) : ''}${r.proposal ? `<details><summary>查看修改前后</summary><div class="diff"><section><h3>修改前</h3><pre>${esc(r.proposal.before)}</pre></section><section><h3>建议修改后</h3><pre>${esc(r.proposal.after)}</pre></section></div></details>${r.status === 'succeeded' && r.proposal.status === 'pending' ? `<p class="muted">请核对每一项职业事实，再确认采用。</p><button class="primary" data-proposal="${r.proposal.id}">确认应用提案</button>` : r.proposal.status === 'applied' ? '<p>提案已确认应用</p>' : ''}` : ''}<details><summary>本轮资料包与版本</summary><pre>${esc(JSON.stringify(r.packet, null, 2))}</pre></details><details><summary>实际 Provider 请求体</summary><pre>${esc(JSON.stringify(r.payload, null, 2))}</pre></details></details>`).join('')}</section>` : '';
}
function feedbackPage() {
  return `<div class="page-title"><div><p class="eyebrow">反馈记录</p><h1>留住使用中的感受</h1><p>原话永久保留，补充单独追加；不会进入职业资料或 AI 分析。</p></div><div><a class="secondary link-btn" href="/api/feedback/export?format=md">导出 Markdown</a> <a class="secondary link-btn" href="/api/feedback/export?format=json">导出 JSON</a></div></div><div class="timeline">${state.feedback.map((f: Obj) => `<article><span class="dot"></span><div><small>${date(f.created_at)} · ${esc(f.current_page)} · 应用 ${esc(f.app_version)}</small><p class="preserve">${esc(f.text)}</p>${f.screenshot_id ? `<a href="/api/artifacts/${f.screenshot_id}" target="_blank" rel="noopener">查看截图</a>` : ''}${f.notes.map((n: Obj) => `<blockquote><small>补充于 ${date(n.created_at)}</small><p class="preserve">${esc(n.text)}</p></blockquote>`).join('')}<button class="text-btn" data-note="${f.id}">添加补充</button></div></article>`).join('') || '<div class="empty">还没有反馈。随时点击右下角“记录反馈”。</div>'}</div>`;
}
function diagnosticsPage() {
  const d = state.diagnostics;
  return `<div class="page-title"><div><h1>诊断与配置</h1><p>${esc(modeText())}</p></div></div><section class="card"><p>应用版本：${esc(d.app_version)}</p><p>本地数据目录：${esc(d.data_dir)}</p><p>Provider 地址：${esc(d.provider?.base_url || '测试 Provider 不出网')}</p><p>模型：${esc(d.provider?.model || '未配置')}</p></section><section class="setup"><h2>配置真实 AI</h2><ol><li>停止已运行的服务。</li><li>在本地终端设置 CAREER_AI_PROVIDER=real、CAREER_AI_MODEL，以及 CAREER_AI_API_KEY（或 OPENAI_API_KEY）。密钥不要发到聊天，也不要填在网页。</li><li>如使用兼容服务，设置 CAREER_AI_BASE_URL；默认 https://api.openai.com/v1。</li><li>重新运行项目根目录的 .venv/bin/python scripts/run.py。</li></ol><p>详细命令见项目 src/workbench/README.md。开发助手的模型权限不代表产品运行时授权。</p><p>缺配置时仍可编辑资料、手写简历、导出 PDF、记录投递和反馈。</p><p>切换测试模式需显式设置 CAREER_AI_PROVIDER=test，测试结果不代表真实 AI。</p></section>`;
}
function render() {
  root.innerHTML = nav() + `<main><div id="notice" class="notice" role="status" ${notice ? '' : 'hidden'}>${esc(notice)}</div>${({ home, jobs: jobsPage, profile: profilePage, resume: resumePage, feedback: feedbackPage, diagnostics: diagnosticsPage } as Record<Page, () => string>)[page]()}</main><button id="capture-feedback" class="feedback-fab">记录反馈</button>`;
  bind();
}
async function navigate(next: Page, id = jobId) {
  if (!(await flushResume())) return;
  page = next; jobId = id; notice = '';
  if (page === 'resume' && jobId) await ensureResume();
  history.replaceState(null, '', '#' + page + (jobId ? '/' + jobId : ''));
  render();
  window.scrollTo(0, 0);
}
async function ensureResume() {
  const r = await api('/resumes', { job_id: jobId });
  const index = state.resumes.findIndex((x: Obj) => x.id === r.id);
  if (index < 0) state.resumes.push(r); else state.resumes[index] = r;
  if (!resumeBuffers.get(r.id)?.dirty) resumeBuffers.set(r.id, { content: r.content, revision: r.revision, dirty: false });
}
async function saveProfile() {
  const b = profileBuffer || { ...state.profile }; const sent = b.content;
  try {
    const p = await api('/profile', { content: sent, expected_revision: b.revision });
    state.profile = p;
    if (profileBuffer?.content === sent) profileBuffer = null;
    else if (profileBuffer) profileBuffer.revision = p.revision;
    await load(); render(); inform('个人资料已保存。');
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      await load(); comparison('个人资料存在新版本', b.content, state.profile.content, () => { profileBuffer = { ...b, revision: state.profile.revision }; });
    } else failure(e);
  }
}
async function saveJob(event: Event) {
  event.preventDefault(); const j = currentJob(); const b = jobBuffers.get(j.id) || { ...j };
  const sent = JSON.stringify(b);
  try {
    const result = await api('/jobs/' + j.id, { ...b, expected_revision: b.revision });
    if (JSON.stringify(jobBuffers.get(j.id) || b) === sent) jobBuffers.delete(j.id);
    else jobBuffers.get(j.id)!.revision = result.revision;
    await load(); render(); inform('岗位已保存。');
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      await load(); const latest = state.jobs.find((x: Obj) => x.id === j.id);
      comparison('岗位已被更新', [b.company, b.title, b.jd, b.url].join('\n'), [latest.company, latest.title, latest.jd, latest.url].join('\n'), () => jobBuffers.set(j.id, { ...b, revision: latest.revision }));
    } else failure(e);
  }
}
function addJob() {
  modal('添加目标岗位', `<form id="new-job">${jobForm({}, 'new')}<button class="primary full" type="submit">保存岗位</button></form>`, dialog => {
    $('#new-job')!.onsubmit = async event => {
      event.preventDefault(); const button = dialog.querySelector<HTMLButtonElement>('button[type=submit]')!; button.disabled = true;
      const form = new FormData($('#new-job') as HTMLFormElement);
      try { const j = await api('/jobs', Object.fromEntries(form.entries())); jobId = j.id; await load(); dialog.close(); history.replaceState(null, '', '#jobs/' + jobId); render(); inform('岗位已添加。'); }
      catch (e) { modalError(e); button.disabled = false; }
    };
  });
}
async function changeJobStatus(status: string) {
  const j = currentJob();
  if (jobBuffers.has(j.id)) { inform('请先保存岗位修改，再更改状态。'); return; }
  try { await api('/jobs/' + j.id, { ...j, status, expected_revision: j.revision }); await load(); render(); }
  catch (e) { failure(e); }
}
async function flushResume(): Promise<boolean> {
  clearTimeout(saveTimer);
  if (saving) { const ok = await saving; return ok ? flushResume() : false; }
  const r = currentResume(); if (!r) return true;
  const b = bufferFor(r); if (!b.dirty) return true;
  if (b.conflict) {
    await load(); const latest = state.resumes.find((x: Obj) => x.id === r.id);
    comparison('简历存在新版本', b.content, latest.content, () => { b.revision = latest.revision; b.conflict = false; });
    return false;
  }
  const text = b.content; const revision = b.revision;
  saving = (async () => {
    try {
      const saved = await api('/resumes/' + r.id, { content: text, expected_revision: revision });
      b.revision = saved.revision; b.dirty = b.content !== text;
      Object.assign(r, saved);
      const label = $('#autosave'); if (label) label.textContent = b.dirty ? '继续保存新修改…' : '已自动保存';
      const revLabel = $('#draft-version'); if (revLabel) revLabel.textContent = '版本 ' + b.revision;
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        b.conflict = true; await load(); const latest = state.resumes.find((x: Obj) => x.id === r.id);
        comparison('简历存在新版本', b.content, latest.content, () => { b.revision = latest.revision; b.conflict = false; });
      } else failure(e);
      return false;
    }
  })();
  const ok = await saving; saving = null;
  return ok && b.dirty ? flushResume() : ok;
}
async function saveVersion() {
  if (!(await flushResume())) return;
  const r = currentResume();
  try { await api('/resumes/' + r.id + '/versions', { expected_revision: bufferFor(r).revision }); await load(); render(); inform('正式版本已保存，可生成 PDF。'); }
  catch (e) { failure(e); }
}
async function createPdf(id: string) {
  try { await api('/versions/' + id + '/pdf', {}); await load(); render(); inform('PDF 已生成并关联此版本。'); }
  catch (e) { failure(e); }
}
async function prepareAnalysis(kind: 'job' | 'resume') {
  if (!(await flushResume())) return;
  if (profileBuffer || jobBuffers.has(jobId)) { inform('请先保存个人资料和当前岗位修改，再预览分析。'); return; }
  const selected = jobId;
  modal(kind === 'job' ? '分析岗位' : '生成简历提案', `<p>${esc(modeText())}</p><label>本轮调整指令（可选）<textarea id="instruction" placeholder="例如：重点看实际参与范围；不要添加未知的量化成果。"></textarea></label><button class="primary full" id="preview-context">预览本轮资料</button><div id="context-preview"></div>`, dialog => {
    $('#preview-context')!.onclick = async () => {
      const body = { job_id: selected, kind, instruction: ($('#instruction') as HTMLTextAreaElement).value };
      try {
        const packet = await api('/context', body); const key = crypto.randomUUID();
        $('#context-preview')!.innerHTML = `<h3>本次发送范围</h3><p>当前职业资料（版本 ${packet.sources[0].revision}）＋目标 JD（版本 ${packet.sources[1].revision}）＋上面的本轮指令。</p><p>未包含旧修订、旧分析、历史简历或反馈。请核对下面的完整资料包。</p><details open><summary>查看本轮资料包</summary><pre>${esc(JSON.stringify(packet, null, 2))}</pre></details><button class="primary full" id="send-analysis">确认发送${state.diagnostics.provider.mode === 'test' ? '（测试模式）' : '给 Provider'}</button>`;
        ($('#instruction') as HTMLTextAreaElement).disabled = true;
        $('#send-analysis')!.onclick = async () => {
          const button = $('#send-analysis') as HTMLButtonElement; button.disabled = true; button.textContent = '正在分析，请稍候…';
          try {
            const result = await api('/analysis', { ...body, expected_epoch: packet.epoch, idempotency_key: key });
            await load(); dialog.close(); render(); inform(result.status === 'succeeded' ? '分析已返回，请审阅依据和未知项。' : statusNames[result.status] || result.status);
          } catch (e) { modalError(e); button.disabled = false; button.textContent = '检查结果 / 重试同一请求'; }
        };
      } catch (e) { modalError(e); }
    };
  });
}
async function applyProposal(id: string) {
  if (!(await flushResume())) return;
  try {
    const result = await api('/proposals/' + id + '/apply', {});
    resumeBuffers.set(result.id, { content: result.content, revision: result.revision, dirty: false });
    await load(); render(); inform('已确认应用到简历工作稿，个人资料正本未改动。');
  } catch (e) { await load(); render(); failure(e); }
}
function recordApplication(versionId: string) {
  const v = state.versions.find((v: Obj) => v.id === versionId); const a = state.artifacts.find((a: Obj) => a.version_id === v.id); const j = state.jobs.find((j: Obj) => j.id === v.job_id);
  if (!a) { inform('请先生成并检查此版本的 PDF。'); return; }
  const time = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16); const key = crypto.randomUUID();
  modal('记录实际投递', `<form id="application-form"><p>${esc(j.company)} · ${esc(j.title)}</p><p>简历保存于 ${date(v.created_at)} · 工作稿版本 ${v.draft_revision}</p><a href="/api/artifacts/${a.id}" target="_blank" rel="noopener">检查实际使用的 PDF</a><label>实际投递时间<input id="applied-at" type="datetime-local" required value="${time}"></label><label>当前状态<select id="application-status">${['applied', 'interviewing', 'rejected', 'offer', 'closed'].map(s => `<option value="${s}">${statusNames[s]}</option>`).join('')}</select></label><p class="muted">确认已实际投递后保存。此操作仅记录事件，不会替你投递。</p><button class="primary full" type="submit">保存投递记录</button></form>`, dialog => {
    let request: Obj | null = null;
    $('#application-form')!.onsubmit = async event => {
      event.preventDefault(); const button = dialog.querySelector<HTMLButtonElement>('button[type=submit]')!; button.disabled = true;
      request ||= { job_id: j.id, version_id: v.id, artifact_id: a.id, applied_at: new Date(($('#applied-at') as HTMLInputElement).value).toISOString(), status: ($('#application-status') as HTMLSelectElement).value, idempotency_key: key };
      try { await api('/applications', request); await load(); dialog.close(); render(); inform('投递已记录，历史材料已固定。'); }
      catch (e) { modalError(e); button.disabled = false; }
    };
  });
}
async function screenshotData(input: HTMLInputElement) {
  const file = input.files?.[0]; if (!file) return undefined;
  if (file.size > 5 * 1024 * 1024 || !['image/png', 'image/jpeg'].includes(file.type)) throw new Error('截图仅支持 5MB 以内的 PNG / JPEG。');
  const data = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(new Error('无法读取截图')); reader.onload = () => resolve(String(reader.result).split(',')[1]); reader.readAsDataURL(file); });
  return { name: file.name, media_type: file.type, data_base64: data };
}
function captureFeedback() {
  const capturedPage = page; const entity = ['jobs', 'resume'].includes(page) ? jobId : page === 'profile' ? 'profile' : '';
  modal('记录反馈', `<form id="feedback-form"><label>此刻的感受<textarea id="feedback-text" required placeholder="随手记一句就好。" autofocus></textarea></label><label>截图（可选）<input id="feedback-screenshot" type="file" accept="image/png,image/jpeg"></label><p class="muted">仅保存你输入的文字、选中的截图和当前位置，不采集页面正文。</p><button class="primary full" type="submit">保存并关闭</button></form>`, dialog => {
    $('#feedback-form')!.onsubmit = async event => {
      event.preventDefault(); const button = dialog.querySelector<HTMLButtonElement>('button[type=submit]')!; button.disabled = true;
      try {
        await api('/feedback', { text: ($('#feedback-text') as HTMLTextAreaElement).value, current_page: capturedPage, entity_id: entity, screenshot: await screenshotData($('#feedback-screenshot') as HTMLInputElement) });
        await load(); dialog.close(); if (page === 'feedback') render(); inform('反馈已保存。可以继续当前任务。');
      } catch (e) { modalError(e); button.disabled = false; }
    };
  });
}
function addNote(id: string) {
  modal('补充反馈', '<form id="note-form"><label>补充内容<textarea id="note-text" required></textarea></label><button type="submit" class="primary full">保存补充</button></form>', dialog => {
    $('#note-form')!.onsubmit = async event => {
      event.preventDefault(); const button = dialog.querySelector<HTMLButtonElement>('button[type=submit]')!; button.disabled = true;
      try { await api('/feedback/' + id + '/notes', { text: ($('#note-text') as HTMLTextAreaElement).value }); await load(); dialog.close(); render(); }
      catch (e) { modalError(e); button.disabled = false; }
    };
  });
}
function bind() {
  document.querySelectorAll<HTMLElement>('[data-page]').forEach(el => el.onclick = () => { void navigate(el.dataset.page as Page).catch(failure); });
  document.querySelectorAll<HTMLElement>('[data-job]').forEach(el => el.onclick = () => { void navigate('jobs', el.dataset.job).catch(failure); });
  $('#capture-feedback')!.onclick = captureFeedback;
  $('#add-job')?.addEventListener('click', addJob);
  $('#save-profile')?.addEventListener('click', saveProfile);
  $('#profile-text')?.addEventListener('input', event => { profileBuffer ||= { ...state.profile }; profileBuffer!.content = (event.target as HTMLTextAreaElement).value; });
  $('#edit-job')?.addEventListener('submit', saveJob);
  $('#edit-job')?.addEventListener('input', event => { const input = event.target as HTMLInputElement; const j = currentJob(); const b = jobBuffers.get(j.id) || { ...j }; b[input.name] = input.value; jobBuffers.set(j.id, b); });
  document.querySelectorAll<HTMLElement>('[data-job-status]').forEach(el => el.onclick = () => { void changeJobStatus(el.dataset.jobStatus!); });
  $('#open-resume')?.addEventListener('click', () => { void navigate('resume').catch(failure); });
  $('#resume-job')?.addEventListener('change', event => { void navigate('resume', (event.target as HTMLSelectElement).value).catch(failure); });
  $('#resume-text')?.addEventListener('input', event => {
    const b = bufferFor(currentResume()); b.content = (event.target as HTMLTextAreaElement).value; b.dirty = true;
    $('#autosave')!.textContent = '等待保存…'; clearTimeout(saveTimer); saveTimer = setTimeout(() => { void flushResume(); }, 700);
  });
  $('#save-resume')?.addEventListener('click', () => { void flushResume().then(async ok => { if (ok) { await load(); render(); inform('简历手改已保存。'); } }).catch(failure); });
  $('#save-version')?.addEventListener('click', saveVersion);
  $('#analyze-job')?.addEventListener('click', () => { void prepareAnalysis('job'); });
  $('#analyze-resume')?.addEventListener('click', () => { void prepareAnalysis('resume'); });
  document.querySelectorAll<HTMLElement>('[data-pdf]').forEach(el => el.onclick = () => { void createPdf(el.dataset.pdf!); });
  document.querySelectorAll<HTMLElement>('[data-proposal]').forEach(el => el.onclick = () => { void applyProposal(el.dataset.proposal!); });
  document.querySelectorAll<HTMLElement>('[data-application]').forEach(el => el.onclick = () => recordApplication(el.dataset.application!));
  document.querySelectorAll<HTMLSelectElement>('[data-application-status]').forEach(el => el.onchange = async () => { try { await api('/applications/' + el.dataset.applicationStatus + '/status', { status: el.value }); await load(); render(); } catch (e) { failure(e); } });
  document.querySelectorAll<HTMLElement>('[data-note]').forEach(el => el.onclick = () => addNote(el.dataset.note!));
}
async function start() {
  try {
    await load(); const [p, id] = location.hash.slice(1).split('/');
    if (['home', 'jobs', 'resume', 'profile', 'feedback', 'diagnostics'].includes(p)) page = p as Page;
    jobId = state.jobs.some((j: Obj) => j.id === id) ? id : activeJobs()[0]?.id || '';
    if (page === 'resume' && jobId) await ensureResume(); render();
  } catch (e) { render(); failure(e); }
}
void start();
