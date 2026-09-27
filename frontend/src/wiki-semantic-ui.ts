type Obj = Record<string, any>;

export const semanticWikiUI = {
  scope: "all",
  status: "current",
  selected: "",
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
  return scope.type === "personal" ? "个人职业资料" : "相关资料";
};

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
  const refs = (patch.source_refs || []).map((ref: Obj) =>
    `<button type="button" class="text-btn" data-d1-open-raw-kind="${esc(ref.kind)}" data-d1-open-raw-id="${esc(ref.id)}" data-d1-open-raw-revision="${esc(ref.revision)}" data-d1-open-raw-hash="${esc(ref.hash)}">查看本轮原文 →</button>`,
  ).join("");
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
  if (scopeType === "cognition") return "跨经历认知";
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

function scopeOptions(d: Obj) {
  const values: Array<[string, string]> = [
    ["personal", labelFor(d, "personal", "")],
    ["cognition", labelFor(d, "cognition", "")],
    ...(d.workDomain.projects || []).map((x: Obj) => [
      scopeKey("project", x.id), labelFor(d, "project", x.id),
    ] as [string, string]),
    ...(d.workDomain.employments || []).map((x: Obj) => [
      scopeKey("employment", x.id), labelFor(d, "employment", x.id),
    ] as [string, string]),
    ...(d.workDomain.persons || []).filter((x: Obj) => x.identity_status === "confirmed").map((x: Obj) => [
      scopeKey("person", x.id), labelFor(d, "person", x.id),
    ] as [string, string]),
    ...(d.state.opportunities || []).map((x: Obj) => [
      scopeKey("opportunity", x.id), labelFor(d, "opportunity", x.id),
    ] as [string, string]),
  ];
  return values.map(([value, label]) =>
    `<option value="${esc(value)}" ${value === semanticWikiUI.scope ? "selected" : ""}>${esc(label)}</option>`,
  ).join("");
}

function rawLink(source: Obj, label = source.title) {
  const ref = source.source_ref || source;
  return `<button class="text-btn" data-d1-open-raw-kind="${esc(ref.kind)}" data-d1-open-raw-id="${esc(ref.id)}" data-d1-open-raw-revision="${esc(ref.revision)}" data-d1-open-raw-hash="${esc(ref.hash)}">${esc(label)}</button>`;
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

export function wikiSemanticView(d: Obj) {
  const data = d.wikiSemantic || { items: [], raw: [] };
  const items = data.items || [];
  const selected = items.find((x: Obj) => x.id === semanticWikiUI.selected) || items[0];
  if (selected && !items.some((x: Obj) => x.id === semanticWikiUI.selected)) semanticWikiUI.selected = selected.id;
  const chosen = semanticWikiUI.scope !== "all";
  const rawItems = data.raw || [];
  const sourceCatalog = [...rawItems, ...(data.sourceCatalog || [])];
  return `<section class="materials d1-wiki"><div class="pane-heading"><div><h2>Wiki</h2><p class="muted">这里放当前值得记住的已确认事实、观察和待验证判断。</p></div><div class="actions"><button class="text-btn" data-open-legacy-wiki>原求职资料</button></div></div><div class="pane-heading"><div class="actions"><select aria-label="Wiki 范围" id="d1-wiki-scope"><option value="all" ${semanticWikiUI.scope === "all" ? "selected" : ""}>全部知识</option>${scopeOptions(d)}</select><select aria-label="知识状态" id="d1-wiki-status"><option value="current" ${semanticWikiUI.status === "current" ? "selected" : ""}>当前</option><option value="retired" ${semanticWikiUI.status === "retired" ? "selected" : ""}>不再有效</option><option value="all" ${semanticWikiUI.status === "all" ? "selected" : ""}>全部</option></select></div><div class="actions"><button class="secondary" data-d1-add-raw ${chosen ? "" : "disabled"}>添加原始资料</button><button class="primary" data-d1-add-wiki ${chosen ? "" : "disabled"}>写入 Wiki</button></div></div><div class="split"><section class="entity-rail"><h3>知识</h3><div class="scroll rail-list">${items.map((item: Obj) => `<button class="entity-row ${selected?.id === item.id ? "selected" : ""}" data-d1-select-wiki="${esc(item.id)}"><b>${esc(knowledgeTypeLabel(item.knowledge_type))}</b><small>${esc(item.content)}</small><span>${esc(labelFor(d, item.scope_type, item.scope_id))} · ${item.status === "retired" ? "不再有效" : "当前"}</span></button>`).join("") || '<div class="empty">这个范围还没有 Wiki 知识。</div>'}</div></section><section class="detail-pane scroll">${selected ? `<div class="pane-heading"><div><small>${esc(labelFor(d, selected.scope_type, selected.scope_id))}</small><h3>${esc(knowledgeTypeLabel(selected.knowledge_type))}</h3><p class="muted">${selected.status === "retired" ? "不再有效" : "当前"}</p></div><div class="actions"><button class="secondary" data-d1-edit-wiki="${esc(selected.id)}">编辑</button>${selected.status === "current" ? `<button class="quiet" data-d1-retire-wiki="${esc(selected.id)}">标记不再有效</button>` : `<button class="quiet" data-d1-revive-wiki="${esc(selected.id)}">恢复为当前</button>`}<button class="text-btn" data-d1-wiki-history="${esc(selected.id)}">历史</button></div></div><p class="preserve">${esc(selected.content)}</p><div class="actions project-tags">${(selected.tags || []).map((tag: string) => `<span class="pill">${esc(tag.startsWith("#") ? tag : "#" + tag)}</span>`).join("") || '<span class="muted">无 Tags</span>'}</div><section><h4>来源</h4>${selected.source_refs?.length ? selected.source_refs.map((ref: Obj) => { const raw = sourceCatalog.find((x: Obj) => sourceRefKey(x) === sourceRefKey(ref)); return rawLink(raw || { ...ref, title: sourceNames[ref.kind] || "查看来源" }, raw ? `${raw.title} · ${sourceLabel(raw)}${raw.version_changed ? "（来源版本已变化）" : ""}` : `${sourceNames[ref.kind] || "来源"}（来源暂不可用）`); }).join("") : '<p class="muted">这是用户手工写入的知识，没有伪造原文来源。</p>'}</section>` : '<div class="empty">先选一个范围，再写入一条知识。</div>'}</section></div>${chosen ? `<section class="work-domain-card"><div class="pane-heading"><h3>这个范围的原始资料</h3><small>${rawItems.length} 条</small></div>${rawItems.map((item: Obj) => `<div class="setting-row"><span>${esc(item.title)} <small>${esc(sourceLabel(item))}</small>${Number(item.pending_patch_count || 0) > 0 ? `<small>${esc(item.pending_patch_count)} 条建议待处理</small>` : ""}</span><div class="actions">${rawLink(item, "打开原文 →")}${wikiCompilerAction(item)}</div></div>`).join("") || '<p class="muted">还没有原始资料。添加后可以在写 Wiki 时选择它。</p>'}</section>` : ""}</section>`;
}

export function projectWikiHTML(project: Obj, data: Obj = {}) {
  const rawItems = data.raw || [];
  const current = data.knowledge || [];
  const retired = data.retired || [];
  const currentView = wikiCurrentUnderstandingHTML("project", project.id, current, rawItems, { showActions: true });
  const retiredView = retired.length
    ? `<details class="wiki-retired"><summary>不再有效的知识 · ${retired.length}</summary>${retired.map((item: Obj) => knowledgeCard(item, rawItems)).join("")}</details>`
    : "";
  return `<div class="project-wiki">${currentView}${scopeRawHTML("project", project.id, rawItems)}${retiredView}</div>`;
}
