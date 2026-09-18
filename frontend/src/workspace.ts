import {
  knowledgeView,
  directoryView,
  opportunityObjects,
  resumeUses,
  knowledgeUI,
} from "./knowledge-ui";
import { profilePanel } from "./profile-ui";
import { aiSettingsView } from "./ai-config-ui";
type Row = Record<string, any>;
export const ui = {
  sidebar: !window.matchMedia("(max-width: 760px)").matches,
  jobTab: "jd",
  workTab: "action",
  materialTab: "versions",
  episodeId: "",
  selectedNote: "",
  selectedFeedback: "",
  jobFilter: "active",
};
export const stageNames: Row = {
  screening: "筛选",
  research: "研究",
  resume: "简历",
  outreach: "沟通",
  applied: "已投递",
  interview: "面试",
  offer: "Offer",
  closed: "结束",
};
export const noteNames: Row = {
  research: "研究",
  communication: "沟通",
  interview: "面试",
  offer: "Offer",
  action: "事项",
  collaboration: "协作",
  reflection: "收获",
};
const e = (v: any): string =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
const dt = (v: string) =>
  v
    ? new Date(v).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";
const icons: Row = {
  panel: "M4 4h16v16H4z M9 4v16",
  home: "M3 11l9-8 9 8 M5 9v12h14V9 M9 21v-7h6v7",
  jobs: "M4 7h16v14H4z M8 7V3h8v4 M4 12h16 M10 12v3h4v-3",
  resume: "M6 3h9l4 4v14H6z M14 3v5h5 M9 12h7 M9 16h7",
  work: "M3 7h7l2 2h9v11H3z M3 7V4h7l2 3",
  practice:
    "M12 3l2.8 5.7L21 10l-4.5 4.4 1 6.2L12 17.7l-5.5 2.9 1-6.2L3 10l6.2-1.3z",
  footprint: "M12 3a9 9 0 1 0 9 9 M12 6v6l4 2 M17 3h4v4",
  feedback: "M4 4h16v13H9l-5 4z M8 8h8 M8 12h5",
  plus: "M12 5v14 M5 12h14",
  settings: "M4 7h16 M4 17h16 M8 4v6 M16 14v6",
  arrow: "M5 12h14 M14 7l5 5-5 5",
};
export const icon = (name: string) =>
  `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${icons[name] || icons.resume}"/></svg>`;
const empty = (text: string) => `<div class="empty">${text}</div>`;
const tabs = (group: string, items: string[][], selected: string) =>
  `<div class="tabs" role="tablist">${items.map(([id, label]) => `<button role="tab" aria-selected="${id === selected}" data-tab-group="${group}" data-tab="${id}">${label}</button>`).join("")}</div>`;
const title = (name: string, actions = "") =>
  `<div class="pane-heading"><h2>${e(name)}</h2><div class="actions">${actions}</div></div>`;
const addNote = (scope: string, id: string, kind: string) =>
  `<button class="primary" data-add-note="${scope}:${e(id)}:${kind}">${icon("plus")}记录${noteNames[kind]}</button>`;
export const SIDEBAR_MODULES: [string, string][] = [
  ["home", "今天"], ["wiki", "职业 Wiki"], ["jobs", "机会"],
  ["resume", "简历工作台"], ["work", "任职"],
];
const sidebarStorageKey = "career.sidebar.module-order.v1";
function sidebarOrder(): [string, string][] {
  const ids = SIDEBAR_MODULES.map(([id]) => id);
  let saved: unknown = [];
  try { saved = JSON.parse(localStorage.getItem(sidebarStorageKey) || "[]"); } catch { saved = []; }
  const ordered = Array.isArray(saved) ? saved.filter((id): id is string => typeof id === "string" && ids.includes(id)) : [];
  ids.forEach((id) => { if (!ordered.includes(id)) ordered.push(id); });
  return ordered.map((id) => SIDEBAR_MODULES.find(([candidate]) => candidate === id)!);
}
function saveSidebarOrder(nav: HTMLElement) {
  const order = [...nav.querySelectorAll<HTMLElement>("[data-sidebar-module]")].map((el) => el.dataset.sidebarModule!);
  try { localStorage.setItem(sidebarStorageKey, JSON.stringify(order)); } catch { /* local preference is best effort */ }
}
export function bindSidebarOrder() {
  const nav = document.querySelector<HTMLElement>("#sidebar-nav");
  if (!nav) return;
  let dragging: HTMLElement | null = null;
  let placeholder: HTMLElement | null = null;
  let pointerId: number | null = null;
  let pointerStartX = 0;
  let pointerStartY = 0;
  let pointerMoved = false;
  let touchTimer: number | undefined;
  let dragActive = false;
  let moveFrame: number | undefined;
  let pendingMove: {x: number; y: number} | null = null;
  let suppressClick = false;
  const resetDraggedItem = () => {
    if (!dragging) return;
    dragging.classList.remove("is-dragging");
    dragging.removeAttribute("aria-grabbed");
    dragging.style.removeProperty("width");
    dragging.style.removeProperty("position");
    dragging.style.removeProperty("left");
    dragging.style.removeProperty("top");
    dragging.style.removeProperty("z-index");
    dragging.style.removeProperty("pointer-events");
    dragging.style.removeProperty("transform");
  };
  const resetDrag = () => {
    if (touchTimer) window.clearTimeout(touchTimer);
    touchTimer = undefined;
    if (moveFrame) window.cancelAnimationFrame(moveFrame);
    moveFrame = undefined;
    pendingMove = null;
    if (placeholder) placeholder.remove();
    placeholder = null;
    nav.classList.remove("is-sorting");
    resetDraggedItem();
    dragging = null;
    pointerId = null;
    dragActive = false;
  };
  const beginDrag = () => {
    if (!dragging || dragActive) return;
    const rect = dragging.getBoundingClientRect();
    placeholder = document.createElement("div");
    placeholder.className = "sidebar-drop-placeholder";
    placeholder.style.height = `${rect.height}px`;
    placeholder.setAttribute("aria-hidden", "true");
    nav.insertBefore(placeholder, dragging);
    nav.classList.add("is-sorting");
    dragging.classList.add("is-dragging");
    dragging.setAttribute("aria-grabbed", "true");
    dragging.style.width = `${rect.width}px`;
    dragging.style.position = "fixed";
    dragging.style.left = `${rect.left}px`;
    dragging.style.top = `${rect.top}px`;
    dragging.style.zIndex = "20";
    dragging.style.pointerEvents = "none";
    dragging.style.transform = "scale(1.02)";
    dragActive = true;
  };
  const placePlaceholder = (clientY: number) => {
    if (!dragActive || !dragging || !placeholder) return;
    const items = [...nav.querySelectorAll<HTMLElement>("[data-sidebar-module]")].filter((item) => item !== dragging);
    const before = items.find((item) => {
      const rect = item.getBoundingClientRect();
      return clientY < rect.top + rect.height / 2;
    });
    if (before) {
      if (placeholder.nextElementSibling !== before) nav.insertBefore(placeholder, before);
    } else if (placeholder !== nav.lastElementChild) {
      nav.appendChild(placeholder);
    }
  };
  const queueMove = (clientX: number, clientY: number) => {
    if (!dragActive || !dragging) return;
    pendingMove = {x: clientX, y: clientY};
    if (moveFrame) return;
    moveFrame = window.requestAnimationFrame(() => {
      moveFrame = undefined;
      if (!pendingMove || !dragging) return;
      dragging.style.transform = `translate(${pendingMove.x - pointerStartX}px, ${pendingMove.y - pointerStartY}px) scale(1.02)`;
      placePlaceholder(pendingMove.y);
      pendingMove = null;
    });
  };
  // Use pointer events for both desktop drag and mobile long-press. Prevent
  // the browser's native HTML5 drag from stealing the pointer stream.
  nav.addEventListener("dragstart", (event) => event.preventDefault());
  nav.addEventListener("pointerdown", (event) => {
    const item = (event.target as HTMLElement).closest<HTMLElement>("[data-sidebar-module]");
    if (!item) return;
    dragging = item;
    pointerId = event.pointerId;
    pointerStartX = event.clientX;
    pointerStartY = event.clientY;
    pointerMoved = false;
    try { item.setPointerCapture(event.pointerId); } catch { /* best effort */ }
    if (event.pointerType === "touch") touchTimer = window.setTimeout(beginDrag, 350);
  });
  nav.addEventListener("pointermove", (event) => {
    if (!dragging || pointerId !== event.pointerId) return;
    if (Math.abs(event.clientX - pointerStartX) + Math.abs(event.clientY - pointerStartY) > 4) pointerMoved = true;
    if (!dragActive) {
      if (event.pointerType === "touch" && pointerMoved) {
        if (touchTimer) window.clearTimeout(touchTimer);
        touchTimer = undefined;
        dragging = null;
        pointerId = null;
      } else if (event.pointerType !== "touch" && pointerMoved) beginDrag();
      return;
    }
    event.preventDefault();
    queueMove(event.clientX, event.clientY);
  });
  nav.addEventListener("pointerup", (event) => {
    if (pointerId !== event.pointerId) return;
    if (touchTimer) window.clearTimeout(touchTimer); touchTimer = undefined;
    if (dragActive && placeholder && dragging) {
      nav.insertBefore(dragging, placeholder);
      placeholder.remove();
      placeholder = null;
      resetDraggedItem();
      saveSidebarOrder(nav);
      suppressClick = true;
    }
    try { dragging?.releasePointerCapture(event.pointerId); } catch { /* best effort */ }
    resetDrag();
  });
  nav.addEventListener("pointercancel", (event) => {
    if (pointerId !== event.pointerId) return;
    try { dragging?.releasePointerCapture(event.pointerId); } catch { /* best effort */ }
    resetDrag();
  });
  nav.addEventListener("click", (event) => { if (!suppressClick) return; event.preventDefault(); event.stopPropagation(); suppressClick = false; });
}
export function shell(
  page: string,
  content: string,
  notice: string,
  test: boolean,
) {
  const active =
    page === "jobs" || page === "progress"
      ? "jobs"
      : page === "profile"
        ? "wiki"
        : page;
  const items = sidebarOrder();
  const label =
    items.find(([id]) => id === active)?.[1] ||
    (page === "feedback"
      ? "反馈记录"
      : page === "directory"
        ? "公司与方向"
        : "设置");
  const accountAvatar = `<span class="avatar"><span class="avatar-atmosphere" aria-hidden="true"></span><img src="/assets/career-avatar.png" alt="">
    <svg class="avatar-flow" viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <linearGradient id="avatar-cold" x1="0" y1="1" x2="1" y2="0"><stop stop-color="#223947" stop-opacity="0"/><stop offset=".42" stop-color="#577c97"/><stop offset=".7" stop-color="#d4f2ff"/><stop offset="1" stop-color="#82b5d1" stop-opacity="0"/></linearGradient>
        <linearGradient id="avatar-warm" x1="1" y1="0" x2="0" y2="1"><stop stop-color="#8c4f23" stop-opacity="0"/><stop offset=".45" stop-color="#b98542"/><stop offset=".7" stop-color="#ffe9b4"/><stop offset="1" stop-color="#c08737" stop-opacity="0"/></linearGradient>
        <filter id="avatar-turbulence" x="-35%" y="-35%" width="170%" height="170%"><feTurbulence type="fractalNoise" baseFrequency=".065 .12" numOctaves="2" seed="8" result="noise"/><feDisplacementMap in="SourceGraphic" in2="noise" scale="5" xChannelSelector="R" yChannelSelector="G"/><feGaussianBlur stdDeviation=".35"/></filter>
        <filter id="avatar-soft" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="2.2"/></filter>
        <mask id="avatar-clear-face"><rect width="100" height="100" fill="white"/><rect x="17" y="17" width="66" height="66" fill="black"/></mask>
      </defs>
      <g mask="url(#avatar-clear-face)">
        <g class="flow-smoke" filter="url(#avatar-soft)" fill="none" stroke-width="8">
          <path stroke="url(#avatar-cold)" d="M14 91C4 62 23 45 14 25S54 9 86 13"/>
          <path stroke="url(#avatar-warm)" d="M85 7C98 35 77 49 86 76S43 94 13 85"/>
        </g>
        <g class="flow-stream" filter="url(#avatar-turbulence)" fill="url(#avatar-cold)">
          <path d="M13 91C1 68 19 46 13 29C6 9 45 19 79 7C58 21 19 13 20 33C22 53 8 66 13 91Z"/>
          <path d="M6 70C22 49 7 27 21 16C33 7 56 16 71 11C49 23 23 13 21 30C17 45 20 60 6 70Z" opacity=".65"/>
        </g>
        <g class="flow-stream flow-warm" filter="url(#avatar-turbulence)" fill="url(#avatar-warm)">
          <path d="M87 8C98 31 79 50 87 71C97 96 44 80 19 94C45 71 78 94 80 69C80 50 94 28 87 8Z"/>
          <path d="M96 42C80 57 96 74 78 85C62 96 44 81 28 91C49 74 70 88 79 75C90 60 83 55 96 42Z" opacity=".7"/>
        </g>
        <path class="flow-filament" stroke="#e0f4ff" stroke-width=".8" d="M11 83C8 59 22 50 16 29S49 19 80 10"/>
        <path class="flow-filament flow-filament-warm" stroke="#ffebbf" stroke-width=".9" d="M88 18C93 40 77 52 85 73S51 83 23 91"/>
        <g class="flow-embers" fill="#c79955"><circle cx="85" cy="86" r=".9"/><circle cx="68" cy="94" r=".6"/><circle cx="93" cy="62" r=".6"/><path d="M89 46l1-3 .4 2.5z"/></g>
        <g class="flow-embers" fill="#8bb3ca" style="animation-delay:-1.8s"><circle cx="14" cy="13" r=".7"/><circle cx="7" cy="42" r=".6"/><circle cx="39" cy="8" r=".8"/></g>
      </g>
    </svg></span>`;
  return `<div class="workspace ${ui.sidebar ? "" : "sidebar-hidden"}"><aside class="sidebar" ${ui.sidebar ? "" : "inert"}><div class="brand">Career OS</div><nav id="sidebar-nav" aria-label="主导航">${items.map(([id, text]) => `<button class="nav ${active === id ? "active" : ""}" data-page="${id}" data-sidebar-module="${id}" draggable="true" aria-grabbed="false">${icon(id)}<span>${text}</span></button>`).join("")}</nav><div class="sidebar-bottom"><details class="account-menu"><summary aria-label="蒸🐮🐸，账户菜单">${accountAvatar}<span class="account-name"><span>蒸</span><span class="account-emoji">🐮</span><span class="account-emoji">🐸</span></span><span class="more">···</span></summary><div class="account-popover"><button data-page="profile">${icon("resume")}个人资料</button><button data-page="directory">${icon("jobs")}公司与方向</button><button data-page="diagnostics">${icon("settings")}设置</button><button data-page="feedback">${icon("feedback")}反馈记录</button></div></details></div></aside><main><header class="topbar"><div class="actions"><button class="icon-button" id="toggle-sidebar" aria-label="${ui.sidebar ? "收起" : "展开"}侧栏" aria-expanded="${ui.sidebar}">${icon("panel")}</button><h1>${label}</h1>${test ? '<span class="test-badge">测试空间</span>' : ""}</div><button class="quiet" id="capture-feedback">${icon("feedback")}反馈</button></header><div id="notice" class="notice toast" role="status" ${notice ? "" : "hidden"}>${e(notice)}</div><div class="workspace-content">${content}</div></main></div>`;
}
export function view(page: string, d: Row, h: Row): string {
  const {
    state: s,
    journey: j,
    workDomain,
    jobId,
    editorVersions,
    profileBuffer,
    jobBuffers,
    planBuffers,
  } = d;
  const jobs = s.jobs as Row[],
    notes = j.notes as Row[],
    episodes = j.episodes as Row[];
  const profileHtml = () => profilePanel(s.profile);
  if (page === "diagnostics") return aiSettingsView(s, h.modeText());
  if (page === "wiki" || page === "profile") {
    if (page === "profile") knowledgeUI.tab = "profile";
    return knowledgeView(d, profileHtml);
  }
  if (page === "directory") return directoryView(d);
  const job = jobs.find((x) => x.id === jobId),
    plan = (job &&
      (planBuffers.get(job.id) ||
        j.plans.find((x: Row) => x.job_id === job.id))) || {
      stage: "screening",
      next_action: "",
    };
  const origin = (n: Row) => {
    const x =
      n.scope_type === "job"
        ? jobs.find((x) => x.id === n.scope_id)
        : episodes.find((x) => x.id === n.scope_id);
    return x
      ? `<button class="text-btn" ${n.scope_type === "job" ? `data-job="${e(x.id)}" data-note-kind="${e(n.kind)}" data-origin-note="${e(n.id)}"` : `data-open-episode="${e(x.id)}" data-note-kind="${e(n.kind)}" data-origin-note="${e(n.id)}"`}>${e(x.company)} · ${e(x.title || x.role)} ${icon("arrow")}</button>`
      : "";
  };
  const records = (ns: Row[], extra = "", tools = "") => {
    ns = ns
      .slice()
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
    if (!ns.length)
      return `<div class="record-empty">${empty("暂无记录")}${extra}</div>`;
    const selected = ns.find((n) => n.id === ui.selectedNote) || ns[0];
    return `<div class="records"><select class="record-picker" aria-label="选择记录" data-record-picker>${ns.map((n) => `<option value="${e(n.id)}" ${selected.id === n.id ? "selected" : ""}>${e(n.title || noteNames[n.kind])} · ${dt(n.created_at)}</option>`).join("")}</select><div class="record-list scroll" aria-label="记录列表">${ns.map((n) => `<button class="record-row ${selected.id === n.id ? "selected" : ""}" data-select-note="${e(n.id)}"><span>${e(n.title || noteNames[n.kind] || "未命名记录")}</span><small>${dt(n.created_at)} · ${e(noteNames[n.kind])}</small></button>`).join("")}</div><article class="reading scroll"><div class="reading-meta">${dt(selected.created_at)} · ${selected.note_revision ? `更正视图 v${selected.note_revision}` : "原始记录"} ${tools}</div><div class="actions record-actions"><button class="secondary" data-record-correct="${e(selected.id)}">更正记录</button><button class="text-btn" data-record-history="${e(selected.id)}">原文与历史</button><button class="primary" data-record-candidate="${e(selected.id)}">整理为待确认事实</button></div><h3>${e(selected.title || "未命名记录")}</h3>${origin(selected)}${selected.submission_id ? `<p class="muted">关联投递：${e(s.applications.find((a: Row) => a.id === selected.submission_id)?.resume_snapshot?.name || "已固定版本")} · <a href="/#jobs/${encodeURIComponent(selected.scope_id)}?tab=resume">查看投递快照</a></p>` : ""}<div class="prose">${e(selected.content)}</div></article></div>`;
  };
  const versions = () =>
    `${editorVersions.length ? editorVersions.map((v: Row) => `<article class="version"><div><b>${e(v.name || "未命名版本")}</b><small>${dt(v.createdAt)}</small></div><div class="actions"><a class="secondary" href="/api/artifacts/${e(v.artifact_id)}" target="_blank" rel="noopener">查看 PDF</a><a class="text-btn" href="/api/artifacts/${e(v.artifact_id)}?download=true">下载</a></div></article>`).join("") : empty("在简历工作台保存版本后，会显示在这里。")}`;
  if (page === "home") {
    const phaseLabels: Row = {resume:"写简历",submitted:"已投递",interview:"面试",offer:"Offer"};
    const nextLabels: Row = {resume:"准备投递",submitted:"记录招聘沟通",interview:"准备当前面试",offer:"核对 Offer"};
    const active = (s.opportunities || [])
      .filter((x: Row) => !x.read_only && x.result === "active")
      .sort((a: Row,b: Row)=>String(b.phase_changed_on||b.created_on||"").localeCompare(String(a.phase_changed_on||a.created_on||"")));
    const urgentJob = active[0];
    const urgentAction = urgentJob
      ? `<button class="primary" data-job="${e(urgentJob.id)}">继续：${e(nextLabels[urgentJob.phase] || urgentJob.title)}</button>`
      : `<button class="primary" id="home-add-job">${icon("plus")}添加机会</button>`;
    return `<div class="home scroll"><div class="home-inner"><p class="muted today-date">${new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "long" })}</p><h2>今天，先完成一件事</h2><div class="quick-start">${urgentAction}<button class="secondary" data-page="resume">${icon("resume")}简历工作台</button><button class="secondary" id="add-episode">${icon("work")}记录工作</button></div><section class="continue-list">${title("继续推进", `<button class="text-btn" data-page="jobs">全部 ${icon("arrow")}</button>`)}${
      active.length
        ? active.slice(0,4).map((x:Row)=>`<button class="continue-row" data-job="${e(x.id)}"><div><b>${e(nextLabels[x.phase]||x.title)}</b><small>${e(x.company)} · ${e(x.title)}</small></div><span>${e(phaseLabels[x.phase]||"待核对")}</span>${icon("arrow")}</button>`).join("")
        : empty("添加一个机会，或先整理个人资料。")
    }</section><button class="text-btn" data-page="wiki">${icon("resume")}整理职业 Wiki</button></div></div>`;
  }
  if (page === "jobs" || page === "progress") {
    const list = jobs.filter((x) =>
      ui.jobFilter === "active" ? x.status === "active" : x.status !== "active",
    );
    let content = "";
    if (job) {
      if (ui.jobTab === "jd")
        content = `${title("机会信息", `<button class="secondary" id="edit-job-dialog">${jobBuffers.has(job.id) ? "继续编辑 · 未保存" : "编辑机会"}</button>`)}<div class="reading scroll">${opportunityObjects(d, job.id)}<h3>${e(job.company)} · ${e(job.title)}</h3>${job.url ? `<a href="${e(/^https?:\/\//i.test(job.url) ? job.url : "#")}" target="_blank" rel="noopener">查看招聘原文 ↗</a>` : ""}<div class="prose">${e(job.jd)}</div></div>`;
      else if (ui.jobTab === "analysis")
        content = `${title("机会评估", `<button class="text-btn" data-open-wiki="job:${e(job.id)}">相关 Wiki</button><button class="secondary" id="analyze-job" ${job.status === "active" ? "" : "disabled"}>评估机会</button>`)}<div class="scroll panel-body">${h.runsHtml("job", job.id) || empty(s.diagnostics?.provider?.configured ? "尚未评估这个机会。" : "AI 尚未配置，可在设置中接入。")}</div>`;
      else if (ui.jobTab === "resume")
        content = `${title("准备简历", `<a class="secondary" href="/editor.html?job_id=${encodeURIComponent(job.id)}">进入简历工作台</a>`)}<div class="scroll panel-body">${resumeUses(d, job.id)}<section class="applications"><h2>历史投递</h2>${h.applicationsHtml(job.id)}</section></div>`;
      else
        content = `${title(noteNames[ui.jobTab] + "记录", `<button class="text-btn" data-open-wiki="job:${e(job.id)}">相关 Wiki</button>` + addNote("job", job.id, ui.jobTab))}${records(
          notes.filter(
            (n) =>
              n.scope_type === "job" &&
              n.scope_id === job.id &&
              n.kind === ui.jobTab,
          ),
          ui.jobTab === "interview"
            ? '<p class="muted">可粘贴面试转写；语音模拟尚未接入。</p>'
            : "",
        )}`;
    }
    const hasJd = String(job?.jd || "").trim().length > 0;
    const hasEvaluation = !!job && s.runs.some((r: Row) => r.kind === "job" && r.job_id === job.id && r.status === "succeeded");
    const opportunityId = job
      ? s.opportunities?.find((o: Row) => o.legacy_job_id === job.id)?.id
      : undefined;
    const jobUses = job ? d.domain.resume_uses.filter((u: Row) =>
      (u.scope_type === "job" && u.scope_id === job.id) ||
      (u.scope_type === "opportunity" && u.scope_id === opportunityId),
    ) : [];
    const hasSubmission = !!job && s.applications.some((a: Row) => a.job_id === job.id);
    const primary = !job ? "" : !hasJd ? `<button class="primary" data-primary-opportunity="jd">补充机会信息</button>` : !hasEvaluation ? `<button class="primary" data-primary-opportunity="analysis" ${job.status === "active" ? "" : "disabled"}>评估机会</button>` : !jobUses.length ? `<a class="primary" href="/editor.html?job_id=${encodeURIComponent(job.id)}">准备简历</a>` : !hasSubmission ? `<button class="primary" data-application="${e(jobUses[0].version_id)}" data-application-job="${e(job.id)}">登记投递</button>` : `<button class="primary" data-primary-opportunity="plan" ${job.status === "active" ? "" : "disabled"}>${e(plan.next_action || "安排下一步")}</button>`;
    return `<div class="split"><section class="entity-rail"><div class="rail-heading"><h2>机会</h2><button class="icon-button" id="add-job" aria-label="添加机会">${icon("plus")}</button></div>${tabs(
      "jobFilter",
      [
        ["active", "进行中"],
        ["archived", "已归档"],
      ],
      ui.jobFilter,
    )}<div class="scroll rail-list">${
      list
        .map((x) => {
          const p = j.plans.find((p: Row) => p.job_id === x.id);
          return `<button class="entity-row ${x.id === jobId ? "selected" : ""}" data-job="${e(x.id)}"><b>${e(x.title)}</b><span>${e(x.company)}</span><small>${x.status === "active" ? e(stageNames[p?.stage] || "筛选") : x.status === "deleted" ? "已删除" : "已排除"}${p?.due_date ? " · " + e(p.due_date) : ""}</small></button>`;
        })
        .join("") || empty("暂无机会")
    }</div></section><section class="detail-pane">${job ? `<div class="entity-heading"><div><small>${e(job.company)}</small><h2>${e(job.title)}</h2></div><details class="more-menu"><summary aria-label="机会操作">···</summary><div>${job.status === "active" ? '<button data-job-status="excluded">排除机会</button><button data-job-status="deleted">删除机会</button>' : '<button data-job-status="active">恢复机会</button>'}</div></details></div><div class="next-strip opportunity-next"><span class="pill">${e(stageNames[plan.stage] || "筛选")}</span><div class="next-text">${primary || e(plan.next_action || "选择一个机会")}</div><small>${e(plan.due_date || "")}</small><button class="text-btn" id="edit-plan" ${job.status === "active" ? "" : "disabled"}>编辑计划</button></div>${tabs("jobTab", [["jd", "机会"], ["analysis", "评估"], ["research", "研究"], ["resume", "简历"], ["communication", "沟通"], ["interview", "面试"], ["offer", "Offer"], ...["action", "reflection"].filter((kind) => notes.some((n) => n.scope_type === "job" && n.scope_id === job.id && n.kind === kind)).map((kind) => [kind, noteNames[kind]])], ui.jobTab)}<div class="module-content">${content}</div>` : empty("选择或添加一个机会")}</section></div>`;
  }
  if (page === "work") {
    const selected = episodes.find((x) => x.id === ui.episodeId) || episodes[0];
    const employmentId = selected
      ? workDomain.employments?.find((x: Row) => x.legacy_episode_id === selected.id)?.id || "employment:" + selected.id
      : "";
    const projects = selected ? workDomain.projects.filter((p: Row) =>
      (p.scope_type === "episode" && p.scope_id === selected.id) ||
      (p.scope_type === "employment" && p.scope_id === employmentId),
    ) : [];
    const projectWorkspace = selected ? `<section class="work-domain-card"><div class="pane-heading"><div><h2>项目与成果</h2><p class="muted">记录项目进展、成果和证据。成果与证据不会自动进入个人 Wiki。</p></div><button class="primary" data-work-project="${e(selected.id)}">新建项目</button></div>${projects.length ? projects.map((p: Row) => { const events = workDomain.events.filter((x: Row) => x.target_type === "project" && x.target_id === p.id); const achievements = workDomain.achievements.filter((x: Row) => x.project_id === p.id); const evidence = workDomain.evidence.filter((x: Row) => x.scope_type === "project" && x.scope_id === p.id); return `<article class="work-project"><div><h3>${e(p.name)}</h3><p class="preserve">${e(p.description || "暂无项目说明")}</p></div><div class="work-project-meta"><span>${events.length} 个事件</span><span>${achievements.length} 项成果</span><span>${evidence.length} 条证据</span></div><div class="actions"><button class="secondary" data-work-event="${e(p.id)}">记录事件</button><button class="secondary" data-work-achievement="${e(p.id)}">记录成果</button><button class="secondary" data-work-evidence="${e(p.id)}">添加证据</button><button class="text-btn" data-work-link-evidence="${e(p.id)}">关联证据</button><button class="text-btn" data-work-person="${e(p.id)}">添加参与者</button></div></article>`; }).join("") : empty("先建立一个项目，再记录当前进展。")}</section>` : "";
    return `<div class="split"><section class="entity-rail"><div class="rail-heading"><h2>任职</h2><button class="icon-button" id="add-episode" aria-label="新建任职">${icon("plus")}</button></div><div class="scroll rail-list">${episodes.map((x) => `<button class="entity-row ${selected?.id === x.id ? "selected" : ""}" data-open-episode="${e(x.id)}"><b>${e(x.company)}</b><span>${e(x.role)}</span><small>${e(x.start_date || "")} — ${e(x.end_date || "至今")}</small></button>`).join("") || empty("新建一份任职，开始记录当前进展。")}</div></section><section class="detail-pane">${selected ? `<div class="entity-heading"><div><small>${e(selected.company)}</small><h2>${e(selected.role)}</h2></div><div class="actions"><button class="quiet" data-open-wiki="episode:${e(selected.id)}">项目与 Wiki</button><button class="quiet" data-episode="${e(selected.id)}">编辑</button><button class="quiet" data-export-episode="${e(selected.id)}">导出</button></div></div><div class="focus-line" title="${e(selected.focus)}">${e(selected.focus || "尚未填写当前进展")}</div>${projectWorkspace}${tabs("workTab", [["action", "事项"], ["collaboration", "协作"], ["reflection", "收获"], ...(notes.some((n) => n.scope_type === "episode" && n.scope_id === selected.id && n.kind === "interview") ? [["interview", "历史面试"]] : [])], ui.workTab)}<div class="module-content">${title("当前进展", addNote("episode", selected.id, ui.workTab))}${records(notes.filter((n) => n.scope_type === "episode" && n.scope_id === selected.id && n.kind === ui.workTab))}</div>` : empty("新建一份任职，开始记录当前进展。")}</section></div>`;
  }
  if (page === "resume" || page === "profile") {
    const tab = page === "profile" ? "profile" : ui.materialTab;
    const p = profileBuffer || s.profile;
    return `<div class="materials">${tabs(
      "materialTab",
      [
        ["versions", "文档与版本"],
        ["uses", "方向与机会用途"],
      ],
      tab,
    )}${tab === "profile" ? profilePanel(s.profile) : tab === "uses" ? `<section class="module-content"><div class="scroll panel-body">${resumeUses(d)}</div></section>` : `<section class="module-content">${title("选择当前文档", '<button class="secondary" data-page="jobs">从机会开始新简历</button>')}<div class="scroll panel-body"><p class="muted">选择最近编辑的文档，在同一简历工作台继续。不会自动选中任何工作稿。</p>${(s.resume_documents || []).map((doc: Row) => `<article class="version"><div><b>${e(doc.company)} · ${e(doc.title)}</b><small>最近编辑 ${dt(doc.saved_at)}</small></div><a class="primary" href="/editor.html?document_id=${encodeURIComponent(doc.document_id)}">编辑简历</a></article>`).join("") || empty("还没有工作稿。请从具体机会明确选择创建来源。") }<details><summary>历史材料（只读）</summary>${versions()}</details><a class="text-btn" href="/editor.html?legacy=1">查看历史全局稿（只读）</a></div></section>`}</div>`;
  }
  if (page === "practice" || page === "footprint") {
    const ns =
      page === "practice"
        ? notes.filter((n) => ["interview", "reflection"].includes(n.kind))
        : notes;
    return `<section class="full-panel">${title(page === "practice" ? "面试与复盘" : "全部记录", `<span class="muted">${ns.length} 条</span>`)}${records(ns, '<p class="muted">请进入<button class="text-btn" data-page="jobs">机会</button>或<button class="text-btn" data-page="work">工作卡</button>追加记录，保留任务归属。</p>')}</section>`;
  }
  if (page === "feedback") {
    const fs = s.feedback as Row[],
      f = fs.find((x) => x.id === ui.selectedFeedback) || fs[0];
    return `<section class="full-panel">${title("反馈记录", '<a class="text-btn" href="/api/feedback/export?format=md">导出 Markdown</a><a class="text-btn" href="/api/feedback/export?format=json">JSON</a>')}${f ? `<div class="records"><div class="record-list scroll">${fs.map((x) => `<button class="record-row ${x.id === f.id ? "selected" : ""}" data-select-feedback="${e(x.id)}"><span>${e(x.text.slice(0, 50))}</span><small>${dt(x.created_at)}</small></button>`).join("")}</div><article class="reading scroll"><div class="pane-heading"><small>${dt(f.created_at)} · ${e(f.current_page)}</small><button class="secondary" data-note="${e(f.id)}">补充</button></div><div class="prose">${e(f.text)}</div>${f.screenshot_id ? `<a href="/api/artifacts/${e(f.screenshot_id)}" target="_blank">查看截图</a>` : ""}${f.notes.map((n: Row) => `<blockquote><small>${dt(n.created_at)}</small><div class="prose">${e(n.text)}</div></blockquote>`).join("")}</article></div>` : empty("使用中遇到问题，随时点右上角反馈。")}</section>`;
  }
  return `<section class="settings scroll">${title("本地设置")}<div class="setting-row"><span>AI</span><b>${e(h.modeText())}</b></div><div class="setting-row"><span>数据位置</span><code>${e(s.diagnostics.data_dir)}</code></div><div class="setting-row"><span>应用版本</span><span>${e(s.diagnostics.app_version)}</span></div><div class="setting-row"><span>全链路案例</span><div><p class="muted">当前隔离 v2 保留既有案例读取。完整案例的装载和删除暂停，避免改变旧资料及附件引用。</p><div class="actions"><button class="secondary" id="load-demo" disabled>装载 / 补齐案例</button><button class="quiet" id="remove-demo" disabled>删除案例</button></div></div></div><details class="setup"><summary>配置 AI</summary><p>在本地终端配置 CAREER_AI_PROVIDER=real、CAREER_AI_MODEL、CAREER_AI_API_KEY（或 OPENAI_API_KEY），然后重启服务。兼容服务可另设 CAREER_AI_BASE_URL。</p><p>具体命令见 src/workbench/README.md。密钥只在本机终端设置。</p><p>${e(s.diagnostics.provider?.base_url)} · ${e(s.diagnostics.provider?.model || "未配置模型")}</p></details><button class="text-btn" data-page="feedback">查看反馈记录 ${icon("arrow")}</button></section>`;
}
