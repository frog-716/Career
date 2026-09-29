type Obj = Record<string, any>;

export const semanticWikiUI = {
  browse: "recent",
  scope: "all",
  status: "current",
  selected: "",
  historyId: "",
  legacyView: false,
};

export const knowledgeTypeLabels: Record<string, string> = {
  fact: "已确认事实",
  observation: "观察",
  hypothesis: "待验证判断",
};
export function knowledgeTypeLabel(type: string) {
  return knowledgeTypeLabels[type] || "知识";
}
export function wikiHistoryStatusLabel(item: Obj, revisions: Obj[]) {
  const latestRevision = Math.max(0, ...(revisions || []).map((revision) => Number(revision.revision) || 0));
  if (Number(item.revision) !== latestRevision) return "历史";
  return item.status === "retired" ? "不再有效" : "当前";
}
const sourceNames: Record<string, string> = {
  wiki_knowledge: "经历中的 Wiki 知识",
  raw_material: "手工原文",
  knowledge_source: "原始资料",
  work_project_source: "项目原文",
  work_event: "工作事件原文",
  work_evidence: "证据原文",
  journey_note: "任职 / 机会原文",
  interview_raw: "面试转写",
  communication: "沟通记录",
};
export function sourceLabel(source: Obj) {
  if (source.kind === "interview_raw") {
    if (source.source_kind === "simulation_interview_transcript") return "模拟面试转写";
    if (source.source_kind === "real_interview_transcript") return "真实面试转写";
    if (source.source_kind === "legacy_interview_transcript") return "历史面试转写";
  }
  return sourceNames[source.kind] || source.source_kind || "原始资料";
}
const esc = (v: any) =>
  String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
      c
    ]!,
  );

const compilerScopeLabel = (scope: Obj) => {
  const identity = scope.minimal_identity || scope.scope_identity || {};
  if (scope.type === "project") return `项目 · ${identity.name || "项目"}`;
  if (scope.type === "employment") {
    const name = [identity.company, identity.role].filter(Boolean).join(" / ");
    return `任职 · ${name || "任职"}`;
  }
  if (scope.type === "person") {
    const role = identity.project_role || identity.employment_role;
    return `人物 · ${identity.name || "人物"}${role ? ` · ${role}` : ""}`;
  }
  if (scope.type === "opportunity") {
    const name = [identity.company, identity.title].filter(Boolean).join(" / ");
    return `机会 · ${name || "机会"}`;
  }
  if (scope.type === "cognition") return "长期认知";
  return scope.type === "personal" ? "个人职业资料" : "相关资料";
};

export function proposalScopeLabel(proposal: Obj, patch: Obj, fallback: string) {
  const scope = (proposal.scopes || []).find((item: Obj) => item.type === patch.scope_type && item.stable_id === patch.scope_id);
  return scope ? compilerScopeLabel(scope) : fallback;
}

function compilerTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value || "")
    : new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function wikiCompilerPreviewHTML(context: Obj, details: Obj = {}) {
  const scopes = (context.scopes || []).map(compilerScopeLabel);
  const scopeList = scopes.map((label: string) => `<li>${esc(label)}</li>`).join("");
  const knowledge = (context.current_knowledge || []).map((item: Obj) => {
    const tags = (item.tags || []).map((tag: string) => esc(String(tag).replace(/^#+/, ""))).filter(Boolean).join("、");
    return `<article class="d2-preview-item"><small>${esc(knowledgeTypeLabel(item.type))}</small><pre class="d2-preview-content">${esc(item.content)}</pre>${tags ? `<p class="muted d2-preview-tags">标签：${tags}</p>` : ""}</article>`;
  }).join("");
  const detailsScopes = (details.scopes || []).map((label: string) => esc(label)).join("、") || "当前范围";
  const recordedAt = context.raw?.created_at
    ? `<p class="muted d2-preview-time">资料记录时间：${esc(compilerTime(context.raw.created_at))}</p>` : "";
  return `<p class="d2-preview-summary">AI 会比较“新资料”和“Wiki 里已有的信息”，判断 Wiki 是否需要更新。</p><section class="d2-preview-section"><h4>新资料</h4><pre class="d2-preview-content">${esc(context.raw?.content || "")}</pre>${recordedAt}</section><section class="d2-preview-section"><h4>所属项目 / 任职 / 人物</h4>${scopeList ? `<ul class="d2-preview-scopes">${scopeList}</ul>` : '<p class="muted">个人职业资料</p>'}</section><section class="d2-preview-section"><h4>Wiki 里已有的信息</h4>${knowledge || '<p class="muted">当前没有 Wiki 信息。</p>'}</section><section class="d2-preview-explainer"><h4>AI 会判断</h4><ul><li>有没有值得新增的信息</li><li>已有信息是否需要修改</li><li>有没有已经失效的信息</li></ul></section><p class="d2-preview-boundary">仅限上面这些内容，不会读取其他 Career 资料。</p><details class="d2-preview-details"><summary>查看发送详情</summary><ul><li>模型：${esc(details.model || "当前配置")}</li><li>新资料：${esc(details.raw_count ?? 1)}</li><li>当前知识：${esc(details.wiki_count ?? 0)}</li><li>范围：${detailsScopes}</li></ul></details><button type="button" class="primary full" data-d2-confirm>让 AI 整理</button><button type="button" class="text-btn full" data-d2-cancel>取消</button>`;
}

export function wikiCompilerFrozenBefore(patch: Obj, revisions: Obj[]) {
  if (patch.operation !== "rewrite" && patch.operation !== "retire") return undefined;
  const frozen = (revisions || []).find((item: Obj) => item.revision === patch.before_revision);
  if (!frozen || typeof frozen.content !== "string") {
    throw new Error("找不到建议对应的 Wiki 原始版本，已停止审批。");
  }
  return frozen.content;
}

export function wikiCompilerPatchHTML(
  patch: Obj, beforeContent: string | undefined, scope: string, editing = false,
  options: { cognition?: boolean; supportingExperiences?: Obj[] } = {},
) {
  const operation = patch.operation;
  const isAdd = operation === "add";
  const isRewrite = operation === "rewrite";
  const isRetire = operation === "retire";
  const title = isAdd ? "新增信息" : isRewrite ? "修改已有信息" : "建议将这条信息标记为不再有效";
  const details = isAdd
    ? `<h4>建议新增</h4><pre class="preserve">${esc(patch.content)}</pre>`
    : isRewrite
      ? `<h4>原来</h4><pre class="preserve">${esc(beforeContent)}</pre><h4>建议改为</h4><pre class="preserve">${esc(patch.content)}</pre>`
      : `<h4>当前信息</h4><pre class="preserve">${esc(beforeContent)}</pre>`;
  const editField = isRetire
    ? `<label>编辑退役原因<textarea data-d2-edit-value maxlength="1000">${esc(patch.reason)}</textarea></label><p class="muted">退役原因只记录在审批结果中，不会改写 Wiki 正文。</p>`
    : `<label>${isAdd ? "建议新增" : "建议改为"}<textarea data-d2-edit-value maxlength="100000">${esc(patch.content)}</textarea></label>`;
  const editDetails = isRetire
    ? `<h4>当前信息</h4><pre class="preserve">${esc(beforeContent)}</pre>${editField}`
    : isRewrite
      ? `<h4>原来</h4><pre class="preserve">${esc(beforeContent)}</pre>${editField}`
      : editField;
  const body = editing ? editDetails : details;
  if (options.cognition) {
    const cognitionBody = editing
      ? editDetails
      : isAdd
        ? `<h4>${esc(knowledgeTypeLabel(patch.knowledge_type))}</h4><pre class="preserve">${esc(patch.content)}</pre>`
        : isRewrite
          ? `<h4>${esc(knowledgeTypeLabel(patch.knowledge_type))} · 修改已有信息</h4><h5>原来</h5><pre class="preserve">${esc(beforeContent)}</pre><h5>建议改为</h5><pre class="preserve">${esc(patch.content)}</pre>`
          : `<h4>${esc(knowledgeTypeLabel(patch.knowledge_type))} · 标记为不再有效</h4><h5>当前信息</h5><pre class="preserve">${esc(beforeContent)}</pre>`;
    const experiences = (options.supportingExperiences || []).map((item: Obj) =>
      `<li>${esc(item.label || item.name || experienceName(item.type))}</li>`,
    ).join("");
    const reason = patch.reason
      ? `<details><summary>为什么？</summary><p>${esc(patch.reason)}</p></details>` : "";
    const support = `<h4>支持经历</h4><ul>${experiences || '<li class="muted">来源经历暂不可显示。</li>'}</ul>`;
    const cognitionActions = editing
      ? '<button type="button" class="primary" data-d2-confirm-edit>确认修改并接受</button><button type="button" class="text-btn" data-d2-cancel-edit>取消编辑</button><button type="button" class="text-btn" data-d2-reject>拒绝</button>'
      : '<button type="button" class="primary" data-d2-accept>接受</button><button type="button" class="secondary" data-d2-edit-accept>编辑后接受</button><button type="button" class="text-btn" data-d2-reject>拒绝</button>';
    return `<article class="work-domain-card d2-proposal-patch d4-cognition-proposal">${cognitionBody}${support}${reason}<div class="actions">${cognitionActions}</div></article>`;
  }
  const refs = (patch.source_refs || []).map((ref: Obj) => ref.kind === "wiki_knowledge"
    ? `<button type="button" class="text-btn" data-d4-open-wiki-source="${esc(ref.id)}" data-d4-source-revision="${esc(ref.revision)}">查看支撑知识 →</button>`
    : `<button type="button" class="text-btn" data-d1-open-raw-kind="${esc(ref.kind)}" data-d1-open-raw-id="${esc(ref.id)}" data-d1-open-raw-revision="${esc(ref.revision)}" data-d1-open-raw-hash="${esc(ref.hash)}">查看本轮原文 →</button>`).join("");
  const actions = editing
    ? '<button type="button" class="primary" data-d2-confirm-edit>确认修改并接受</button><button type="button" class="text-btn" data-d2-cancel-edit>取消编辑</button><button type="button" class="text-btn" data-d2-reject>拒绝</button>'
    : '<button type="button" class="primary" data-d2-accept>接受</button><button type="button" class="secondary" data-d2-edit-accept>编辑后接受</button><button type="button" class="text-btn" data-d2-reject>拒绝</button>';
  return `<article class="work-domain-card d2-proposal-patch"><small class="d2-patch-scope">${esc(scope)}</small><h3>${title}</h3>${body}<p><b>原因：</b>${esc(patch.reason)}</p><p><b>来源：</b>${refs}</p><div class="actions">${actions}</div></article>`;
}

export function scopeKey(scopeType: string, scopeId: string) {
  return scopeType === "personal" || scopeType === "cognition"
    ? scopeType
    : `${scopeType}:${scopeId}`;
}

function labelFor(d: Obj, scopeType: string, scopeId: string) {
  if (scopeType === "personal") return "个人职业资料";
  if (scopeType === "cognition") return "长期认知";
  if (scopeType === "project") {
    const item = (d.workDomain.projects || []).find((x: Obj) => x.id === scopeId);
    return `项目 · ${item?.name || "未知项目"}`;
  }
  if (scopeType === "employment") {
    const item = (d.workDomain.employments || []).find((x: Obj) => x.id === scopeId);
    return `任职 · ${item ? `${item.company} / ${item.role}` : "未知任职"}`;
  }
  if (scopeType === "person") {
    const item = (d.workDomain.persons || []).find((x: Obj) => x.id === scopeId);
    return `人物 · ${item?.name || "未知人物"}`;
  }
  if (scopeType === "opportunity") {
    const item = (d.state.opportunities || []).find((x: Obj) => x.id === scopeId);
    return `机会 · ${item ? `${item.company} / ${item.title}` : "未知机会"}`;
  }
  return "未知范围";
}

function rawLink(source: Obj, label = source.title) {
  const ref = source.source_ref || source;
  if (ref.kind === "wiki_knowledge") {
    return `<button class="text-btn" data-d4-open-wiki-source="${esc(ref.id)}" data-d4-source-revision="${esc(ref.revision)}">${esc(label || "查看支撑知识 →")}</button>`;
  }
  return `<button class="text-btn" data-d1-open-raw-kind="${esc(ref.kind)}" data-d1-open-raw-id="${esc(ref.id)}" data-d1-open-raw-revision="${esc(ref.revision)}" data-d1-open-raw-hash="${esc(ref.hash)}">${esc(label)}</button>`;
}

function experienceName(type: string) {
  return type === "project" ? "项目" : "任职";
}

export function cognitionExperiencePickerHTML(experiences: Obj[], preselected: Obj[] = []) {
  const rows = (experiences || []).map((item: Obj) => {
    const noKnowledge = Number(item.current_knowledge_count || 0) === 0;
    const checked = preselected.some((ref) => ref.type === item.type && ref.id === item.id);
    const value = encodeURIComponent(JSON.stringify({ type: item.type, id: item.id }));
    const status = item.status === "ended" ? "已结束" : item.status === "completed" ? "已完成" : item.status === "canceled" ? "已取消" : "进行中";
    return `<label class="d4-experience-choice ${noKnowledge ? "disabled" : ""}"><input type="checkbox" data-d4-experience value="${esc(value)}" ${checked && !noKnowledge ? "checked" : ""} ${noKnowledge ? "disabled" : ""}><span><b>${esc(experienceName(item.type))} · ${esc(item.name)}</b><small>${status} · ${Number(item.current_knowledge_count || 0)} 条当前 Wiki${noKnowledge ? " · 先整理 Wiki 信息" : ""}</small></span></label>`;
  }).join("");
  return `<p class="muted">选择至少两段、最多20段不同的项目或任职经历。每段都需要有当前 Wiki 信息；多条 Wiki 如果属于同一段经历，仍只算一段。</p><fieldset class="d4-experience-list">${rows || '<p class="muted">还没有可选择的项目或任职经历。</p>'}</fieldset><p class="d4-selection-error" data-d4-selection-error hidden></p><button type="button" class="primary full" data-d4-prepare>查看 AI 会读取的内容</button><button type="button" class="text-btn full" data-d4-cancel>取消</button>`;
}

export function cognitionPreviewHTML(context: Obj, details: Obj = {}) {
  const wikiCount = (context.selected_experiences || []).reduce(
    (total: number, experience: Obj) => total + (experience.current_knowledge || []).length, 0,
  );
  const experiences = (context.selected_experiences || []).map((experience: Obj) => {
    const knowledge = (experience.current_knowledge || []).map((item: Obj) => {
      const tags = (item.tags || []).map((tag: string) => esc(String(tag).replace(/^#+/, ""))).filter(Boolean).join("、");
      return `<article class="d2-preview-item"><small>${esc(knowledgeTypeLabel(item.type))}</small><pre class="d2-preview-content">${esc(item.content)}</pre>${tags ? `<p class="muted d2-preview-tags">标签：${tags}</p>` : ""}</article>`;
    }).join("");
    return `<section class="d2-preview-section"><h4>${experienceName(experience.type)} · ${esc(experience.name)}</h4>${knowledge}</section>`;
  }).join("");
  const existingItems = context.existing_cognition || [];
  const existing = existingItems.map((item: Obj) =>
    `<article class="d2-preview-item"><small>${esc(knowledgeTypeLabel(item.type))}</small><pre class="d2-preview-content">${esc(item.content)}</pre></article>`,
  ).join("");
  const existingSection = existingItems.length
    ? `<details class="d2-preview-details d4-existing-cognition"><summary>已有长期认知（${existingItems.length}）</summary>${existing}</details>`
    : "";
  const names = (details.experiences || []).map((value: string) => esc(value)).join("、");
  return `<h3>整理长期认知</h3><p class="d2-preview-summary">AI 将比较 ${Number((context.selected_experiences || []).length)} 段经历</p>${experiences || '<p class="muted">没有可读取的 Wiki 信息。</p>'}${existingSection}<p class="d2-preview-boundary">不会读取原始资料。</p><details class="d2-preview-details"><summary>查看发送详情</summary><ul><li>模型：${esc(details.model || "当前配置")}</li><li>所选经历：${names || Number(details.experience_count || 0)}</li><li>当前 Wiki：${wikiCount} 条</li>${existingItems.length ? `<li>已有长期认知：${existingItems.length} 条</li>` : ""}</ul></details><button type="button" class="primary full" data-d4-confirm>让 AI 整理</button><button type="button" class="text-btn full" data-d4-cancel>取消</button>`;
}

export function cognitionOutputErrorHTML() {
  return `<section class="notice d4-output-invalid"><b>AI 返回的结果无法安全使用，本次没有修改长期认知。</b><button type="button" class="text-btn" data-d4-output-invalid>关闭</button></section>`;
}

export function cognitionWikiHTML(data: Obj, status = "current", selectedId = "") {
  const snapshot = { ...semanticWikiUI };
  Object.assign(semanticWikiUI, { browse: "cognition", scope: "cognition", status, selected: selectedId });
  try { return wikiSemanticView({ state: {}, workDomain: {}, wikiSemantic: { cognition: data } }); }
  finally { Object.assign(semanticWikiUI, snapshot); }
}

export function wikiCompilerAction(source: Obj, targetScope?: Obj) {
  const ref = source.source_ref || source;
  if (ref.kind !== "raw_material" || source.source_kind !== "manual_text") return "";
  const target = targetScope
    ? ` data-d2-target-scope-type="${esc(targetScope.scope_type)}" data-d2-target-scope-id="${esc(targetScope.scope_id)}"`
    : "";
  const pending = Number(source.pending_patch_count || 0);
  return `<button class="secondary" data-d2-compile="${esc(ref.id)}"${target}>${pending > 0 ? "继续处理建议" : "整理到 Wiki"}</button>`;
}

function sourceRefKey(value: Obj) {
  const ref = value.source_ref || value;
  return JSON.stringify([ref.kind, ref.id, ref.revision, ref.hash]);
}

function knowledgeCard(item: Obj, rawItems: Obj[], showActions = true, historyOnly = false) {
  const refs = (item.source_refs || []).map((ref: Obj) => {
    const source = rawItems.find((x: Obj) => sourceRefKey(x) === sourceRefKey(ref));
    return rawLink(source || { ...ref, title: sourceNames[ref.kind] || "查看来源" }, source
      ? `${source.title} · ${sourceLabel(source)}${source.version_changed ? "（来源版本已变化）" : ""}`
      : `${sourceNames[ref.kind] || "来源"}（来源暂不可用）`);
  }).join("");
  const tags = (item.tags || []).map((tag: string) => `<span class="pill">${esc(tag.startsWith("#") ? tag : "#" + tag)}</span>`).join("");
  const actions = showActions
    ? `<div class="actions"><button class="text-btn" data-d1-edit-wiki="${esc(item.id)}">编辑</button>${item.status === "current" ? `<button class="text-btn" data-d1-retire-wiki="${esc(item.id)}">标记不再有效</button>` : `<button class="text-btn" data-d1-revive-wiki="${esc(item.id)}">恢复为当前</button>`}<button class="text-btn" data-d1-wiki-history="${esc(item.id)}">历史</button></div>`
    : historyOnly ? `<div class="actions"><button class="text-btn" data-d1-wiki-history="${esc(item.id)}">历史</button></div>` : "";
  return `<article class="work-domain-card wiki-knowledge-card" data-d1-knowledge="${esc(item.id)}"><div class="pane-heading"><div><small>${esc(knowledgeTypeLabel(item.knowledge_type))} · ${item.status === "retired" ? "不再有效" : "当前"}</small><p class="preserve">${esc(item.content)}</p></div>${actions}</div><div class="actions project-tags">${tags || '<span class="muted">无 Tags</span>'}</div><div class="source-links"><small>${refs ? "来源" : "手工写入 · 未引用原文"}</small>${refs}</div></article>`;
}

const knowledgeTypeOrder: Record<string, number> = {
  fact: 0, observation: 1, hypothesis: 2,
};

export function sortCurrentWikiKnowledge(items: Obj[]) {
  return [...(items || [])].filter((item) => item.status !== "retired").sort((left, right) => {
    const typeOrder = (knowledgeTypeOrder[left.knowledge_type] ?? 99)
      - (knowledgeTypeOrder[right.knowledge_type] ?? 99);
    if (typeOrder) return typeOrder;
    const leftTime = String(left.updated_at || left.created_at || "");
    const rightTime = String(right.updated_at || right.created_at || "");
    if (leftTime !== rightTime) return rightTime.localeCompare(leftTime);
    return Number(right.revision || 0) - Number(left.revision || 0);
  });
}

function rawTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value || "")
    : new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function shanghaiDateParts(date: Date) {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Shanghai", year: "numeric", month: "numeric", day: "numeric" }).formatToParts(date);
  const pick = (type: string) => Number(parts.find((part) => part.type === type)?.value || 0);
  return { year: pick("year"), month: pick("month"), day: pick("day") };
}
export function wikiReadingDay(value: string, now = new Date()) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value || "");
  const target = shanghaiDateParts(date), today = shanghaiDateParts(now);
  const ordinal = (x: { year: number; month: number; day: number }) => Date.UTC(x.year, x.month - 1, x.day) / 86400000;
  const difference = ordinal(today) - ordinal(target);
  if (difference === 0) return "今天";
  if (difference === 1) return "昨天";
  return `${target.month}月${target.day}日`;
}
export function wikiHistoryTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value || "");
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Shanghai", year: "2-digit", month: "numeric", day: "numeric",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(date);
  const pick = (type: string) => parts.find((part) => part.type === type)?.value || "";
  return `${pick("year")}年${Number(pick("month"))}月${Number(pick("day"))}日 ${pick("hour")}:${pick("minute")}`;
}
function sourceDisplayTitle(value: unknown) {
  const title = String(value || "").trim();
  const shorter = title.replace(/^(?:(?:20\d{2}年)?\d{1,2}月\d{1,2}日|\d{4}[-/]\d{1,2}[-/]\d{1,2})(?:\s+\d{1,2}:\d{2})?(?:\s*[·•｜|]\s*|\s*)/, "").trim();
  return shorter || title;
}

export function scopeRawHTML(scopeType: string, scopeId: string, rawItems: Obj[]) {
  const scope = { scope_type: scopeType, scope_id: scopeId };
  const rows = (rawItems || []).map((item: Obj) => `<div class="setting-row d3-raw-row"><span><b>${esc(item.title || "未命名资料")}</b><small>${esc(rawTime(item.created_at))} · ${esc(sourceLabel(item))}</small>${Number(item.pending_patch_count || 0) > 0 ? `<small>${esc(item.pending_patch_count)} 条建议待处理</small>` : ""}</span><div class="actions">${rawLink(item, "查看")}${wikiCompilerAction(item, scope)}</div></div>`).join("");
  return `<section class="work-domain-card d3-scope-raw" data-d3-raw-scope-type="${esc(scopeType)}" data-d3-raw-scope-id="${esc(scopeId)}"><div class="pane-heading"><div><h2>资料</h2><p class="muted">只显示这个对象自己的原始资料。</p></div><button class="secondary" data-d1-add-raw data-d1-scope-type="${esc(scopeType)}" data-d1-scope-id="${esc(scopeId)}">添加资料</button></div>${rows || '<p class="muted">还没有资料。</p>'}</section>`;
}

export function wikiCurrentUnderstandingHTML(
  scopeType: string, scopeId: string, knowledge: Obj[], rawItems: Obj[],
  options: { showActions?: boolean } = {},
) {
  const rows = sortCurrentWikiKnowledge(knowledge);
  const cards = rows.map((item: Obj) => knowledgeCard(
    item, rawItems, options.showActions === true, options.showActions !== true,
  )).join("");
  return `<section class="work-domain-card d3-current-understanding" data-d3-wiki-scope-type="${esc(scopeType)}" data-d3-wiki-scope-id="${esc(scopeId)}"><div class="pane-heading"><div><h2>当前理解</h2><p class="muted">这是这个对象当前 Wiki 的内容。</p></div><div class="actions"><button class="text-btn" data-d3-open-wiki-scope-type="${esc(scopeType)}" data-d3-open-wiki-scope-id="${esc(scopeId)}">在 Wiki 查看历史</button>${options.showActions ? `<button class="primary" data-d1-add-wiki data-d1-scope-type="${esc(scopeType)}" data-d1-scope-id="${esc(scopeId)}">写入 Wiki</button>` : ""}</div></div>${cards || '<p class="muted">目前还没有值得长期保留的知识。</p>'}</section>`;
}

/** UX-2: read-only projections over the existing knowledge and revision records. */
export function wikiReadingQuery() {
  const params = new URLSearchParams({ browse: semanticWikiUI.browse, scope: semanticWikiUI.scope,
    status: semanticWikiUI.status, knowledge: semanticWikiUI.selected });
  if (semanticWikiUI.historyId) params.set("history", semanticWikiUI.historyId);
  return params.toString();
}
export function restoreWikiReadingRoute(params: URLSearchParams) {
  const browse = params.get("browse") || "recent";
  semanticWikiUI.browse = ["recent", "project", "employment", "person", "cognition"].includes(browse) ? browse : "recent";
  semanticWikiUI.scope = params.get("scope") || (browse === "cognition" ? "cognition" : "all");
  semanticWikiUI.status = ["current", "retired", "all"].includes(params.get("status") || "") ? params.get("status")! : "current";
  semanticWikiUI.selected = params.get("knowledge") || "";
  semanticWikiUI.historyId = params.get("history") || "";
  semanticWikiUI.legacyView = false;
}
export async function loadWikiReadingPages(api: (path: string) => Promise<Obj>, query: URLSearchParams) {
  const params = new URLSearchParams(query);
  const historyId = params.get("history") || "";
  params.delete("history");
  const items: Obj[] = [], source_catalog: Obj[] = [];
  const seen = new Set<string>();
  while (true) {
    const result = await api("/wiki?" + params.toString());
    items.push(...(result.items || result));
    source_catalog.push(...(result.source_catalog || []));
    if (!result.next_cursor) break;
    if (seen.has(result.next_cursor)) throw new Error("无法载入下一页，请稍后重新打开 Wiki。");
    seen.add(result.next_cursor);
    params.set("cursor", result.next_cursor);
  }
  let history_revisions: Obj[] = [], history_catalog: Obj[] = [];
  if (historyId) {
    const history = await api(`/wiki/${encodeURIComponent(historyId)}/history`);
    history_revisions = history.revisions || [];
    const latest = history_revisions[history_revisions.length - 1];
    if (latest && latest.scope_type !== "cognition") {
      const sources = await api(`/raw?scope_type=${encodeURIComponent(latest.scope_type)}&scope_id=${encodeURIComponent(latest.scope_id)}`);
      history_catalog = sources.items || [];
    }
  }
  return { items, source_catalog, next_cursor: "", history_revisions, history_catalog };
}

const readingTabs = [["recent", "最近更新"], ["project", "项目"], ["employment", "任职"], ["person", "人物"], ["cognition", "长期认知"]];
function readingObjectName(d: Obj, item: Obj) {
  return labelFor(d, item.scope_type, item.scope_id).replace(/^(项目|任职|人物|机会) · /, "");
}
function readingObjectKind(item: Obj) {
  return ({ project: "项目", employment: "任职", person: "人物", opportunity: "机会", cognition: "长期认知", personal: "个人职业资料" } as Record<string, string>)[item.scope_type] || "职业资料";
}
export function recentWikiKnowledge(items: Obj[]) {
  return [...items].sort((a, b) => String(b.updated_at || b.created_at || "").localeCompare(String(a.updated_at || a.created_at || "")) || String(a.id).localeCompare(String(b.id)));
}
function readingSources(item: Obj, catalog: Obj[]) {
  const refs = item.source_refs || [];
  const rows = refs.map((ref: Obj) => {
    const source = catalog.find((x: Obj) => sourceRefKey(x) === sourceRefKey(ref));
    const title = source?.title || (ref.kind === "wiki_knowledge" ? "支撑这条判断的知识" : "查看来源");
    return `<li><span class="reading-source-prefix">来源 · </span>${rawLink({ ...ref, title }, title)}${source?.version_changed ? '<span class="reading-meta">来源已更新</span>' : ""}</li>`;
  }).join("");
  if (!rows) return '<p class="reading-source-line reading-meta">由你记录，未关联资料</p>';
  return refs.length > 1
    ? `<details class="reading-section reading-sources"><summary>来源 · ${refs.length}</summary><ul>${rows}</ul></details>`
    : `<section class="reading-section reading-sources"><ul>${rows}</ul></section>`;
}
function readingActions(item: Obj) {
  return `<details class="reading-more"><summary>更多操作</summary><div class="reading-menu"><button data-d1-edit-wiki="${esc(item.id)}">编辑</button>${item.status === "current" ? `<button data-d1-retire-wiki="${esc(item.id)}">不再有效</button>` : `<button data-d1-revive-wiki="${esc(item.id)}">恢复为当前</button>`}</div></details>`;
}
function knowledgeReadingHTML(d: Obj, item: Obj, catalog: Obj[]) {
  const tags = (item.tags || []).map((t: string) => esc(t.startsWith("#") ? t : "#" + t)).join("　");
  const support = (item.supporting_experiences || []).map((x: Obj) => `<li><button class="text-btn" data-d4-open-experience-type="${esc(x.type)}" data-d4-open-experience-id="${esc(x.id)}">${esc(x.name)}</button></li>`).join("");
  const sources = item.scope_type === "cognition" && (item.source_refs || []).some((r: Obj) => r.kind === "wiki_knowledge")
    ? `<section class="reading-section"><h4>支持这个判断的经历</h4>${support ? `<ul>${support}</ul>` : ""}<button class="reading-source-link" data-d4-open-source-tree="${esc(item.id)}">查看支撑知识 →</button></section>`
    : readingSources(item, catalog);
  const owner = labelFor(d, item.scope_type, item.scope_id);
  return `<article class="reading-detail"><p class="reading-owner">${esc(owner)}</p><div class="reading-body preserve reading-detail-content">${esc(item.content)}</div>${sources}<div class="reading-kind">${esc(knowledgeTypeLabel(item.knowledge_type))}${item.status === "retired" ? '<span class="reading-retired">不再有效</span>' : ""}</div>${tags ? `<p class="reading-meta reading-tags">${tags}</p>` : ""}<footer class="reading-footer">${readingActions(item)}<button class="reading-history-link" data-d1-wiki-history="${esc(item.id)}">历史</button></footer></article>`;
}
function readingRows(d: Obj, items: Obj[], showOwner = true) {
  const catalog = (d.wikiSemantic?.raw || []).concat(d.wikiSemantic?.sourceCatalog || []);
  return `<div class="reading-list">${items.map(item => {
    const refs = item.source_refs || [];
    const source = refs.length === 1 ? catalog.find((x: Obj) => sourceRefKey(x) === sourceRefKey(refs[0]))?.title : "";
    const meta = `${esc(readingObjectKind(item))} · ${esc(wikiReadingDay(item.updated_at || item.created_at || ""))}`;
    const owner = showOwner && item.scope_type !== "cognition" ? `<strong>${esc(readingObjectName(d, item))}</strong>` : "";
    return `<button class="reading-row" data-d1-select-wiki="${esc(item.id)}"><span class="reading-excerpt">${esc(item.content)}</span>${owner}<span class="reading-row-meta">${meta}</span>${source ? `<span class="reading-row-source">来源 · ${esc(sourceDisplayTitle(source))}</span>` : refs.length > 1 ? `<span class="reading-row-source">${refs.length} 条来源</span>` : ""}</button>`;
  }).join("")}</div>`;
}
function readingFilter() {
  return `<details class="reading-filter"><summary>筛选</summary><label>显示<select aria-label="知识状态" id="d1-wiki-status"><option value="current" ${semanticWikiUI.status === "current" ? "selected" : ""}>有效信息</option><option value="retired" ${semanticWikiUI.status === "retired" ? "selected" : ""}>不再有效</option><option value="all" ${semanticWikiUI.status === "all" ? "selected" : ""}>全部</option></select></label></details>`;
}
export function wikiHistoryHTML(revisions: Obj[], catalog: Obj[]) {
  const ordered = [...revisions].sort((a, b) => Number(b.revision) - Number(a.revision));
  if (!ordered.length) return '<div class="reading-surface reading-history"><p class="reading-empty">暂无历史。</p></div>';
  const sourceLine = (item: Obj) => {
    const refs = item.source_refs || [];
    const links = refs.map((ref: Obj) => {
      const source = catalog.find((x: Obj) => sourceRefKey(x) === sourceRefKey(ref));
      const title = sourceDisplayTitle(source?.title || (ref.kind === "wiki_knowledge" ? "支撑这条判断的知识" : "原始资料"));
      return rawLink({ ...ref, title }, `${title} →`);
    }).join("、");
    if (!refs.length) return "";
    return `<p class="reading-history-source">${links}</p>`;
  };
  const current = ordered[0];
  const currentLabel = wikiHistoryStatusLabel(current, revisions);
  const currentHTML = `<section class="reading-history-current"><header><strong>${esc(currentLabel)}</strong><time class="reading-meta">${esc(wikiHistoryTime(current.updated_at || current.created_at || ""))}</time></header><p class="reading-body preserve">${esc(current.content)}</p>${sourceLine(current)}</section>`;
  const previous = ordered.slice(1);
  const previousHTML = previous.length
    ? `<section class="reading-history-previous"><h2>之前的变化</h2>${previous.map(item => `<article class="reading-history-item"><time class="reading-meta">${esc(wikiHistoryTime(item.updated_at || item.created_at || ""))}${Number(item.revision) === 1 ? " · 首次记录" : ""}</time><p class="reading-body preserve">${esc(item.content)}</p>${sourceLine(item)}</article>`).join("")}</section>`
    : "";
  return `<div class="reading-surface reading-history">${currentHTML}${previousHTML}</div>`;
}

export function wikiSemanticView(d: Obj) {
  const data = d.wikiSemantic || { items: [], raw: [] };
  const cognition = semanticWikiUI.scope === "cognition";
  const scoped = !["all", "cognition"].includes(semanticWikiUI.scope);
  const all = cognition && data.cognition ? [...(data.cognition.knowledge || []), ...(data.cognition.retired || [])] : data.items || [];
  const items = recentWikiKnowledge(all.filter((item: Obj) =>
    (item.scope_type !== "opportunity" || semanticWikiUI.scope === `opportunity:${item.scope_id}`)
    && (semanticWikiUI.status === "all" || item.status === semanticWikiUI.status)
    && (!scoped || scopeKey(item.scope_type, item.scope_id) === semanticWikiUI.scope),
  ));
  const selected = items.find((x: Obj) => x.id === semanticWikiUI.selected);
  const catalog = [...(data.raw || []), ...(data.sourceCatalog || [])];
  const activeTab = cognition ? "cognition" : scoped && ["project", "employment", "person"].includes(semanticWikiUI.scope.split(":")[0]) ? semanticWikiUI.scope.split(":")[0] : semanticWikiUI.browse;
  const tabs = semanticWikiUI.historyId ? "" : `<nav class="reading-tabs" aria-label="Wiki 浏览">${readingTabs.map(([key, label]) => `<button data-wiki-browse="${key}" aria-current="${key === activeTab ? "page" : "false"}">${label}</button>`).join("")}</nav>`;
  const more = `<details class="reading-more"><summary>更多</summary><div class="reading-menu"><button data-wiki-personal>个人职业资料</button><button data-open-legacy-wiki>历史 / 旧资料</button>${scoped ? '<button data-d1-add-wiki>手工记一条</button>' : ""}</div></details>`;
  const title = scoped ? readingObjectName(d, { scope_type: semanticWikiUI.scope.split(":")[0], scope_id: semanticWikiUI.scope.slice(semanticWikiUI.scope.indexOf(":") + 1) }) : cognition ? "长期认知" : (readingTabs.find(([key]) => key === activeTab)?.[1] || "最近更新");
  let content: string;
  if (semanticWikiUI.historyId) {
    content = `<button class="reading-back" data-wiki-history-back>← 返回条目</button>${wikiHistoryHTML(data.history_revisions || [], [...(data.raw || []), ...(data.history_catalog || [])])}`;
  } else if (selected) {
    content = `<button class="reading-back" data-wiki-back>← 返回${esc(title)}</button>${knowledgeReadingHTML(d, selected, catalog)}`;
  } else {
    const pending = cognition ? (data.cognition?.proposals || []).filter((x: Obj) => x.status === "pending") : [];
    const notices = pending.map((x: Obj) => `<div class="reading-pending"><span>有长期认知建议待处理</span><button class="text-btn" data-d4-resume-proposal="${esc(x.id)}">继续</button></div>`).join("");
    const heading = `<header class="reading-section-heading"><h2>${esc(title)}</h2>${cognition ? '<button class="secondary" data-d4-start>选择经历整理</button>' : readingFilter()}</header>`;
    if (!scoped && ["project", "employment", "person"].includes(activeTab)) {
      const seen = new Set<string>();
      const representatives = items.filter((item: Obj) => { if (item.scope_type !== activeTab || seen.has(item.scope_id)) return false; seen.add(item.scope_id); return true; });
      content = heading + (representatives.length ? `<div class="reading-list">${representatives.map((item: Obj) => `<button class="reading-row" data-wiki-object="${esc(scopeKey(item.scope_type, item.scope_id))}"><strong>${esc(readingObjectName(d, item))}</strong><span class="reading-excerpt">${esc(item.content)}</span></button>`).join("")}</div>` : '<p class="reading-empty">还没有整理过的信息。</p>');
    } else {
      content = heading + notices + (items.length ? readingRows(d, items, !scoped && !cognition) : `<p class="reading-empty">${cognition ? "当前没有长期认知。" : "还没有整理过的信息。"}</p>`);
      if (cognition) content += readingFilter();
    }
  }
  return `<section class="reading-page d1-wiki career-visual"><div class="reading-surface"><header class="reading-page-heading"><div><h1>Wiki</h1>${semanticWikiUI.historyId ? "" : "<p>Career 最近记住了什么重要信息</p>"}</div></header>${tabs}${semanticWikiUI.status === "retired" && !selected && !semanticWikiUI.historyId ? '<p class="reading-meta">正在查看不再有效的信息</p>' : ""}${content}${semanticWikiUI.historyId ? "" : `<footer class="reading-home-footer">${more}</footer>`}</div></section>`;
}

export function projectWikiHTML(project: Obj, data: Obj = {}) {
  const rawItems = data.raw || [];
  const current = data.knowledge || [];
  const retired = data.retired || [];
  const currentView = wikiCurrentUnderstandingHTML("project", project.id, current, rawItems, { showActions: true });
  const retiredView = retired.length
    ? `<details class="wiki-retired"><summary>不再有效的知识 · ${retired.length}</summary>${retired.map((item: Obj) => knowledgeCard(item, rawItems)).join("")}</details>`
    : "";
  const recap = ["completed", "canceled"].includes(project.status)
    ? `<button class="secondary" data-d4-start data-d4-prefill-type="project" data-d4-prefill-id="${esc(project.id)}">从这个项目整理长期认知</button>`
    : "";
  return `<div class="project-wiki">${recap}${currentView}${scopeRawHTML("project", project.id, rawItems)}${retiredView}</div>`;
}
