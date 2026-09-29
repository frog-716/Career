import {
  knowledgeTypeLabel,
  sortCurrentWikiKnowledge,
  wikiCompilerAction,
} from "./wiki-semantic-ui.ts";
import { participantsForProject, type ParticipantRow, type PersonRow, type ProjectRow } from "./person-relations.ts";

type Obj = Record<string, any>;
const e = (value: unknown): string => String(value ?? "").replace(/[&<>"']/g, (char) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!,
);

const projectStatuses: Record<string, string> = {
  active: "进行中", paused: "已暂停", completed: "已完成", canceled: "已取消",
};

function dateLabel(value: string | undefined) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", month: "numeric", day: "numeric",
  }).format(date);
}

function monthLabel(value: string | undefined) {
  if (!value) return "";
  const match = /^(\d{4})-(\d{2})/.exec(value);
  return match ? `${match[1]}.${match[2]}` : value;
}

function rawButton(item: Obj, label = "查看资料") {
  const ref = item.source_ref || item;
  return `<button class="ux3-source-link" data-d1-open-raw-kind="${e(ref.kind)}" data-d1-open-raw-id="${e(ref.id)}" data-d1-open-raw-revision="${e(ref.revision)}" data-d1-open-raw-hash="${e(ref.hash)}">${e(label)} →</button>`;
}

function sourceLinks(item: Obj, rawItems: Obj[]) {
  const sources = (item.source_refs || []).map((ref: Obj) => {
    const match = rawItems.find((raw) => {
      const candidate = raw.source_ref || raw;
      return candidate.kind === ref.kind && candidate.id === ref.id;
    });
    return match ? rawButton(match, match.title || "查看来源") : "";
  }).filter(Boolean).join("");
  return sources ? `<div class="ux3-source-links">${sources}</div>` : "";
}

function compactKnowledge(
  item: Obj, rawItems: Obj[], extraClass = "", options: { hideTypeLabel?: boolean } = {},
) {
  const tags = (item.tags || []).map((tag: string) => String(tag).replace(/^#+/, "")).filter(Boolean);
  const typeLabel = options.hideTypeLabel ? "" : `<div class="ux3-knowledge-type">${e(knowledgeTypeLabel(item.knowledge_type))}</div>`;
  return `<article class="ux3-knowledge-row ${extraClass}" data-ux3-knowledge="${e(item.id)}">${typeLabel}<p>${e(item.content)}</p>${tags.length ? `<small class="ux3-tags">${tags.map((tag: string) => `#${e(tag)}`).join(" · ")}</small>` : ""}${sourceLinks(item, rawItems)}<button class="ux3-history-link" data-d1-wiki-history="${e(item.id)}">历史</button></article>`;
}

function currentKnowledge(items: Obj[]) {
  return sortCurrentWikiKnowledge(items || []);
}

function latestCurrentKnowledge(items: Obj[]) {
  return currentKnowledge(items).slice().sort((left, right) =>
    String(right.updated_at || right.created_at || "").localeCompare(String(left.updated_at || left.created_at || "")),
  )[0];
}

function materialsHTML(
  scopeType: string, scopeId: string, rawItems: Obj[],
  options: { title?: string; limit?: number; directScopeOnly?: boolean } = {},
) {
  const ordered = (rawItems || []).slice().sort((a, b) =>
    String(b.created_at || "").localeCompare(String(a.created_at || "")),
  );
  const visible = options.directScopeOnly
    ? ordered.filter((item) => item.scope_type === scopeType && item.scope_id === scopeId)
    : ordered;
  const rows = (options.limit ? visible.slice(0, options.limit) : visible).map((item: Obj) => {
    const sourceName = item.source_kind === "manual_text" ? "手工资料"
      : item.source_kind === "document" ? "文档"
        : item.source_kind === "meeting" ? "会议记录" : "资料";
    return `<div class="ux3-material-row"><div class="ux3-material-main">${rawButton(item, item.title || "未命名资料")}<small>${dateLabel(item.created_at)} · ${sourceName}</small>${Number(item.pending_patch_count || 0) ? `<small>有 ${Number(item.pending_patch_count)} 条建议待处理</small>` : ""}</div><div class="ux3-material-actions">${wikiCompilerAction(item, { scope_type: scopeType, scope_id: scopeId })}</div></div>`;
  }).join("");
  return `<section class="ux3-section ux3-materials" data-ux3-material-scope="${e(scopeType)}:${e(scopeId)}"><div class="ux3-section-heading"><h3>${e(options.title || "资料")}</h3><button class="secondary" data-d1-add-raw data-d1-scope-type="${e(scopeType)}" data-d1-scope-id="${e(scopeId)}">+ 添加资料</button></div>${rows || `<p class="ux3-empty">还没有资料</p>`}</section>`;
}

function understandingHTML(items: Obj[], rawItems: Obj[], omitId = "") {
  const remaining = currentKnowledge(items).filter((item) => item.id !== omitId);
  if (!remaining.length) return "";
  return `<section class="ux3-section ux3-understanding"><div class="ux3-section-heading"><h3>当前理解</h3></div>${remaining.map((item) => compactKnowledge(item, rawItems)).join("")}</section>`;
}

function recentChangesHTML(knowledge: Obj[], rawItems: Obj[], omitKnowledgeId = "") {
  const changes = [
    ...(rawItems || []).map((item: Obj) => ({ kind: "material", at: item.created_at, item })),
    ...(knowledge || []).filter((item: Obj) => item.id !== omitKnowledgeId).map((item: Obj) => ({ kind: "wiki", at: item.updated_at || item.created_at, item })),
  ].sort((a, b) => String(b.at || "").localeCompare(String(a.at || ""))).slice(0, 3);
  const rows = changes.map(({ kind, at, item }) => kind === "material"
    ? `<div class="ux3-recent-row"><span>${rawButton(item, item.title || "未命名资料")}</span><small>新资料 · ${dateLabel(at)}</small></div>`
    : `<div class="ux3-recent-row"><span><button class="ux3-source-link" data-d1-wiki-history="${e(item.id)}">${e(item.content)} →</button></span><small>Wiki 更新 · ${dateLabel(at)}</small></div>`,
  ).join("");
  return `<section class="ux3-section ux3-recent"><div class="ux3-section-heading"><h3>最近变化</h3></div>${rows || `<p class="ux3-empty">还没有近期变化</p>`}</section>`;
}

function focusHTML(item: Obj | undefined, heading = "当前重点", emptyMessage = "还没有当前重点") {
  return `<section class="ux3-current-focus"><div class="ux3-section-heading"><h3>${e(heading)}</h3></div>${item
    ? `<p class="ux3-focus-body">${e(item.content)}</p>`
    : `<p class="ux3-empty">${e(emptyMessage)}</p>`}</section>`;
}

export function legacyHistoryDisclosureHTML(count: number, body: string) {
  if (count <= 0) return "";
  return `<details class="ux3-more project-compatibility"><summary>历史工作记录 · ${count} 条 →</summary>${body}</details>`;
}

function objectMeta(status: string, tags: string[], statusNote = "") {
  return `<div class="ux3-object-meta"><span class="ux3-status">${e(status)}</span>${tags.map((tag) => `<span class="ux3-tag">${e(tag.startsWith("#") ? tag : "#" + tag)}</span>`).join("")}${statusNote ? `<span class="ux3-status-note">${e(statusNote)}</span>` : ""}</div>`;
}

export function projectWorkspaceHTML(input: {
  project: Obj; employment?: Obj | null; people: PersonRow[]; participants: ParticipantRow[];
  knowledge: Obj[]; retired?: Obj[]; raw: Obj[]; legacyHTML?: string;
}) {
  const { project, employment, people, participants, raw } = input;
  const current = currentKnowledge(input.knowledge);
  const focus = latestCurrentKnowledge(input.knowledge);
  const collaboration = participantsForProject(project as ProjectRow, people, participants);
  const peopleHTML = collaboration.length
    ? collaboration.map(({ person, role }) => `<div class="ux3-person-row"><button class="ux3-person-link" data-open-person="${e(person.id)}">${e(person.name)}</button><span class="ux3-role-primary">项目角色：${e(role || "未填写")}</span>${person.role ? `<small>任职角色：${e(person.role)}</small>` : ""}</div>`).join("")
    : `<p class="ux3-empty">还没有协作人物</p>`;
  const employmentHTML = employment
    ? `<button class="ux3-relation-link" data-open-employment="${e(employment.legacy_episode_id)}">${e(employment.company)} · ${e(employment.role)} →</button>`
    : "";
  const retired = (input.retired || []).length
    ? `<details class="ux3-more ux3-subordinate"><summary>不再有效的信息 · ${(input.retired || []).length}</summary>${(input.retired || []).map((item) => compactKnowledge(item, raw)).join("")}</details>`
    : "";
  const legacy = input.legacyHTML || "";
  const more = `${legacy}${retired}`;
  const wikiBrowse = `<button class="ux3-history-link" data-d3-open-wiki-scope-type="project" data-d3-open-wiki-scope-id="${e(project.id)}">查看 Wiki →</button>`;
  return `<div class="ux3-workspace-surface ux3-project-page" data-ux3-project="${e(project.id)}"><header class="ux3-object-heading"><div><small>项目</small><h2>${e(project.name)}</h2>${project.description ? `<p>${e(project.description)}</p>` : ""}</div><div class="ux3-heading-actions"><button class="secondary" data-edit-project="${e(project.id)}">编辑项目</button></div></header>${objectMeta(projectStatuses[project.status] || "进行中", project.tags || [], project.status_note)}${employmentHTML ? `<div class="ux3-object-relation">关联任职 · ${employmentHTML}</div>` : ""}<div class="ux3-focus-wrap">${focusHTML(focus, "最近更新", "暂无 Wiki 更新")}${wikiBrowse}</div>${recentChangesHTML(input.knowledge, raw, focus?.id || "")} ${understandingHTML(input.knowledge, raw, focus?.id || "")} ${materialsHTML("project", project.id, raw)}${employment ? `<section class="ux3-section ux3-collaboration"><div class="ux3-section-heading"><h3>协作人物</h3><button class="secondary" data-work-participant="${e(project.id)}">关联人物</button></div>${peopleHTML}</section>` : ""}${more}</div>`;
}

function relationProjectRow(project: Obj) {
  return `<button class="ux3-related-row" data-open-project="${e(project.id)}"><span><b>${e(project.name)}</b><small>${e(projectStatuses[project.status] || "进行中")}${project.tags?.length ? ` · ${project.tags.map((tag: string) => e(tag.startsWith("#") ? tag : "#" + tag)).join(" · ")}` : ""}</small></span><span aria-hidden="true">→</span></button>`;
}

function employmentDateRange(employment: Obj) {
  const start = monthLabel(employment.start_date) || "开始时间未填写";
  const end = employment.end_date ? monthLabel(employment.end_date) : "至今";
  return `${start} – ${end}${employment.end_date ? " · 已结束" : " · 在职"}`;
}

export function employmentWorkspaceHTML(input: {
  employment: Obj; projects: Obj[]; people: PersonRow[]; knowledge: Obj[]; raw: Obj[];
  notesHTML?: string; actionsHTML?: string;
}) {
  const { employment, projects, people, knowledge, raw } = input;
  const focus = String(employment.focus || "").trim();
  const peopleHTML = people.filter((person) => person.identity_status === "confirmed").map((person) =>
    `<div class="ux3-employment-person"><button class="ux3-person-link" data-open-person="${e(person.id)}">${e(person.name)}</button><span>任职角色：${e(person.role || "未填写")}</span></div>`,
  ).join("");
  const projectsHTML = projects.map(relationProjectRow).join("");
  const currentView = currentKnowledge(knowledge).filter((item) => item.content !== focus);
  const notes = input.notesHTML || "";
  const more = notes || input.actionsHTML
    ? `<details class="ux3-more"><summary>更多 · 历史工作记录</summary>${input.actionsHTML || ""}${notes}</details>` : "";
  return `<div class="ux3-workspace-surface ux3-employment-page" data-ux3-employment="${e(employment.id)}"><header class="ux3-object-heading"><div><small>任职</small><h2>${e(employment.company)}</h2><p class="ux3-role-subtitle">${e(employment.role)}</p><div class="ux3-employment-dates">${e(employmentDateRange(employment))}</div></div><div class="ux3-heading-actions"><button class="quiet" data-open-wiki="episode:${e(employment.legacy_episode_id)}">在 Wiki 查看</button><button class="secondary" data-episode="${e(employment.legacy_episode_id)}">编辑任职</button></div></header>${focusHTML(focus ? { content: focus } : undefined, "当前重点", "还没有填写当前重点")}<section class="ux3-section ux3-related-projects"><div class="ux3-section-heading"><h3>关联项目</h3><div class="ux3-inline-actions"><button class="quiet" data-link-existing-project="${e(employment.id)}">关联已有项目</button><button class="secondary" data-work-project-employment="${e(employment.id)}">新建项目</button></div></div>${projectsHTML || `<p class="ux3-empty">这段任职还没有关联项目</p>`}</section><section class="ux3-section ux3-important-people"><div class="ux3-section-heading"><h3>重要人物</h3><button class="secondary" data-add-employment-person="${e(employment.id)}">添加人物</button></div>${peopleHTML || `<p class="ux3-empty">还没有需要长期维护的人</p>`}</section>${materialsHTML("employment", employment.id, raw, { title: "最近资料", limit: 3 })}${currentView.length ? `<section class="ux3-section ux3-understanding"><div class="ux3-section-heading"><h3>当前理解</h3></div>${currentView.map((item) => compactKnowledge(item, raw)).join("")}</section>` : ""}${more}</div>`;
}

export function personWorkspaceHTML(input: {
  person: PersonRow & Obj; employment: Obj; projects: Array<{ project: Obj; role: string }>;
  knowledge: Obj[]; raw: Obj[];
}) {
  const { person, employment, projects, knowledge, raw } = input;
  const current = currentKnowledge(knowledge);
  const important = current.filter((item) => item.knowledge_type === "fact");
  const observations = current.filter((item) => item.knowledge_type === "observation");
  const hypotheses = current.filter((item) => item.knowledge_type === "hypothesis");
  const sideProjects = projects.length
    ? projects.map(({ project, role }) => `<div class="ux3-person-project"><button class="ux3-project-link" data-open-project="${e(project.id)}">${e(project.name)} →</button><small>项目角色：${e(role || "未填写")}</small></div>`).join("")
    : `<p class="ux3-empty">还没有关联项目</p>`;
  const body = important.length
    ? important.map((item) => compactKnowledge(item, raw, "ux3-important-knowledge")).join("")
    : `<p class="ux3-empty">还没有重要信息</p>`;
  return `<div class="ux3-workspace-surface ux3-person-page" data-ux3-person="${e(person.id)}"><button class="ux3-back-link" data-open-employment="${e(employment.legacy_episode_id)}">← ${e(employment.company)}</button><div class="ux3-person-layout"><main class="ux3-person-main"><header class="ux3-object-heading"><div><small>人物</small><h2>${e(person.name)}</h2><p class="ux3-role-subtitle">任职角色：${e(person.role || "未填写")}</p></div><button class="secondary" data-edit-employment-person="${e(person.id)}" data-employment-id="${e(employment.id)}" data-person-revision="${e(person.revision)}">编辑人物</button></header><section class="ux3-section ux3-important-info"><div class="ux3-section-heading"><h3>重要信息</h3></div>${body}</section>${observations.length ? `<section class="ux3-section ux3-person-observations"><div class="ux3-section-heading"><h3>观察</h3></div>${observations.map((item) => compactKnowledge(item, raw, "", { hideTypeLabel: true })).join("")}</section>` : ""}${hypotheses.length ? `<section class="ux3-section ux3-person-hypotheses"><div class="ux3-section-heading"><h3>待验证判断</h3></div>${hypotheses.map((item) => compactKnowledge(item, raw, "", { hideTypeLabel: true })).join("")}</section>` : ""}${materialsHTML("person", person.id, raw, { directScopeOnly: true })}</main><aside class="ux3-person-context"><div class="ux3-person-context-section"><h3>所属任职</h3><button class="ux3-relation-link" data-open-employment="${e(employment.legacy_episode_id)}">${e(employment.company)} · ${e(employment.role)} →</button></div><div class="ux3-person-context-section"><h3>关联项目</h3>${sideProjects}</div></aside></div></div>`;
}
