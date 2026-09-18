import { opportunityHTML, bindOpportunity } from "./opportunity-ui";
import "./style.css";
import { ui, view, shell, stageNames, noteNames, bindSidebarOrder, sidebarHome } from "./workspace";
import { bindKnowledge, knowledgeUI, entryNames } from "./knowledge-ui";

import { bindProfile, hasUnsavedProfile } from "./profile-ui";
import { bindRecords } from "./record-ui";
import { bindAiSettings } from "./ai-config-ui";

type Obj = Record<string, any>;
type Page =
  | "wiki"
  | "directory"
  | "jobs"
  | "resume"
  | "profile"
  | "feedback"
  | "diagnostics"
  | "progress"
  | "work"
  | "practice"
  | "footprint";
const PAGE_IDS: Page[] = [
  "wiki", "directory", "jobs", "progress", "work", "practice", "footprint",
  "resume", "profile", "feedback", "diagnostics",
];
const isPage = (value: string): value is Page => PAGE_IDS.includes(value as Page);
const root = document.querySelector<HTMLDivElement>("#app")!;
let state: Obj = {
  profile: { content: "", revision: 0 },
  jobs: [],
  resumes: [],
  versions: [],
  artifacts: [],
  applications: [],
  feedback: [],
  runs: [],
  diagnostics: {},
};
let journey: Obj = { plans: [], episodes: [], notes: [] };
let editorVersions: Obj[] = [];
let knowledge: Obj = { sources: [], candidates: [], entries: [] };
let domain: Obj = { objects: [], opportunities: [], resume_uses: [] };
let workDomain: Obj = { employments: [], projects: [], sources: [], persons: [], participants: [], events: [], achievements: [], evidence: [], evidence_links: [] };
let opportunityCommunications: Obj[] = [];
let opportunityTimeline: Obj = { items: [], unknown_date_items: [] };
let opportunityInterviews: Obj[] = [];
let opportunityOffer: Obj | null = null;
let opportunityResearch: Obj = {company: {items: []}, opportunity: {items: [], revision: 0}};
let opportunityLoadToken = 0;
const planBuffers = new Map<string, Obj>();
let page: Page = sidebarHome() as Page;
let jobId = "";
let notice = "";
let opportunityView = "all";
let opportunityAnchor = "";
let profileBuffer: Obj | null = null;
const jobBuffers = new Map<string, Obj>();
const resumeBuffers = new Map<string, Obj>();
let saveTimer: ReturnType<typeof setTimeout> | undefined;
let saving: Promise<boolean> | null = null;
const statusNames: Obj = {
  active: "进行中",
  excluded: "已排除",
  deleted: "已删除",
  applied: "已投递",
  interviewing: "面试中",
  rejected: "已拒绝",
  offer: "收到 Offer",
  closed: "已结束",
  succeeded: "已返回 · 待审阅",
  stale: "已过期，请重新分析",
  failed: "失败",
  running: "处理中",
  pending: "待确认",
};
const fieldNames: Obj = {
  core_goal: "岗位核心目标",
  requirements: "关键要求",
  hard_gates: "硬门槛",
  evidence: "当前证据",
  gaps: "缺口与未知",
  expression_issues: "表达问题",
  priorities: "建议优先级",
  investment: "是否值得继续投入",
  draft: "建议草稿",
};
const esc = (value: any): string =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (x) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        x
      ]!,
  );
const date = (value: string) => new Date(value).toLocaleString("zh-CN");
const $ = <T extends HTMLElement = HTMLElement>(selector: string) =>
  document
    .querySelector<HTMLDialogElement>("#modal")
    ?.querySelector<T>(selector) || document.querySelector<T>(selector);
const activeJobs = () => state.jobs.filter((j: Obj) => j.status === "active");
const currentJob = () => state.jobs.find((j: Obj) => j.id === jobId);
const currentResume = () => state.resumes.find((r: Obj) => r.job_id === jobId);
const modeText = () => {
  if (state.diagnostics?.provider?.mode === "test") return "测试模式 · 非真实 AI";
  const ai = state.ai;
  const current = ai?.configs?.find(
    (config: Obj) => config.id === ai.default_model_config_id,
  );
  if (current) return `真实 AI · ${current.provider} / ${current.model}`;
  return "真实 AI · 未配置";
};

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
async function api(path: string, body?: Obj, method = "POST"): Promise<any> {
  const response = await fetch(
    "/api" + path,
    body === undefined
      ? {}
      : {
          method,
          headers: {
            "Content-Type": "application/json",
            "X-Career-Request": "1",
          },
          body: JSON.stringify(body),
        },
  );
  const result = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new ApiError(
      typeof result.detail === "string"
        ? result.detail
        : "输入格式不正确，请检查后重试",
      response.status,
    );
  return result;
}
async function load() {
  const data = await Promise.all([
    api("/state"),
    api("/journey"),
    api("/knowledge"),
    api("/domain"),
    api("/work-domain").catch(() => ({ employments: [], projects: [], sources: [], persons: [], participants: [], events: [], achievements: [], evidence: [], evidence_links: [] })),
  ]);
  [state, journey, knowledge, domain, workDomain] = data;
  const [editorResult, catalogue] = await Promise.all([api("/editor/versions"), api("/resume-documents")]);
  state.resume_documents = catalogue.documents;
  editorVersions = Array.isArray(editorResult)
    ? editorResult
    : editorResult.versions;
  if (!Array.isArray(editorVersions))
    throw new Error("编辑器版本返回格式不正确");
  await loadOpportunityScope(jobId);
}
async function loadOpportunityScope(id: string) {
  const token = ++opportunityLoadToken;
  if (!(page === "jobs" || page === "progress") || !id) {
    opportunityCommunications = [];
    opportunityTimeline = { items: [], unknown_date_items: [] };
    opportunityInterviews = [];
    opportunityOffer = null;
    opportunityResearch = {company: {items: []}, opportunity: {items: [], revision: 0}};
    return;
  }
  const result = await Promise.all([
    api("/opportunities/" + encodeURIComponent(id) + "/communications"),
    api("/opportunities/" + encodeURIComponent(id) + "/timeline"),
    api("/opportunities/" + encodeURIComponent(id) + "/interviews"),
    api("/opportunities/" + encodeURIComponent(id) + "/offer"),
    api("/opportunities/" + encodeURIComponent(id) + "/research-overview"),
  ]);
  if (token !== opportunityLoadToken || id !== jobId || !(page === "jobs" || page === "progress")) return;
  [opportunityCommunications, opportunityTimeline, opportunityInterviews, opportunityOffer, opportunityResearch] = result;
}
function inform(text: string) {
  notice = text;
  const el = $("#notice");
  if (el) {
    el.textContent = text;
    el.hidden = !text;
  }
}
function failure(error: unknown) {
  inform(error instanceof Error ? error.message : "操作失败，请重试");
}
function isDirty() {
  return (
    !!document.querySelector("dialog[open][data-dirty=true]") ||
    !!profileBuffer || hasUnsavedProfile() ||
    jobBuffers.size > 0 ||
    planBuffers.size > 0 ||
    [...resumeBuffers.values()].some((b) => b.dirty)
  );
}
window.addEventListener("beforeunload", (event) => {
  if (isDirty()) {
    event.preventDefault();
    event.returnValue = "";
  }
});

function modal(
  title: string,
  content: string,
  onReady?: (dialog: HTMLDialogElement) => void,
): HTMLDialogElement {
  const parent = document.querySelector<HTMLDialogElement>("#modal");
  if (parent) parent.removeAttribute("id");
  const dialog = document.createElement("dialog");
  dialog.id = "modal";
  dialog.innerHTML = `<div class="modal-head"><h2>${esc(title)}</h2><div>${title === "记录反馈" ? "" : '<button type="button" class="text-btn" data-modal-feedback>记录反馈</button> '}<button class="ghost" type="button" aria-label="关闭弹窗">关闭</button></div></div><div id="modal-error" class="notice" hidden></div>${content}`;
  document.body.appendChild(dialog);
  dialog
    .querySelector('[aria-label="关闭弹窗"]')!
    .addEventListener("click", () => dialog.close());
  dialog
    .querySelector("[data-modal-feedback]")
    ?.addEventListener("click", captureFeedback);
  dialog.addEventListener("input", () => {
    dialog.dataset.dirty = "true";
  });
  dialog.addEventListener("close", () => {
    dialog.remove();
    if (parent?.isConnected) parent.id = "modal";
  });
  dialog.showModal();
  onReady?.(dialog);
  return dialog;
}
function modalError(error: unknown) {
  const el = document.querySelector("#modal #modal-error");
  if (el) {
    el.textContent = error instanceof Error ? error.message : "操作失败";
    (el as HTMLElement).hidden = false;
  } else failure(error);
}
function comparison(
  title: string,
  mine: string,
  latest: string,
  resolve: () => void,
) {
  if ($("#modal")) {
    modalError(
      new Error(
        "另有编辑发生版本冲突。当前弹窗内容仍保留，关闭后请再次保存并比较版本。",
      ),
    );
    return;
  }
  modal(
    title,
    `<p>当前输入已保留。请比较内容，再决定如何合并；不会自动覆盖服务器版本。</p><div class="diff"><section><h3>你的未保存内容</h3><pre>${esc(mine)}</pre></section><section><h3>服务器当前内容</h3><pre>${esc(latest)}</pre></section></div><button class="primary" id="resolve-conflict">基于最新版本继续编辑</button>`,
    (dialog) => {
      $("#resolve-conflict")!.onclick = () => {
        resolve();
        dialog.close();
        render();
        inform("已保留你的内容并更新版本基线，请检查、合并后再保存。");
      };
    },
  );
}
function jobForm(j: Obj, prefix: string) {
  return `<label>公司<input id="${prefix}-company" name="company" required maxlength="500" value="${esc(j.company)}"></label><label>岗位名称<input id="${prefix}-title" name="title" required maxlength="500" value="${esc(j.title)}"></label><label>JD 正文<textarea id="${prefix}-jd" name="jd" required>${esc(j.jd)}</textarea></label><label>原始链接（可选）<input id="${prefix}-url" name="url" type="url" value="${esc(j.url)}" placeholder="https://..."></label>`;
}
function bufferFor(r: Obj): Obj {
  if (!resumeBuffers.has(r.id))
    resumeBuffers.set(r.id, {
      content: r.content,
      revision: r.revision,
      dirty: false,
    });
  return resumeBuffers.get(r.id)!;
}
function legacyResumePage() {
  const r = currentResume();
  const b = r ? bufferFor(r) : null;
  return `<div class="page-title"><div><h2>早期文字稿与投递</h2></div><label>目标岗位<select id="resume-job"><option value="">请选择岗位</option>${state.jobs.map((j: Obj) => `<option value="${j.id}" ${j.id === jobId ? "selected" : ""}>${esc(j.title)} · ${esc(j.company)}${j.status !== "active" ? "（已归档）" : ""}</option>`).join("")}</select></label></div>${!r ? '<div class="empty">请先添加或选择一个岗位，再开始编辑。</div><button class="primary" data-page="jobs">前往目标岗位</button>' : `<div class="resume-grid"><section class="editor-card"><div class="editor-label"><span>当前工作稿</span><small id="draft-version">版本 ${b!.revision}</small></div><label for="resume-text">简历正文</label><textarea id="resume-text" placeholder="可直接手动填写简历，无需先运行 AI。">${esc(b!.content)}</textarea><div class="form-actions"><span class="muted" id="autosave">${b!.dirty ? "有未保存修改" : "已保存；输入后自动保存"}</span><button class="secondary" id="save-resume">保存手改</button></div><button class="primary full" id="save-version">保存正式版本</button></section><section class="side-card"><h3>AI 简历适配</h3><p class="muted">每轮使用当前职业资料、目标 JD 与本轮指令。当前手改草稿不自动发送；可用新的指令重新生成提案。</p><button class="primary full" id="analyze-resume" ${currentJob()?.status !== "active" ? "disabled" : ""}>生成简历提案</button><h3>正式版本与 PDF</h3>${versionsHtml(r.id)}</section></div>${runsHtml("resume", jobId)}<section class="side-card applications"><h2>实际投递记录</h2><p class="muted">这里只登记已经发生的投递，不会对外发送任何材料。</p>${applicationsHtml(jobId)}</section>`}`;
}
function versionsHtml(resumeId: string) {
  return (
    state.versions
      .filter((v: Obj) => v.resume_id === resumeId)
      .map((v: Obj, i: number) => {
        const a = state.artifacts.find((a: Obj) => a.version_id === v.id);
        return `<div class="version"><div><b>${date(v.created_at)}</b><small>工作稿版本 ${v.draft_revision}</small><details><summary>查看保存的正文</summary><pre>${esc(v.content)}</pre></details></div><div>${a ? `<a href="/api/artifacts/${a.id}" target="_blank" rel="noopener" class="text-btn">预览 PDF</a><a href="/api/artifacts/${a.id}?download=true" class="text-btn">下载 PDF</a>` : `<button class="text-btn" data-pdf="${v.id}">生成 PDF</button>`}<button class="secondary" data-application="${v.id}" ${a ? "" : "disabled"}>记录投递</button></div></div>`;
      })
      .join("") ||
    '<p class="muted">先保存正式版本，再生成 PDF。保存版本不会自动记录投递。</p>'
  );
}
function frozenResumeText(v: Obj): string {
  if (!v.document) return v.content || "";
  // Display frozen structured content as plain text; never execute its rich HTML.
  const plain = (value: unknown) => {
    const doc = new DOMParser().parseFromString(String(value || ""), "text/html");
    return doc.body.textContent || "";
  };
  const d = v.document;
  return [plain(d.profile.name), ...d.profile.contacts.map((c: Obj) => plain(c.content)),
    ...d.sections.flatMap((s: Obj) => [plain(s.title), ...s.items.flatMap((i: Obj) =>
      [i.content, i.organization, i.role, i.title, i.responsibility, i.school, i.major, i.date,
        ...(i.bullets || []).map((b: Obj) => b.content)].filter(Boolean).map(plain))])].join("\n");
}
function applicationsHtml(id: string) {
  return state.applications.filter((a: Obj) => a.job_id === id).map((a: Obj) => {
    const v = a.resume_snapshot;
    const name = v.document ? v.name : `早期文字稿 · 工作稿版本 ${v.draft_revision}`;
    return `<article class="application-row"><b>${esc(a.job_snapshot.company)} · ${esc(a.job_snapshot.title)}</b><p>${date(a.applied_at)} · ${esc(a.channel || "渠道未记录")}</p><p>投递版本：${esc(name)}</p><a href="/api/artifacts/${a.artifact_id}" target="_blank" rel="noopener">预览实际投递 PDF</a> <a href="/api/artifacts/${a.artifact_id}?download=true">下载实际投递 PDF</a><p>历史投递状态只读；当前阶段请查看机会。</p><details><summary>当时的简历正文</summary><pre>${esc(frozenResumeText(v))}</pre></details><details><summary>当时的岗位条件</summary><pre>${esc(a.job_snapshot.jd)}</pre></details></article>`;
  }).join("") || '<p class="muted">暂无实际投递。从已关联的版本登记已经发生的投递；关联版本不会自动创建投递。</p>';
}

function renderResult(result: Obj, sources: Obj[] = []) {
  const sourceLabel = (id: string) => {
    const source = sources.find((s) => s.id === id);
    if (!source) return id;
    const label =
      source.content?.title ||
      (source.purpose === "target_jd"
        ? "目标 JD"
        : id === "profile"
          ? "基础资料"
          : id);
    return `${label} · v${source.revision}`;
  };
  return `<div class="result">${Object.entries(result)
    .filter(([key]) => key !== "claims")
    .map(
      ([key, value]) =>
        `<div><b>${esc(fieldNames[key] || key)}</b><p class="preserve">${esc(Array.isArray(value) ? value.join("\n") || "未提供 / 待核实" : typeof value === "object" ? JSON.stringify(value) : value)}</p></div>`,
    )
    .join(
      "",
    )}</div><details><summary>判断类型与依据</summary>${(result.claims || []).map((c: Obj) => `<p><b>${({ Fact: "事实", Inference: "推断", Recommendation: "建议" } as Obj)[c.kind]}</b> ${esc(c.text)}<small>来源：${esc(c.source_ids.map(sourceLabel).join("、"))}</small></p>`).join("")}</details>`;
}
function runsHtml(kind: string, id: string) {
  const runs = state.runs.filter(
    (r: Obj) => r.kind === kind && r.job_id === id,
  );
  return runs.length
    ? `<section class="runs"><h2>${kind === "job" ? "岗位分析" : "简历建议"}</h2>${runs.map((r: Obj, i: number) => `<details class="analysis-box" ${i === 0 ? "open" : ""}><summary>${date(r.created_at)} · ${statusNames[r.status] || r.status} · ${r.provider?.mode === "test" ? "测试结果" : "真实 Provider"}</summary>${r.error ? `<p class="notice">${esc(r.error)}</p>` : ""}${r.status === "stale" ? '<p class="notice">资料或草稿已变化，本结果仅供历史查看，不能应用。</p>' : ""}${r.result ? renderResult(r.result, r.packet?.sources || []) : ""}${r.proposal ? `<details><summary>查看修改前后</summary><div class="diff"><section><h3>修改前</h3><pre>${esc(r.proposal.before)}</pre></section><section><h3>建议修改后</h3><pre>${esc(r.proposal.after)}</pre></section></div></details>${r.status === "succeeded" && r.proposal.status === "pending" ? `<p class="muted">请核对每一项职业事实，再确认采用。</p><button class="primary" data-proposal="${r.proposal.id}">确认应用提案</button>` : r.proposal.status === "applied" ? "<p>提案已确认应用</p>" : ""}` : ""}<details><summary>本轮资料包与版本</summary><pre>${esc(JSON.stringify(r.packet, null, 2))}</pre></details><details><summary>实际 Provider 请求体</summary><pre>${esc(JSON.stringify(r.payload, null, 2))}</pre></details></details>`).join("")}</section>`
    : "";
}
function render() {
  if (page === 'jobs' || page === 'progress') {
    const ctx = {state,domain,journey,id:jobId,filter:opportunityView,anchor:opportunityAnchor,communications:opportunityCommunications,timeline:opportunityTimeline,interviews:opportunityInterviews,offer:opportunityOffer,research:opportunityResearch};
    root.innerHTML=shell('jobs',opportunityHTML(ctx),notice,state.diagnostics?.provider?.mode==='test');
    history.replaceState(null,'','#opportunities'+(jobId?'/'+encodeURIComponent(jobId):'')+'?view='+opportunityView+(opportunityAnchor?'&tab='+encodeURIComponent(opportunityAnchor):''));
    bind();
    bindOpportunity(ctx,{api,refresh:load,go:(id,filter)=>{const changed=id!==jobId;jobId=id;if(filter)opportunityView=filter;opportunityAnchor='';if(changed)void load().then(render).catch(failure);else render();}});
    return;
  }
  const ep =
    journey.episodes.find((x: Obj) => x.id === ui.episodeId) ||
    journey.episodes[0];
  if (
    ui.workTab === "interview" &&
    !journey.notes.some(
      (n: Obj) =>
        n.scope_type === "episode" &&
        n.scope_id === ep?.id &&
        n.kind === "interview",
    )
  )
    ui.workTab = "action";
  if (
    ["action", "reflection"].includes(ui.jobTab) &&
    !journey.notes.some(
      (n: Obj) =>
        n.scope_type === "job" && n.scope_id === jobId && n.kind === ui.jobTab,
    )
  )
    ui.jobTab = "jd";
  root.innerHTML = shell(
    page,
    view(
      page,
      {
        state,
        knowledge,
        domain,
        workDomain,
        journey,
        jobId,
        editorVersions,
        profileBuffer,
        jobBuffers,
        planBuffers,
      },
      { runsHtml, legacyResumePage, modeText, applicationsHtml },
    ),
    notice,
    state.diagnostics?.provider?.mode === "test",
  );
  bind();
}
async function navigate(next: Page, id = jobId) {
  if (!(await flushResume())) return;
  page = next;
  jobId = id;
  notice = "";
  if (page === "jobs" || page === "progress") await loadOpportunityScope(jobId);
  if (page === "profile") knowledgeUI.tab = "profile";
  if (page === "profile" || (page === "wiki" && knowledgeUI.tab === "profile")) state.profile = (await api("/state")).profile;
  if (page === "resume") {
    const v = await api("/editor/versions");
    editorVersions = Array.isArray(v) ? v : v.versions;
  }
  if (page === "resume" && ui.materialTab === "legacy" && jobId)
    await ensureResume();
  history.replaceState(
    null,
    "",
    "#" +
      page +
      ((page === "jobs" || page === "progress") && jobId
        ? "/" + jobId
        : page === "work" && ui.episodeId
          ? "/" + ui.episodeId
          : ""),
  );
  render();
}
async function ensureResume() {
  const r = await api("/resumes", { job_id: jobId });
  const index = state.resumes.findIndex((x: Obj) => x.id === r.id);
  if (index < 0) state.resumes.push(r);
  else state.resumes[index] = r;
  if (!resumeBuffers.get(r.id)?.dirty)
    resumeBuffers.set(r.id, {
      content: r.content,
      revision: r.revision,
      dirty: false,
    });
}
async function saveProfile() {
  const b = profileBuffer || { ...state.profile };
  const sent = b.content;
  try {
    const p = await api("/profile", {
      content: sent,
      expected_revision: b.revision,
    });
    state.profile = p;
    if (profileBuffer?.content === sent) profileBuffer = null;
    else if (profileBuffer) profileBuffer.revision = p.revision;
    await load();
    render();
    inform("个人资料已保存。");
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      await load();
      comparison("个人资料存在新版本", b.content, state.profile.content, () => {
        profileBuffer = { ...b, revision: state.profile.revision };
      });
    } else failure(e);
  }
}
function editJobDialog() {
  const j = currentJob();
  if (!j) return;
  const b = jobBuffers.get(j.id) || { ...j };
  modal(
    "编辑岗位",
    `<form id="edit-job"><fieldset>${jobForm(b, "job")}</fieldset><div id="job-conflict"></div><button type="submit" class="primary full">保存岗位</button></form>`,
    (dialog) => {
      dialog.dataset.entityId = j.id;
      const form = dialog.querySelector<HTMLFormElement>("form")!;
      const fields = form.querySelector("fieldset")!;
      let saved = false;
      form.oninput = () => {
        Object.assign(b, Object.fromEntries(new FormData(form).entries()));
        jobBuffers.set(j.id, b);
      };
      form.onsubmit = async (event) => {
        event.preventDefault();
        const button = form.querySelector<HTMLButtonElement>(
          "button[type=submit]",
        )!;
        if (button.disabled) return;
        button.disabled = true;
        fields.disabled = true;
        try {
          if (!saved) {
            await api("/jobs/" + j.id, { ...b, expected_revision: b.revision });
            saved = true;
            jobBuffers.delete(j.id);
          }
          await load();
          dialog.close();
          render();
          inform("岗位已保存。");
        } catch (error) {
          if (error instanceof ApiError && error.status === 409) {
            try {
              await load();
            } catch {
              modalError(
                new Error(
                  "检测到岗位版本冲突，但暂时无法读取最新内容。输入已保留，请重试保存以加载比较。",
                ),
              );
              return;
            }
            const latest = state.jobs.find((x: Obj) => x.id === j.id);
            const box = dialog.querySelector("#job-conflict")!;
            box.innerHTML = `<p class="notice">岗位已在另一个窗口更新。请比较后合并。</p><div class="diff"><pre>${esc([b.company, b.title, b.jd, b.url].join("\n"))}</pre><pre>${esc([latest.company, latest.title, latest.jd, latest.url].join("\n"))}</pre></div><button class="secondary" type="button">保留输入，基于最新版本继续</button>`;
            box.querySelector("button")!.onclick = () => {
              b.revision = latest.revision;
              jobBuffers.set(j.id, b);
              box.innerHTML = "";
            };
          } else {
            modalError(error);
            if (saved) button.textContent = "刷新已保存的岗位";
          }
        } finally {
          button.disabled = false;
          fields.disabled = saved;
        }
      };
    },
  );
}
function addJob() {
  modal(
    "添加目标岗位",
    `<form id="new-job">${jobForm({}, "new")}<button class="primary full" type="submit">保存岗位</button></form>`,
    (dialog) => {
      $("#new-job")!.onsubmit = async (event) => {
        event.preventDefault();
        const button = dialog.querySelector<HTMLButtonElement>(
          "button[type=submit]",
        )!;
        button.disabled = true;
        const form = new FormData($("#new-job") as HTMLFormElement);
        try {
          const j = await api("/jobs", Object.fromEntries(form.entries()));
          jobId = j.id;
          page = "jobs";
          await load();
          dialog.close();
          history.replaceState(null, "", "#jobs/" + jobId);
          render();
          inform("岗位已添加。");
        } catch (e) {
          modalError(e);
          button.disabled = false;
        }
      };
    },
  );
}
function planText(p: Obj) {
  return `阶段：${stageLabels[p.stage] || "筛选"}\n下一步：${p.next_action || "未填写"}\n日期：${p.due_date || "未设置"}`;
}
const stageLabels: Obj = {
  screening: "筛选",
  research: "研究",
  resume: "简历",
  outreach: "沟通",
  applied: "已投递",
  interview: "面试",
  offer: "Offer",
  closed: "结束",
};
function editPlan() {
  const j = currentJob();
  if (!j) return;
  const p = planBuffers.get(j.id) ||
    journey.plans.find((x: Obj) => x.job_id === j.id) || {
      stage: "screening",
      next_action: "",
      due_date: "",
      revision: 0,
    };
  let expected = p.revision,
    saved = false;
  modal(
    "下一步",
    `<form id="plan-form"><fieldset><label>当前阶段<select name="stage">${Object.entries(
      stageNames,
    )
      .map(
        ([key, label]) =>
          `<option value="${key}" ${p.stage === key ? "selected" : ""}>${label}</option>`,
      )
      .join(
        "",
      )}</select></label><label>下一步<input name="next_action" required maxlength="500" value="${esc(p.next_action)}" placeholder="具体要做什么"></label><label>日期<input type="date" name="due_date" value="${esc(p.due_date)}"></label></fieldset><p class="muted">阶段仅作计划标记，不会登记实际投递。</p><div id="plan-conflict"></div><button class="primary full" type="submit">保存下一步</button></form>`,
    (dialog) => {
      dialog.dataset.entityId = j.id;
      const form = dialog.querySelector<HTMLFormElement>("form")!,
        fields = form.querySelector("fieldset")!;
      form.oninput = () =>
        planBuffers.set(j.id, {
          ...p,
          ...Object.fromEntries(new FormData(form).entries()),
          revision: expected,
        });
      form.onsubmit = async (event) => {
        event.preventDefault();
        const button = form.querySelector<HTMLButtonElement>(
          "button[type=submit]",
        )!;
        if (button.disabled) return;
        const mine = {
          ...p,
          ...Object.fromEntries(new FormData(form).entries()),
        };
        planBuffers.set(j.id, { ...mine, revision: expected });
        button.disabled = true;
        fields.disabled = true;
        try {
          if (!saved) {
            await api("/journey/plans/" + j.id, {
              ...mine,
              expected_revision: expected,
            });
            saved = true;
            planBuffers.delete(j.id);
          }
          await load();
          dialog.close();
          render();
          inform("下一步已保存。");
        } catch (error) {
          if (error instanceof ApiError && error.status === 409) {
            try {
              await load();
            } catch {
              modalError(
                new Error(
                  "检测到计划版本冲突，但暂时无法读取最新内容。输入已保留，请重试保存以加载比较。",
                ),
              );
              return;
            }
            const latest = journey.plans.find(
              (x: Obj) => x.job_id === j.id,
            ) || { revision: 0 };
            const box = dialog.querySelector("#plan-conflict")!;
            box.innerHTML = `<p class="notice">计划已更新。请比较后再保存。</p><div class="diff"><pre>${esc(planText(mine))}</pre><pre>${esc(planText(latest))}</pre></div><button class="secondary" type="button">保留输入，基于最新版本继续</button>`;
            box.querySelector("button")!.onclick = () => {
              expected = latest.revision;
              planBuffers.set(j.id, { ...mine, revision: expected });
              box.innerHTML = "";
            };
          } else {
            modalError(error);
            if (saved) button.textContent = "刷新已保存的计划";
          }
        } finally {
          button.disabled = false;
          fields.disabled = saved;
        }
      };
    },
  );
}
function episodeFields(e: Obj = {}) {
  return `<label>公司<input name="company" required maxlength="500" value="${esc(e.company)}"></label><label>角色 / 职位<input name="role" required maxlength="500" value="${esc(e.role)}"></label><label>开始日期<input name="start_date" type="date" value="${esc(e.start_date)}"></label><label>结束日期<input name="end_date" type="date" value="${esc(e.end_date)}"></label><label>阶段重点<textarea name="focus" maxlength="100000">${esc(e.focus)}</textarea></label>`;
}
function addEpisode() {
  editEpisode();
}
function editEpisode(id?: string) {
  const e = id ? journey.episodes.find((x: Obj) => x.id === id) : {};
  if (!e) return;
  let expected = e.revision;
  let saved = false;
  modal(
    id ? "编辑工作卡" : "新建工作卡",
    `<form id="episode-form"><fieldset>${episodeFields(e)}</fieldset><div id="episode-conflict"></div><button class="primary full" type="submit">${id ? "保存修改" : "保存工作卡"}</button></form>`,
    (dialog) => {
      dialog.dataset.entityId = id || "";
      const form = dialog.querySelector<HTMLFormElement>("form")!;
      const fields = form.querySelector("fieldset")!;
      form.onsubmit = async (event) => {
        event.preventDefault();
        const button = form.querySelector<HTMLButtonElement>(
          "button[type=submit]",
        )!;
        if (button.disabled) return;
        const mine = Object.fromEntries(new FormData(form).entries());
        button.disabled = true;
        fields.disabled = true;
        try {
          if (!saved) {
            const result = await api(
              "/journey/episodes" + (id ? "/" + id : ""),
              { ...mine, expected_revision: expected },
            );
            ui.episodeId = result.id;
          }
          page = "work";
          saved = true;
          await load();
          dialog.close();
          history.replaceState(null, "", "#work/" + ui.episodeId);
          render();
          inform("工作卡已保存。");
        } catch (error) {
          if (error instanceof ApiError && error.status === 409 && id) {
            await load();
            const latest = journey.episodes.find((x: Obj) => x.id === id);
            const box = dialog.querySelector("#episode-conflict")!;
            const description = (v: Obj) =>
              `${v.company} · ${v.role}\n${v.start_date || "未设开始日期"} — ${v.end_date || "至今"}\n${v.focus}`;
            box.innerHTML = `<p class="notice">工作卡在另一个窗口已更新。输入已保留，请比较后再保存。</p><div class="diff"><section><h3>你的输入</h3><pre>${esc(description(mine))}</pre></section><section><h3>当前保存内容</h3><pre>${esc(description(latest))}</pre></section></div><button type="button" class="secondary">保留输入，基于最新版本继续编辑</button>`;
            box.querySelector("button")!.onclick = () => {
              expected = latest.revision;
              box.innerHTML = "";
            };
          } else {
            modalError(
              saved
                ? new Error(
                    "工作卡已写入本机，但刷新失败。输入暂时锁定，请重试刷新已保存内容。",
                  )
                : error,
            );
            if (saved) button.textContent = "刷新已保存的工作卡";
          }
        } finally {
          button.disabled = false;
          fields.disabled = saved;
        }
      };
    },
  );
}
function exportEpisode(id: string) {
  const anchor = document.createElement("a");
  anchor.href = "/api/journey/episodes/" + encodeURIComponent(id) + "/export";
  anchor.download = "career-stage.md";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  inform("已请求下载阶段记录（Markdown），内容包含原文、更正视图和修订历史。");
}
function addJourneyNote(scope: string, id: string, kind?: string) {
  let request: Obj | null = null;
  const kinds = kind
    ? [kind]
    : scope === "episode"
      ? ["action", "collaboration", "reflection", "interview"]
      : [
          "research",
          "communication",
          "interview",
          "offer",
          "action",
          "reflection",
        ];
  const labels: Obj = {
    action: "事务",
    collaboration: "协作",
    reflection: "收获",
    research: "研究",
    communication: "沟通",
    interview: "面试",
    offer: "Offer",
  };
  const prompts: Obj = {
    research: "公司主体、信息来源与日期、已知事实、待确认问题。",
    communication: "对方原话、我的回应、沟通目标、接下来要确认什么。",
    interview: "面试问题、我的回答、追问与反馈、下次如何改进。",
    offer: "薪资条款、固定与浮动部分、兑现条件、期限、个人底线与未知项。",
    action: "目标、本人动作、结果、证据、待解决问题。",
    collaboration: "参与者与职责、聊天或交接原文、分歧、待验证的解释。",
    reflection:
      "发生了什么、学到什么、下次如何调整；哪些事实值得补进个人资料。",
  };
  modal(
    kind ? "记录" + noteNames[kind] : "追加记录",
    `<form id="journey-note-form"><fieldset>${kind ? `<input type="hidden" name="kind" value="${esc(kind)}">` : `<label>类型<select name="kind">${kinds.map((k) => `<option value="${k}">${labels[k]}</option>`).join("")}</select></label>`}<label>标题<input name="title" maxlength="500"></label><label>内容<textarea name="content" required maxlength="100000" placeholder="${esc(prompts[kind || kinds[0]])}"></textarea></label>${scope === "job" ? `<label>关联投递（可选）<select name="submission_id"><option value="">未关联投递</option>${state.applications.filter((a: Obj) => a.job_id === id).map((a: Obj) => `<option value="${esc(a.id)}">${esc(a.resume_snapshot?.name || "早期文字版本")} · ${date(a.applied_at)}</option>`).join("")}</select></label>` : ""}</fieldset><p class="muted">保存在当前任务中；不会自动变成个人资料或 AI 分析依据。</p><button class="primary full" type="submit">保存记录</button></form>`,
    (dialog) => {
      dialog.dataset.entityId = id;
      const form = dialog.querySelector<HTMLFormElement>("form")!;
      const fields = form.querySelector("fieldset")!;
      form.onsubmit = async (event) => {
        event.preventDefault();
        const button = form.querySelector<HTMLButtonElement>(
          "button[type=submit]",
        )!;
        if (button.disabled) return;
        if (!request) {
          const values = Object.fromEntries(new FormData(form).entries());
          if (!String(values.content || "").trim()) {
            modalError(new Error("请填写记录内容。"));
            return;
          }
          request = {
            scope_type: scope,
            scope_id: id,
            ...values,
            submission_id: values.submission_id || null,
            idempotency_key: crypto.randomUUID(),
          };
        }
        button.disabled = true;
        fields.disabled = true;
        try {
          const note = await api("/journey/notes", request);
          ui.selectedNote = note.id;
          await load();
          dialog.close();
          render();
          inform("记录已保存。");
        } catch (error) {
          modalError(error);
          button.textContent = "重试保存同一条记录";
          if (error instanceof ApiError && [404, 422].includes(error.status)) {
            request = null;
            fields.disabled = false;
            button.textContent = "保存记录";
          }
        } finally {
          button.disabled = false;
        }
      };
    },
  );
}
function workForm(title: string, fields: string, submit: string, save: (values: Obj) => Promise<void>) {
  modal(title, `<form data-work-form><fieldset>${fields}</fieldset><p class="muted">成果和证据不会自动进入个人 Wiki；需要后续显式整理并确认。</p><button class="primary full" type="submit">${submit}</button></form>`, (dialog) => {
    const form = dialog.querySelector<HTMLFormElement>("form")!;
    form.onsubmit = async (event) => {
      event.preventDefault();
      const button = form.querySelector<HTMLButtonElement>("button[type=submit]")!;
      if (button.disabled) return;
      button.disabled = true;
      try { await save(Object.fromEntries(new FormData(form).entries())); await load(); dialog.close(); render(); inform("已保存工作域记录。"); }
      catch (error) { modalError(error); button.disabled = false; }
    };
  });
}
function createWorkProject(episodeId: string) {
  workForm("新建项目", `<label>项目名称<input name="name" required maxlength="500"></label><label>项目说明<textarea name="description" maxlength="100000"></textarea></label>`, "保存项目", (v) => api("/work/projects", { ...v, scope_type: "employment", scope_id: "employment:" + episodeId, idempotency_key: crypto.randomUUID() }));
}
function createWorkEvent(projectId: string) {
  workForm("记录工作事件", `<label>事件标题<input name="title" required maxlength="500"></label><label>事件类型<input name="kind" required maxlength="100" value="进展"></label><label>原文<textarea name="content" required maxlength="100000"></textarea></label>`, "保存事件", (v) => api("/work/events", { ...v, project_id: projectId, idempotency_key: crypto.randomUUID() }));
}
function createWorkAchievement(projectId: string) {
  workForm("记录成果", `<label>成果标题<input name="title" required maxlength="500"></label><label>成果内容<textarea name="content" required maxlength="100000"></textarea></label>`, "保存成果", (v) => api("/work/achievements", { ...v, project_id: projectId, idempotency_key: crypto.randomUUID() }));
}
function createWorkEvidence(projectId: string) {
  workForm("添加证据", `<label>证据标题<input name="title" required maxlength="500"></label><label>证据类型<input name="source_type" required maxlength="100" value="文档"></label><label>证据原文<textarea name="content" required maxlength="100000"></textarea></label>`, "保存证据", (v) => api("/work/evidence", { ...v, scope_type: "project", scope_id: projectId, idempotency_key: crypto.randomUUID() }));
}
function linkWorkEvidence(projectId: string) {
  const achievements = workDomain.achievements.filter((a: Obj) => a.project_id === projectId);
  const evidence = workDomain.evidence.filter((x: Obj) => x.scope_type === "project" && x.scope_id === projectId);
  if (!achievements.length || !evidence.length) { inform("请先记录成果和项目证据。"); return; }
  workForm("关联成果证据", `<label>成果<select name="achievement_id">${achievements.map((a: Obj) => `<option value="${esc(a.id)}">${esc(a.title)}</option>`).join("")}</select></label><label>证据<select name="evidence_id">${evidence.map((x: Obj) => `<option value="${esc(x.id)}">${esc(x.title)}</option>`).join("")}</select></label>`, "关联证据", (v) => api("/work/evidence-links", { ...v, idempotency_key: crypto.randomUUID() }));
}
function addWorkPerson(projectId: string) {
  workForm("添加项目参与者", `<label>姓名<input name="name" required maxlength="500"></label><label>角色<input name="role" maxlength="500"></label><label>项目内职责<input name="participant_role" maxlength="500"></label>`, "保存参与者", async (v) => { const person = await api("/work/persons", { name: v.name, role: v.role, idempotency_key: crypto.randomUUID() }); return api("/work/projects/" + encodeURIComponent(projectId) + "/participants", { person_id: person.id, role: v.participant_role || "", idempotency_key: crypto.randomUUID() }); });
}
async function changeJobStatus(status: string) {
  const j = currentJob();
  if (jobBuffers.has(j.id)) {
    inform("请先保存岗位修改，再更改状态。");
    return;
  }
  try {
    await api("/jobs/" + j.id, { ...j, status, expected_revision: j.revision });
    await load();
    ui.jobFilter = status === "active" ? "active" : "archived";
    render();
  } catch (e) {
    failure(e);
  }
}
async function flushResume(): Promise<boolean> {
  clearTimeout(saveTimer);
  if (saving) {
    const ok = await saving;
    return ok ? flushResume() : false;
  }
  const r = currentResume();
  if (!r) return true;
  const b = bufferFor(r);
  if (!b.dirty) return true;
  if (b.conflict) {
    await load();
    const latest = state.resumes.find((x: Obj) => x.id === r.id);
    comparison("简历存在新版本", b.content, latest.content, () => {
      b.revision = latest.revision;
      b.conflict = false;
    });
    return false;
  }
  const text = b.content;
  const revision = b.revision;
  saving = (async () => {
    try {
      const saved = await api("/resumes/" + r.id, {
        content: text,
        expected_revision: revision,
      });
      b.revision = saved.revision;
      b.dirty = b.content !== text;
      Object.assign(r, saved);
      const label = $("#autosave");
      if (label) label.textContent = b.dirty ? "继续保存新修改…" : "已自动保存";
      const revLabel = $("#draft-version");
      if (revLabel) revLabel.textContent = "版本 " + b.revision;
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        b.conflict = true;
        await load();
        const latest = state.resumes.find((x: Obj) => x.id === r.id);
        comparison("简历存在新版本", b.content, latest.content, () => {
          b.revision = latest.revision;
          b.conflict = false;
        });
      } else failure(e);
      return false;
    }
  })();
  const ok = await saving;
  saving = null;
  return ok && b.dirty ? flushResume() : ok;
}
async function saveVersion() {
  if (!(await flushResume())) return;
  const r = currentResume();
  try {
    await api("/resumes/" + r.id + "/versions", {
      expected_revision: bufferFor(r).revision,
    });
    await load();
    render();
    inform("正式版本已保存，可生成 PDF。");
  } catch (e) {
    failure(e);
  }
}
async function createPdf(id: string) {
  try {
    await api("/versions/" + id + "/pdf", {});
    await load();
    render();
    inform("PDF 已生成并关联此版本。");
  } catch (e) {
    failure(e);
  }
}
async function prepareAnalysis(kind: "job" | "resume") {
  if (!(await flushResume())) return;
  if (profileBuffer || hasUnsavedProfile() || jobBuffers.has(jobId)) {
    inform("请先保存个人资料和当前岗位修改，再预览分析。");
    return;
  }
  await load();
  const selected = jobId;
  const eligible = knowledge.entries.filter(
    (x: Obj) =>
      x.status === "active" &&
      (x.scope_type === "personal" ||
        (x.scope_type === "job" && x.scope_id === selected)),
  );
  const choices = eligible
    .map((x: Obj) => {
      const mandatory =
        x.scope_type === "personal" &&
        ["goal", "constraint"].includes(x.entry_type);
      return `<label class="wiki-choice"><input type="checkbox" data-wiki-choice value="${esc(x.id)}" ${mandatory ? "checked" : ""} ${mandatory ? "disabled" : ""}><span>${esc(x.title)}<small>${esc(entryNames[x.entry_type])} · v${x.revision}${mandatory ? " · 必选" : ""}</small></span></label>`;
    })
    .join("");
  modal(
    kind === "job" ? "分析岗位" : "生成简历提案",
    `<p>${esc(modeText())}</p><fieldset id="analysis-input"><div class="selection-list">${choices || '<p class="muted">尚无可选 Wiki 条目，当前只使用已保存基础资料。</p>'}</div><label>本轮调整指令（可选）<textarea id="instruction" placeholder="例如：重点看实际参与范围；不要添加未知的量化成果。"></textarea></label></fieldset><button class="primary full" id="preview-context">预览本轮资料</button><div id="context-preview"></div>`,
    (dialog) => {
      $("#preview-context")!.onclick = async () => {
        const body = {
          job_id: selected,
          kind,
          wiki_ids: [
            ...dialog.querySelectorAll<HTMLInputElement>(
              "[data-wiki-choice]:checked",
            ),
          ].map((x) => x.value),
          instruction: ($("#instruction") as HTMLTextAreaElement).value,
        };
        const previewButton = $("#preview-context") as HTMLButtonElement;
        if (previewButton.disabled) return;
        previewButton.disabled = true;
        try {
          const packet = await api("/context", body);
          const key = crypto.randomUUID();
          $("#context-preview")!.innerHTML =
            `<h3>本次发送范围</h3><ul>${packet.sources.map((s: Obj) => `<li>${esc(s.purpose === "target_jd" ? "当前 JD" : s.id === "profile" ? "基础资料" : s.content?.title || s.id)} · v${s.revision}</li>`).join("")}</ul><p>请核对本轮依据，返回可调整选材和指令。</p>${packet.sources.map((source: Obj) => `<section class="context-source"><h4>${esc(source.purpose === "target_jd" ? "当前 JD" : source.id === "profile" ? "基础资料" : source.content?.title || "Wiki 条目")}</h4><div class="prose">${esc(typeof source.content === "string" ? source.content : source.content?.content || source.content?.jd || JSON.stringify(source.content, null, 2))}</div></section>`).join("")}<button class="secondary" id="adjust-context">返回调整</button><details><summary>技术详情：完整资料包</summary><pre>${esc(JSON.stringify(packet, null, 2))}</pre></details><button class="primary full" id="send-analysis">确认发送${state.diagnostics.provider.mode === "test" ? "（测试模式）" : "给 Provider"}</button>`;
          (
            dialog.querySelector("#analysis-input") as HTMLFieldSetElement
          ).disabled = true;
          $("#adjust-context")!.onclick = () => {
            (dialog.querySelector("#analysis-input") as HTMLFieldSetElement).disabled = false;
            $("#context-preview")!.innerHTML = "";
            previewButton.disabled = false;
          };
          $("#send-analysis")!.onclick = async () => {
            const button = $("#send-analysis") as HTMLButtonElement;
            button.disabled = true;
            button.textContent = "正在分析，请稍候…";
            ($("#adjust-context") as HTMLButtonElement).disabled = true;
            try {
              const result = await api("/analysis", {
                ...body,
                expected_epoch: packet.epoch,
                idempotency_key: key,
              });
              await load();
              dialog.close();
              render();
              inform(
                result.status === "succeeded"
                  ? "分析已返回，请审阅依据和未知项。"
                  : statusNames[result.status] || result.status,
              );
            } catch (e) {
              modalError(e);
              button.disabled = false;
              button.textContent = "检查结果 / 重试同一请求";
            }
          };
        } catch (e) {
          modalError(e);
          previewButton.disabled = false;
        }
      };
    },
  );
}
async function applyProposal(id: string) {
  if (!(await flushResume())) return;
  try {
    const result = await api("/proposals/" + id + "/apply", {});
    resumeBuffers.set(result.id, {
      content: result.content,
      revision: result.revision,
      dirty: false,
    });
    await load();
    render();
    inform("已确认应用到简历工作稿，个人资料正本未改动。");
  } catch (e) {
    await load();
    render();
    failure(e);
  }
}
function recordApplication(versionId: string, opportunityId?: string) {
  const v = editorVersions.find((v: Obj) => v.id === versionId) || state.versions.find((v: Obj) => v.id === versionId);
  const owner = opportunityId || v?.opportunity_id || v?.job_id;
  if (!owner) { inform("请先选择机会，再记录已投递。"); return; }
  location.hash = '#opportunities/' + encodeURIComponent(owner);
}
async function screenshotData(input: HTMLInputElement) {
  const file = input.files?.[0];
  if (!file) return undefined;
  if (
    file.size > 5 * 1024 * 1024 ||
    !["image/png", "image/jpeg"].includes(file.type)
  )
    throw new Error("截图仅支持 5MB 以内的 PNG / JPEG。");
  const data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("无法读取截图"));
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.readAsDataURL(file);
  });
  return { name: file.name, media_type: file.type, data_base64: data };
}
function captureFeedback() {
  const capturedPage = page;
  const entity =
    document.querySelector<HTMLDialogElement>("#modal")?.dataset.entityId ||
    (["jobs", "progress"].includes(page)
      ? jobId
      : page === "work"
        ? ui.episodeId || journey.episodes[0]?.id || ""
        : page === "wiki"
          ? knowledgeUI.selected ||
            (knowledgeUI.tab === "profile" ? "profile" : "")
          : page === "profile" ||
              (page === "resume" && ui.materialTab === "profile")
            ? "profile"
            : page === "resume" && ui.materialTab === "legacy"
              ? jobId
              : "");
  modal(
    "记录反馈",
    `<form id="feedback-form"><label>此刻的感受<textarea id="feedback-text" required placeholder="随手记一句就好。" autofocus></textarea></label><label>截图（可选）<input id="feedback-screenshot" type="file" accept="image/png,image/jpeg"></label><p class="muted">仅保存你输入的文字、选中的截图和当前位置，不采集页面正文。</p><button class="primary full" type="submit">保存并关闭</button></form>`,
    (dialog) => {
      $("#feedback-form")!.onsubmit = async (event) => {
        event.preventDefault();
        const button = dialog.querySelector<HTMLButtonElement>(
          "button[type=submit]",
        )!;
        button.disabled = true;
        try {
          await api("/feedback", {
            text: ($("#feedback-text") as HTMLTextAreaElement).value,
            current_page: capturedPage,
            entity_id: entity,
            screenshot: await screenshotData(
              $("#feedback-screenshot") as HTMLInputElement,
            ),
          });
          await load();
          dialog.close();
          if (page === "feedback") render();
          inform("反馈已保存。可以继续当前任务。");
        } catch (e) {
          modalError(e);
          button.disabled = false;
        }
      };
    },
  );
}
function addNote(id: string) {
  modal(
    "补充反馈",
    '<form id="note-form"><label>补充内容<textarea id="note-text" required></textarea></label><button type="submit" class="primary full">保存补充</button></form>',
    (dialog) => {
      $("#note-form")!.onsubmit = async (event) => {
        event.preventDefault();
        const button = dialog.querySelector<HTMLButtonElement>(
          "button[type=submit]",
        )!;
        button.disabled = true;
        try {
          await api("/feedback/" + id + "/notes", {
            text: ($("#note-text") as HTMLTextAreaElement).value,
          });
          await load();
          dialog.close();
          render();
        } catch (e) {
          modalError(e);
          button.disabled = false;
        }
      };
    },
  );
}
function bind() {
  bindSidebarOrder();
  if (page === "diagnostics") bindAiSettings({state, api, modal, modalError, load, render, inform});
  bindProfile({state, api, modal, modalError, load, render, navigate: async () => {
    knowledgeUI.tab = "candidates"; knowledgeUI.scope = "all"; knowledgeUI.category = "all"; await navigate("wiki");
  }});
  bindRecords({notes: journey.notes, api, modal, modalError, load, render, showCandidate: async (id) => {
    knowledgeUI.tab = "candidates"; knowledgeUI.scope = "all"; knowledgeUI.category = "all"; knowledgeUI.selected = id; await navigate("wiki");
  }});
  document.querySelectorAll<HTMLElement>("[data-origin-record]").forEach(el => el.onclick = () => {
    const n = journey.notes.find((n: Obj) => n.id === el.dataset.originRecord);
    if (!n) return;
    ui.selectedNote = n.id;
    if (n.scope_type === "job") {ui.jobTab = n.kind; void navigate("jobs", n.scope_id).catch(failure);}
    else {ui.episodeId = n.scope_id; ui.workTab = n.kind; void navigate("work").catch(failure);}
  });
  bindKnowledge({
    api,
    modal,
    modalError,
    render,
    load,
    navigate,
    failure,
    getData: () => ({
      state,
      journey,
      knowledge,
      domain,
      jobId,
      editorVersions,
      page,
    }),
  });
  $("#toggle-sidebar")!.onclick = () => {
    ui.sidebar = !ui.sidebar;
    root
      .querySelector(".workspace")!
      .classList.toggle("sidebar-hidden", !ui.sidebar);
    (root.querySelector(".sidebar") as HTMLElement).inert = !ui.sidebar;
    const toggle = $("#toggle-sidebar")!;
    toggle.setAttribute("aria-expanded", String(ui.sidebar));
    toggle.setAttribute("aria-label", ui.sidebar ? "收起侧栏" : "展开侧栏");
  };
  $("#edit-job-dialog")?.addEventListener("click", editJobDialog);
  $("#edit-plan")?.addEventListener("click", editPlan);
  document.querySelectorAll<HTMLElement>("[data-primary-opportunity]").forEach((el) => {
    el.onclick = () => {
      const action = el.dataset.primaryOpportunity;
      if (action === "jd") editJobDialog();
      else if (action === "analysis") void prepareAnalysis("job");
      else if (action === "plan") editPlan();
    };
  });
  $("#show-legacy")?.addEventListener("click", () => {
    ui.materialTab = "legacy";
    void navigate("resume").catch(failure);
  });
  document.querySelectorAll<HTMLElement>("[data-tab-group]").forEach(
    (el) =>
      (el.onclick = () => {
        const group = el.dataset.tabGroup as
          | "jobTab"
          | "workTab"
          | "materialTab"
          | "jobFilter";
        void (async () => {
          if (!(await flushResume())) return;
          ui[group] = el.dataset.tab!;
          if (group === "materialTab") {
            page = "resume";
            if (ui.materialTab === "legacy" && jobId) await ensureResume();
          }
          if (group === "jobFilter") {
            const xs = state.jobs.filter((x: Obj) =>
              ui.jobFilter === "active"
                ? x.status === "active"
                : x.status !== "active",
            );
            if (!xs.some((x: Obj) => x.id === jobId)) jobId = xs[0]?.id || "";
          }
          render();
        })().catch(failure);
      }),
  );
  document.querySelectorAll<HTMLElement>("[data-open-episode]").forEach(
    (el) =>
      (el.onclick = () => {
        ui.episodeId = el.dataset.openEpisode!;
        if (el.dataset.originNote) ui.selectedNote = el.dataset.originNote;
        if (el.dataset.noteKind)
          ui.workTab = [
            "action",
            "collaboration",
            "reflection",
            "interview",
          ].includes(el.dataset.noteKind)
            ? el.dataset.noteKind
            : "reflection";
        void navigate("work").catch(failure);
      }),
  );
  document.querySelectorAll<HTMLSelectElement>("[data-record-picker]").forEach(
    (el) =>
      (el.onchange = () => {
        ui.selectedNote = el.value;
        render();
      }),
  );
  document.querySelectorAll<HTMLElement>("[data-select-note]").forEach(
    (el) =>
      (el.onclick = () => {
        ui.selectedNote = el.dataset.selectNote!;
        render();
      }),
  );
  document.querySelectorAll<HTMLElement>("[data-select-feedback]").forEach(
    (el) =>
      (el.onclick = () => {
        ui.selectedFeedback = el.dataset.selectFeedback!;
        render();
      }),
  );
  document.querySelectorAll<HTMLElement>("[data-page]").forEach(
    (el) =>
      (el.onclick = () => {
        void navigate(el.dataset.page as Page, (el.dataset.job || (el.dataset.page === "jobs" ? "" : jobId))).catch(
          failure,
        );
      }),
  );
  document.querySelectorAll<HTMLElement>("[data-job]").forEach(
    (el) =>
      (el.onclick = () => {
        if (el.dataset.originNote) ui.selectedNote = el.dataset.originNote;
        if (el.dataset.noteKind)
          ui.jobTab = [
            "research",
            "communication",
            "interview",
            "offer",
            "action",
            "reflection",
          ].includes(el.dataset.noteKind)
            ? el.dataset.noteKind
            : "jd";
        const j = state.jobs.find((x: Obj) => x.id === el.dataset.job);
        ui.jobFilter = j?.status === "active" ? "active" : "archived";
        void navigate("jobs", el.dataset.job).catch(failure);
      }),
  );
  $("#capture-feedback")!.onclick = captureFeedback;
  $("#add-job")?.addEventListener("click", addJob);
  $("#add-episode")?.addEventListener("click", addEpisode);
  $("#load-demo")?.addEventListener("click", () => {
    void (async () => {
      await api("/demo/load", {});
      await load();
      render();
      inform("全链路案例已装载；重复装载不会新增重复记录。");
    })().catch(failure);
  });
  $("#remove-demo")?.addEventListener("click", () => {
    if (!window.confirm("只删除带全链路案例标识的虚构记录和附件。确认删除？")) return;
    void (async () => {
      await api("/demo/remove", {});
      await load();
      render();
      inform("全链路案例已删除，你的资料未改动。");
    })().catch(failure);
  });
  document.querySelectorAll<HTMLElement>("[data-work-project]").forEach((el) => (el.onclick = () => createWorkProject(el.dataset.workProject!)));
  document.querySelectorAll<HTMLElement>("[data-work-event]").forEach((el) => (el.onclick = () => createWorkEvent(el.dataset.workEvent!)));
  document.querySelectorAll<HTMLElement>("[data-work-achievement]").forEach((el) => (el.onclick = () => createWorkAchievement(el.dataset.workAchievement!)));
  document.querySelectorAll<HTMLElement>("[data-work-evidence]").forEach((el) => (el.onclick = () => createWorkEvidence(el.dataset.workEvidence!)));
  document.querySelectorAll<HTMLElement>("[data-work-link-evidence]").forEach((el) => (el.onclick = () => linkWorkEvidence(el.dataset.workLinkEvidence!)));
  document.querySelectorAll<HTMLElement>("[data-work-person]").forEach((el) => (el.onclick = () => addWorkPerson(el.dataset.workPerson!)));
  document
    .querySelectorAll<HTMLElement>("[data-episode]")
    .forEach((el) => (el.onclick = () => editEpisode(el.dataset.episode!)));
  document
    .querySelectorAll<HTMLElement>("[data-export-episode]")
    .forEach(
      (el) => (el.onclick = () => exportEpisode(el.dataset.exportEpisode!)),
    );
  document.querySelectorAll<HTMLElement>("[data-add-note]").forEach(
    (el) =>
      (el.onclick = () => {
        const [scope, id, kind] = el.dataset.addNote!.split(":");
        addJourneyNote(scope, id, kind);
      }),
  );
  $("#save-profile")?.addEventListener("click", saveProfile);
  $("#profile-text")?.addEventListener("input", (event) => {
    profileBuffer ||= { ...state.profile };
    profileBuffer!.content = (event.target as HTMLTextAreaElement).value;
    const label = $("#profile-save-state");
    if (label) label.textContent = "未保存 · v" + state.profile.revision;
  });
  document.querySelectorAll<HTMLElement>("[data-job-status]").forEach(
    (el) =>
      (el.onclick = () => {
        void changeJobStatus(el.dataset.jobStatus!);
      }),
  );
  $("#open-resume")?.addEventListener("click", () => {
    void navigate("resume").catch(failure);
  });
  $("#resume-job")?.addEventListener("change", (event) => {
    void navigate("resume", (event.target as HTMLSelectElement).value).catch(
      failure,
    );
  });
  $("#resume-text")?.addEventListener("input", (event) => {
    const b = bufferFor(currentResume());
    b.content = (event.target as HTMLTextAreaElement).value;
    b.dirty = true;
    $("#autosave")!.textContent = "等待保存…";
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      void flushResume();
    }, 700);
  });
  $("#save-resume")?.addEventListener("click", () => {
    void flushResume()
      .then(async (ok) => {
        if (ok) {
          await load();
          render();
          inform("简历手改已保存。");
        }
      })
      .catch(failure);
  });
  $("#save-version")?.addEventListener("click", saveVersion);
  $("#analyze-job")?.addEventListener("click", () => {
    void prepareAnalysis("job");
  });
  $("#analyze-resume")?.addEventListener("click", () => {
    void prepareAnalysis("resume");
  });
  document.querySelectorAll<HTMLElement>("[data-pdf]").forEach(
    (el) =>
      (el.onclick = () => {
        void createPdf(el.dataset.pdf!);
      }),
  );
  document.querySelectorAll<HTMLElement>("[data-proposal]").forEach(
    (el) =>
      (el.onclick = () => {
        void applyProposal(el.dataset.proposal!);
      }),
  );
  document
    .querySelectorAll<HTMLElement>("[data-application]")
    .forEach(
      (el) => (el.onclick = () => recordApplication(el.dataset.application!, el.dataset.applicationJob)),
    );
  document
    .querySelectorAll<HTMLElement>("[data-note]")
    .forEach((el) => (el.onclick = () => addNote(el.dataset.note!)));
}
function readRoute() {
  const [path, query = ""] = location.hash.slice(1).split("?");
  const [p, raw = ""] = path.split("/");
  const id = decodeURIComponent(raw), params = new URLSearchParams(query);
  return {p:p === "opportunities" ? "jobs" : p,id,params};
}
function routeSelection(p: string, id: string, params: URLSearchParams) {
  if (p === "footprint" && params.get("record")) ui.selectedNote = params.get("record")!;
  if(p==='jobs'||p==='progress') {opportunityView=params.get('view')||opportunityView;opportunityAnchor=params.get('tab')||'';}
  if (p === "jobs" && ["jd","analysis","resume",...Object.keys(noteNames)].includes(params.get("tab") || "")) ui.jobTab = params.get("tab")!;
  if (p === "wiki" && id) {knowledgeUI.tab = "entries";knowledgeUI.scope = "all";knowledgeUI.category = "all";knowledgeUI.selected = id;}
}
async function start() {
  try {
    const {p,id,params} = readRoute();
    routeSelection(p,id,params);
    const initialPage = p === "home" || !p ? sidebarHome() : p;
    if (isPage(initialPage)) page = initialPage;
    if ((p === "home" || !p) && isPage(initialPage)) history.replaceState(null, "", `#${initialPage}`);
    if (page === "jobs" || page === "progress") jobId = id;
    await load();
    if (page !== "jobs" && page !== "progress")
      jobId = state.jobs.some((j: Obj) => j.id === id) ? id : activeJobs()[0]?.id || "";
    if (page === "jobs" || page === "progress")
      ui.jobFilter =
        state.jobs.find((j: Obj) => j.id === jobId)?.status === "active"
          ? "active"
          : "archived";
    if (page === "work") ui.episodeId = id || "";
    if (page === "profile") knowledgeUI.tab = "profile";
    render();
  } catch (e) {
    render();
    failure(e);
  }
}
window.addEventListener("hashchange", () => {
  void (async () => {
    const {p: rawRequested,id,params} = readRoute();
    const requested = rawRequested === "home" || !rawRequested ? sidebarHome() : rawRequested;
    if (!isPage(requested)) return;
    // Modal inputs stay in their owning task until the user closes the dialog.
    if (document.querySelector("dialog[open]") || !(await flushResume())) {
      history.replaceState(
        null,
        "",
        "#" +
          page +
          (page === "jobs"
            ? "/" + jobId
            : page === "work" && ui.episodeId
              ? "/" + ui.episodeId
              : ""),
      );
      inform("请先完成或关闭当前编辑，再切换链接。");
      return;
    }
    routeSelection(requested,id,params);
    if (requested === "work") ui.episodeId = id || "";
    const targetJob = (requested === 'jobs' || requested === 'progress') ? id : jobId;
    if (requested === "jobs" || requested === "progress")
      ui.jobFilter =
        state.jobs.find((j: Obj) => j.id === targetJob)?.status === "active"
          ? "active"
          : "archived";
    await navigate(requested as Page, targetJob);
  })().catch(failure);
});
void start();
