/** Read-only, disposable presentation of the server's operation ledger. */
type Row = Record<string, any>;
const esc = (value: unknown) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]!));
export function attentionItems(items: Row[]) {
  return items.filter(item => ["processing", "pending", "unknown", "preparing"].includes(item.state)
    || (item.state === "failed" && Date.now() - Date.parse(item.finished_at || item.created_at) < 86400000));
}
export function createActivityReader(api: (path: string) => Promise<Row>) {
  let data: Row[] = [];
  let inflight: Promise<void> | null = null;
  return {
    items: () => data,
    refresh() {
      if (!inflight) inflight = api("/ai/activity").then(result => { data = result.items || []; }).finally(() => { inflight = null; });
      return inflight;
    },
  };
}
export async function beginAIProcessing<T>(show: () => void, execute: () => Promise<T>): Promise<T> {
  show();
  return execute();
}
export function previewExpired(expiresAt: string, now = Date.now()) {
  return !!expiresAt && now >= Date.parse(expiresAt);
}
export function isPreparationExpired(error: unknown) {
  return (error as Row)?.data?.code === "prepared_request_expired"
    || (error instanceof Error && error.message === "准备对象已过期，请重新预览");
}
export function watchPreviewExpiry(dialog: HTMLDialogElement, expiresAt: string, expire: () => void) {
  if (!expiresAt || !Number.isFinite(Date.parse(expiresAt))) return;
  const timer = setTimeout(() => {
    // Never replace an in-flight request or a saved result with an expired Preview.
    if (dialog.open && dialog.querySelector('[data-d2-confirm], [data-d4-confirm]')) expire();
  }, Math.max(0, Date.parse(expiresAt) - Date.now()));
  dialog.addEventListener('close', () => clearTimeout(timer), {once:true});
}
export function processingHTML() {
  return '<section class="ai-processing" role="status"><h3>AI 正在整理…</h3><p>可以关闭窗口，不影响处理。</p><p>稍后从右上角 AI 查看结果。</p></section>';
}
export function operationErrorHTML(error: unknown) {
  const data = (error as Row)?.data || {};
  const unknown = data.state === "outcome_unknown" || data.status === "outcome_unknown";
  const knownFailure = data.state === "failed";
  const title = unknown ? "结果未知" : knownFailure ? "失败" : "暂时无法读取处理结果";
  const message = unknown ? "请求已经发送，但 Career 无法确认是否成功。为了避免重复调用，不会自动重试。"
    : knownFailure ? "AI 这次没有成功完成，没有修改你的资料。"
    : "请从右上角 AI 查看这次操作的实际状态，不会重新发送。";
  return `<section role="status"><h3>${title}</h3><p>${message}</p><p>可从右上角 AI 查看这次操作。</p></section>`;
}
function ownerLabel(item: Row) { return (item.owners || []).map((x: Row) => x.label).join(" / "); }
function statusLabel(item: Row) { return item.state === "failed" ? `${item.title}失败` : `${item.title} · ${item.state_label}`; }
export function activityListHTML(items: Row[]) {
  if (!items.length) return '<p>目前没有 AI 操作。</p>';
  return items.map(item => `<div class="ai-activity-row"><div><strong>${esc(ownerLabel(item))}</strong><p>${esc(statusLabel(item))}${item.review ? ` · 已处理 ${item.review.reviewed} / ${item.review.total}` : ""}</p></div><button class="secondary" data-ai-detail="${esc(item.operation_id)}">${item.state === "pending" ? "继续" : "查看"}</button></div>`).join("");
}
export function activityDetailHTML(item: Row) {
  const progress = item.review ? `<p>已处理 ${item.review.reviewed} / ${item.review.total}</p>` : "";
  const action = item.state === "pending" && item.proposal_kind === "wiki_compiler_proposal"
    ? `<button class="primary" data-ai-resume-proposal="${esc(item.proposal_id)}">继续处理建议</button>`
    : item.state === "pending" ? `<a class="secondary" href="${esc(item.owners[0]?.href || '#wiki')}" data-ai-owner-link>打开所属页面</a>` : "";
  return `<div class="ai-activity-detail"><h3>${esc(ownerLabel(item))}</h3><p>${esc(statusLabel(item))}</p><p role="status">${esc(item.message)}</p>${progress}${action}</div>`;
}
export function createAIActivityUI(ctx: {
  api: (path: string) => Promise<Row>;
  modal: (title: string, html: string) => HTMLDialogElement;
  owner: () => {type: string; id: string} | null;
  openProposal: (id: string) => Promise<void>;
}) {
  const reader = createActivityReader(ctx.api);
  let timer: ReturnType<typeof setTimeout> | undefined;
  let panel: HTMLDialogElement | null = null;
  let selected = "";
  let panelVersion = "";
  let unavailable = false;
  const displayItems = () => {
    const all = reader.items();
    const active = attentionItems(all);
    return [...active, ...all.filter(x => !active.includes(x)).slice(0, 20)];
  };
  function paint() {
    const items = reader.items();
    const pending = items.filter(x => x.state === "pending").length;
    const active = attentionItems(items);
    const global = document.querySelector<HTMLButtonElement>("#ai-activity-entry");
    if (global) {
      global.textContent = unavailable ? "AI · 状态暂不可用" : pending ? `${pending} 个 AI 结果待处理` : active.some(x => x.state === "processing") ? "AI · 处理中" : active.length ? "AI · 有状态待查看" : items.some(x => x.state === "completed" && Date.now() - Date.parse(x.finished_at || "") < 10000) ? "AI · 完成" : "AI";
      global.classList.toggle("ai-attention", !unavailable && active.length > 0);
      global.onclick = () => openPanel();
    }
    const target = ctx.owner();
    const owned = target ? items.filter(x => ["processing","pending"].includes(x.state) && x.owners.some((o: Row) => o.type === target.type && o.id === target.id)) : [];
    let hint = document.querySelector<HTMLElement>("#ai-object-status");
    if (!hint && owned.length) {
      hint = document.createElement("div"); hint.id = "ai-object-status"; hint.className = "ai-object-status";
      document.querySelector(".topbar")?.insertAdjacentElement("afterend", hint);
    }
    if (hint) {
      hint.hidden = !owned.length;
      const markup = owned.length ? `<span>${owned.filter(x => x.state === 'pending').length || owned.length} 个 AI ${owned.some(x => x.state === 'pending') ? '结果待处理' : '操作处理中'}</span> <button class="text-btn">查看</button>` : "";
      if (hint.innerHTML !== markup) hint.innerHTML = markup;
      const button = hint.querySelector("button"); if (button) button.onclick = () => openPanel(owned[0].operation_id);
    }
    if (!panel?.isConnected) return;
    const current = items.find(x => x.operation_id === selected);
    const html = unavailable ? '<p role="status">暂时无法读取 AI 状态。稍后会继续查询，不会重新发送。</p>'
      : selected ? current ? activityDetailHTML(current) : '<p>这次操作暂不可用，没有重新发送。</p>' : activityListHTML(displayItems());
    if (panelVersion === html) return;
    panelVersion = html;
    const body = panel.querySelector<HTMLElement>("[data-ai-panel]")!; body.innerHTML = html;
    body.querySelectorAll<HTMLButtonElement>("[data-ai-detail]").forEach(button => {
      button.onclick = () => {
        const chosen = items.find(x => x.operation_id === button.dataset.aiDetail);
        if (chosen?.state === "pending" && chosen.proposal_kind === "wiki_compiler_proposal") {
          panel?.close(); void ctx.openProposal(chosen.proposal_id); return;
        }
        selected = button.dataset.aiDetail!; panelVersion = ""; paint();
      };
    });
    body.querySelector<HTMLButtonElement>("[data-ai-resume-proposal]")?.addEventListener("click", () => {
      const id = current?.proposal_id; panel?.close(); if (id) void ctx.openProposal(id);
    });
    body.querySelector("[data-ai-owner-link]")?.addEventListener("click", () => panel?.close());
  }
  async function refresh() {
    try { await reader.refresh(); unavailable = false; } catch { unavailable = true; }
    paint();
  }
  function openPanel(id = "") {
    selected = id; panelVersion = "";
    panel = ctx.modal("AI 进度", '<section data-ai-panel></section>');
    panel.classList.add("ai-activity-dialog"); paint(); void refresh();
  }
  function mount() {
    const header = document.querySelector(".topbar");
    if (header && !header.querySelector("#ai-activity-entry")) {
      const button = document.createElement("button"); button.id = "ai-activity-entry"; button.className = "quiet ai-entry";
      header.insertBefore(button, header.lastElementChild);
    }
    paint();
  }
  function schedule() {
    clearTimeout(timer);
    if (document.hidden) return;
    timer = setTimeout(async () => { await refresh(); schedule(); }, reader.items().some(x => x.state === "processing") ? 1500 : 5000);
  }
  function start() {
    void refresh().then(schedule);
    document.addEventListener("visibilitychange", () => { if (document.hidden) clearTimeout(timer); else void refresh().then(schedule); });
    window.addEventListener("focus", () => { void refresh().then(schedule); });
    window.addEventListener("career-ai-activity-change", () => {
      void refresh().then(schedule);
      // A confirm may not yet have reserved its server operation at the first read.
      // Recheck metadata shortly afterwards; neither read can dispatch a request.
      setTimeout(() => { void refresh().then(schedule); }, 250);
    });
  }
  return { mount, start, refresh, openPanel };
}
