type Obj = Record<string, any>;

export const semanticWikiUI = {
  scope: "all",
  status: "current",
  selected: "",
  legacyView: false,
};

const typeNames: Record<string, string> = {
  fact: "Fact · 已确认事实",
  observation: "Observation · 观察",
  hypothesis: "Hypothesis · 待验证推测",
};
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

function sourceRefKey(value: Obj) {
  const ref = value.source_ref || value;
  return JSON.stringify([ref.kind, ref.id, ref.revision, ref.hash]);
}

function knowledgeCard(item: Obj, rawItems: Obj[], showActions = true) {
  const refs = (item.source_refs || []).map((ref: Obj) => {
    const source = rawItems.find((x: Obj) => sourceRefKey(x) === sourceRefKey(ref));
    return rawLink(source || { ...ref, title: sourceNames[ref.kind] || "查看来源" }, source ? `${source.title} · ${sourceLabel(source)}` : `${sourceNames[ref.kind] || "来源"}（版本可能已变化）`);
  }).join("");
  const tags = (item.tags || []).map((tag: string) => `<span class="pill">${esc(tag.startsWith("#") ? tag : "#" + tag)}</span>`).join("");
  return `<article class="work-domain-card wiki-knowledge-card" data-d1-knowledge="${esc(item.id)}"><div class="pane-heading"><div><small>${esc(typeNames[item.knowledge_type] || item.knowledge_type)} · ${item.status === "retired" ? "已退役" : "当前"}</small><p class="preserve">${esc(item.content)}</p></div>${showActions ? `<div class="actions"><button class="text-btn" data-d1-edit-wiki="${esc(item.id)}">编辑</button>${item.status === "current" ? `<button class="text-btn" data-d1-retire-wiki="${esc(item.id)}">退役</button>` : `<button class="text-btn" data-d1-revive-wiki="${esc(item.id)}">恢复为当前</button>`}<button class="text-btn" data-d1-wiki-history="${esc(item.id)}">历史</button></div>` : ""}</div><div class="actions project-tags">${tags || '<span class="muted">无 Tags</span>'}</div><div class="source-links"><small>${refs ? "来源" : "手工写入 · 未引用原文"}</small>${refs}</div></article>`;
}

export function wikiSemanticView(d: Obj) {
  const data = d.wikiSemantic || { items: [], raw: [] };
  const items = data.items || [];
  const selected = items.find((x: Obj) => x.id === semanticWikiUI.selected) || items[0];
  if (selected && !items.some((x: Obj) => x.id === semanticWikiUI.selected)) semanticWikiUI.selected = selected.id;
  const chosen = semanticWikiUI.scope !== "all";
  const rawItems = data.raw || [];
  return `<section class="materials d1-wiki"><div class="pane-heading"><div><h2>Wiki</h2><p class="muted">这里放当前值得记住的事实、观察和待验证想法。</p></div><div class="actions"><button class="text-btn" data-open-legacy-wiki>原求职资料</button></div></div><div class="pane-heading"><div class="actions"><select aria-label="Wiki 范围" id="d1-wiki-scope"><option value="all" ${semanticWikiUI.scope === "all" ? "selected" : ""}>全部长期范围</option>${scopeOptions(d)}</select><select aria-label="知识状态" id="d1-wiki-status"><option value="current" ${semanticWikiUI.status === "current" ? "selected" : ""}>当前</option><option value="retired" ${semanticWikiUI.status === "retired" ? "selected" : ""}>已退役</option><option value="all" ${semanticWikiUI.status === "all" ? "selected" : ""}>全部</option></select></div><div class="actions"><button class="secondary" data-d1-add-raw ${chosen ? "" : "disabled"}>添加原始资料</button><button class="primary" data-d1-add-wiki ${chosen ? "" : "disabled"}>写入 Wiki</button></div></div><div class="split"><section class="entity-rail"><h3>知识</h3><div class="scroll rail-list">${items.map((item: Obj) => `<button class="entity-row ${selected?.id === item.id ? "selected" : ""}" data-d1-select-wiki="${esc(item.id)}"><b>${esc(typeNames[item.knowledge_type] || item.knowledge_type)}</b><small>${esc(item.content)}</small><span>${esc(labelFor(d, item.scope_type, item.scope_id))} · ${item.status === "retired" ? "已退役" : "当前"}</span></button>`).join("") || '<div class="empty">这个范围还没有 Wiki 知识。</div>'}</div></section><section class="detail-pane scroll">${selected ? `<div class="pane-heading"><div><small>${esc(labelFor(d, selected.scope_type, selected.scope_id))}</small><h3>${esc(typeNames[selected.knowledge_type] || selected.knowledge_type)}</h3></div><div class="actions"><button class="secondary" data-d1-edit-wiki="${esc(selected.id)}">编辑</button>${selected.status === "current" ? `<button class="quiet" data-d1-retire-wiki="${esc(selected.id)}">退役</button>` : `<button class="quiet" data-d1-revive-wiki="${esc(selected.id)}">恢复为当前</button>`}<button class="text-btn" data-d1-wiki-history="${esc(selected.id)}">历史</button></div></div><p class="preserve">${esc(selected.content)}</p><div class="actions project-tags">${(selected.tags || []).map((tag: string) => `<span class="pill">${esc(tag.startsWith("#") ? tag : "#" + tag)}</span>`).join("") || '<span class="muted">无 Tags</span>'}</div><section><h4>来源</h4>${selected.source_refs?.length ? selected.source_refs.map((ref: Obj) => { const raw = rawItems.find((x: Obj) => sourceRefKey(x) === sourceRefKey(ref)); return rawLink(raw || { ...ref, title: sourceNames[ref.kind] || "查看来源" }, raw ? `${raw.title} · ${sourceLabel(raw)}` : `${sourceNames[ref.kind] || "来源"}（版本可能已变化）`); }).join("") : '<p class="muted">这是用户手工写入的知识，没有伪造原文来源。</p>'}</section>` : '<div class="empty">先选一个范围，再写入一条知识。</div>'}</section></div>${chosen ? `<section class="work-domain-card"><div class="pane-heading"><h3>这个范围的原始资料</h3><small>${rawItems.length} 条</small></div>${rawItems.map((item: Obj) => `<div class="setting-row"><span>${esc(item.title)} <small>${esc(sourceLabel(item))}</small></span>${rawLink(item, "打开原文 →")}</div>`).join("") || '<p class="muted">还没有原始资料。添加后可以在写 Wiki 时选择它。</p>'}</section>` : ""}</section>`;
}

export function projectWikiHTML(project: Obj, data: Obj = {}) {
  const rawItems = data.raw || [];
  const current = data.knowledge || [];
  const retired = data.retired || [];
  return `<section class="work-domain-card project-wiki"><div class="pane-heading"><div><h2>原始资料</h2><p class="muted">保存当时的原文；Wiki 编辑不会改动这里。</p></div><button class="secondary" data-d1-add-raw data-d1-scope-type="project" data-d1-scope-id="${esc(project.id)}">添加原始资料</button></div>${rawItems.map((item: Obj) => `<div class="setting-row"><span>${esc(item.title)} <small>${esc(sourceLabel(item))}</small></span>${rawLink(item, "打开原文 →")}</div>`).join("") || '<p class="muted">还没有原始资料。</p>'}<div class="pane-heading"><div><h2>Wiki 当前理解</h2><p class="muted">Fact、Observation 和 Hypothesis 可以分别修改或退役。</p></div><button class="primary" data-d1-add-wiki data-d1-scope-type="project" data-d1-scope-id="${esc(project.id)}">写入 Wiki</button></div>${current.map((item: Obj) => knowledgeCard(item, rawItems)).join("") || '<p class="muted">还没有当前 Wiki 知识。</p>'}${retired.length ? `<details class="wiki-retired"><summary>已退役知识 · ${retired.length}</summary>${retired.map((item: Obj) => knowledgeCard(item, rawItems)).join("")}</details>` : ""}</section>`;
}
