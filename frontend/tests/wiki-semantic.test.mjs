import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { knowledgeTypeLabel, projectWikiHTML, semanticWikiUI, sourceLabel, wikiCompilerAction, wikiCompilerFrozenBefore, wikiCompilerPatchHTML, wikiCompilerPreviewHTML, wikiHistoryStatusLabel, wikiSemanticView } from "../src/wiki-semantic-ui.ts";

const bindings = readFileSync(new URL("../src/wiki-semantic-bindings.ts", import.meta.url), "utf8");
const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
const ui = readFileSync(new URL("../src/wiki-semantic-ui.ts", import.meta.url), "utf8");
const raw = {
  id: "raw-fixture", kind: "raw_material", source_kind: "manual_text",
  title: "虚构会议原文", content: "周五提交方案。", revision: 1,
  hash: "a".repeat(64), scope_type: "project", scope_id: "project-fixture",
  source_ref: { kind: "raw_material", id: "raw-fixture", revision: 1, hash: "a".repeat(64) },
};
const knowledge = {
  id: "wiki-fixture", scope_type: "project", scope_id: "project-fixture",
  knowledge_type: "fact", content: "周五提交方案。", tags: ["#D1"],
  source_refs: [raw.source_ref], status: "current", revision: 1,
};
const data = {
  page: "wiki",
  state: { opportunities: [{ id: "opportunity-fixture", company: "虚构公司", title: "虚构岗位" }] },
  workDomain: {
    projects: [{ id: "project-fixture", name: "虚构项目" }],
    employments: [], persons: [],
  },
  wikiSemantic: { items: [knowledge], raw: [raw] },
};

semanticWikiUI.scope = "project:project-fixture";
semanticWikiUI.status = "current";
semanticWikiUI.selected = "wiki-fixture";
const dataBeforeRender = structuredClone(data);
const wikiHtml = wikiSemanticView(data);
assert.match(wikiHtml, /<b>已确认事实<\/b>/);
assert.match(wikiHtml, /虚构项目 · 当前/);
assert.match(wikiHtml, /周五提交方案。/);
assert.match(wikiHtml, /#D1/);
assert.match(wikiHtml, /data-d1-open-raw-kind="raw_material"/);
assert.match(wikiHtml, /data-d1-open-raw-id="raw-fixture"/);
assert.match(wikiHtml, /data-d1-open-raw-revision="1"/);
assert.match(wikiHtml, new RegExp(`data-d1-open-raw-hash="${raw.hash}"`));
assert.match(wikiHtml, /添加原始资料/);
assert.match(wikiHtml, /写入 Wiki/);
assert.equal(knowledgeTypeLabel("fact"), "已确认事实");
assert.equal(knowledgeTypeLabel("observation"), "观察");
assert.equal(knowledgeTypeLabel("hypothesis"), "待验证判断");
assert.doesNotMatch(wikiHtml, /\bFact\b|\bObservation\b|\bHypothesis\b/);
assert.match(bindings, /Object\.entries\(knowledgeTypeLabels\)/,
  "编辑表单使用同一套中文知识类型名称");
assert.match(ui, /knowledgeTypeLabel\(item\.type\)/,
  "Preview 使用和 Wiki 当前页相同的类型映射");

const currentRevisions = [
  { revision: 1, status: "current", knowledge_type: "fact", content: "旧版本" },
  { revision: 2, status: "current", knowledge_type: "fact", content: "新版本" },
];
assert.equal(wikiHistoryStatusLabel(currentRevisions[0], currentRevisions), "历史",
  "旧版本不能因为它保存时曾是 current 而继续显示当前");
assert.equal(wikiHistoryStatusLabel(currentRevisions[1], currentRevisions), "当前");
assert.equal(currentRevisions.filter((item) => wikiHistoryStatusLabel(item, currentRevisions) === "当前").length, 1,
  "同一知识的历史里最多只能有一个当前版本");
const retiredRevisions = currentRevisions.map((item) => ({ ...item, status: "retired" }));
assert.equal(wikiHistoryStatusLabel(retiredRevisions[1], retiredRevisions), "不再有效");
assert.equal(wikiHistoryStatusLabel(retiredRevisions[0], retiredRevisions), "历史");
assert.equal(knowledgeTypeLabel("fact"), "已确认事实");
assert.equal(knowledgeTypeLabel("observation"), "观察");
assert.equal(knowledgeTypeLabel("hypothesis"), "待验证判断");
const historyInputBefore = structuredClone(currentRevisions);
for (const item of currentRevisions) wikiHistoryStatusLabel(item, currentRevisions);
assert.deepEqual(currentRevisions, historyInputBefore, "历史状态展示不能修改 Wiki revision 数据");
assert.deepEqual(data, dataBeforeRender, "Wiki 当前页渲染不能修改 Wiki 对象");
assert.match(bindings, /wikiHistoryStatusLabel\(item, revisions\)/,
  "历史列表必须依据整组 revision 和最新状态标记唯一当前版本");
assert.match(bindings, /knowledgeTypeLabel\(item\.knowledge_type\)/,
  "历史、编辑表单等使用统一中文知识类型映射");
assert.doesNotMatch(ui, /\/wiki\/compiler\/execute|\/wiki\/compiler\/prepare/,
  "Wiki 展示 helper 不调用 Provider 或修改数据的接口");

const newerRaw = {
  ...raw, revision: 2, title: "当前转写新版本", hash: "b".repeat(64),
  source_ref: { ...raw.source_ref, revision: 2, hash: "b".repeat(64) },
};
const staleHtml = wikiSemanticView({ ...data, wikiSemantic: { items: [knowledge], raw: [newerRaw] } });
const sourcePanel = staleHtml.split("<section><h4>来源</h4>")[1].split("</section>")[0];
assert.match(sourcePanel, new RegExp(`data-d1-open-raw-hash="${raw.hash}"`),
  "已有 Wiki 必须保留它原来引用的 revision/hash");
assert.doesNotMatch(sourcePanel, new RegExp(newerRaw.hash),
  "不能因为来源 ID 相同就静默改指向最新 Raw 版本");

const projectHtml = projectWikiHTML(
  { id: "project-fixture", name: "虚构项目" },
  { raw: [raw], knowledge: [knowledge], retired: [{ ...knowledge, id: "old", status: "retired" }] },
);
assert.match(projectHtml, /虚构会议原文/);
assert.match(projectHtml, /Wiki 当前理解/);
assert.match(projectHtml, /data-d1-add-wiki data-d1-scope-type="project"/);
assert.match(projectHtml, /<details class="wiki-retired">/);
assert.match(projectHtml, /已确认事实 · 不再有效/);
assert.doesNotMatch(projectHtml, /\bFact\b|\bObservation\b|\bHypothesis\b/);
assert.doesNotMatch(projectHtml, /<details class="wiki-retired" open/);
assert.match(projectHtml, /data-d2-compile="raw-fixture">整理到 Wiki/);
assert.equal(wikiCompilerAction({ kind: "work_event", source_kind: "work_event", id: "legacy" }), "",
  "旧兼容来源不能直接进入 D2 Compiler");
assert.equal(sourceLabel({ kind: "interview_raw", source_kind: "simulation_interview_transcript" }), "模拟面试转写");
const simulationProjectHtml = projectWikiHTML(
  { id: "project-fixture", name: "虚构项目" },
  { raw: [{ ...raw, kind: "interview_raw", source_kind: "simulation_interview_transcript" }] },
);
assert.match(simulationProjectHtml, /模拟面试转写/);
assert.doesNotMatch(simulationProjectHtml, /真实面试转写/);

assert.match(bindings, /function rawsFor\(d: Obj\)[\s\S]*d\.page === "projects"[\s\S]*wikiSemantic\?\.raw/,
  "项目和全局 Wiki 应使用各自范围的 Raw 清单，不能串页");
assert.match(bindings, /const sourceRefKey[\s\S]*ref\.revision, ref\.hash/,
  "来源选择必须按 ID、revision、hash 精确比较");
assert.match(bindings, /原来源版本已变化/,
  "编辑引用过期来源的 Wiki 时必须明确提示，不能静默换版本");
assert.match(bindings, /await api\("\/raw", request\)[\s\S]*await load\(\)[\s\S]*render\(\)/,
  "保存 Raw 后应重新读取并局部重绘当前页面");
assert.match(bindings, /await api\(item \? [\s\S]*?await load\(\)[\s\S]*?render\(\)/,
  "创建或编辑 Wiki 后应重新读取并局部重绘当前页面");
assert.match(bindings, /async function changeStatus[\s\S]*?await api\([\s\S]*?await load\(\)[\s\S]*?render\(\)/,
  "退役或恢复后应立即更新当前列表");
assert.match(bindings, /api\("\/wiki\/compiler\/prepare"/,
  "Compiler 必须先准备预览");
assert.match(bindings, /api\("\/wiki\/compiler\/execute"[\s\S]*confirm_outbound: true/,
  "Compiler 必须通过单独确认执行");
assert.match(bindings, /function renderCompilerPatch[\s\S]*patches\.findIndex\([\s\S]*status === "pending"/,
  "用户界面一次只展示一条待审 Patch");
assert.match(bindings, /async function renderCompilerPatch[\s\S]*wikiCompilerPatchHTML\(/,
  "审批页面应使用统一、可测试的用户语言 Patch 视图");
assert.match(ui, /function wikiCompilerFrozenBefore[\s\S]*revisions[\s\S]*item\.revision === patch\.before_revision/,
  "rewrite / retire 的原文必须按 Proposal 冻结 revision 从历史读取");
assert.match(ui, /wikiCompilerFrozenBefore[\s\S]*if \(!frozen \|\| typeof frozen\.content !== "string"\)[\s\S]*throw new Error/,
  "找不到冻结 revision 时必须停止，不能用当前 Wiki 冒充原文");
assert.match(bindings, /api\(`\/wiki\/\$\{encodeURIComponent\(patch\.target_knowledge_id\)\}\/history`\)[\s\S]*wikiCompilerFrozenBefore\(patch, history\.revisions \|\| \[\]\)/,
  "只读目标知识的修订历史，并按冻结 revision 取得 before");
assert.doesNotMatch(bindings, /data-d2-edit(?:[\s\]"=])/,
  "Proposal 正常状态不应有独立编辑动作");
assert.match(ui, /data-d2-edit-accept[\s\S]*编辑后接受/,
  "Proposal 仅通过编辑后接受进入编辑状态");
assert.match(ui, /data-d2-confirm-edit[\s\S]*确认修改并接受/,
  "编辑状态必须要求用户明确确认修改并接受");
assert.match(bindings, /data-d2-cancel-edit[\s\S]*renderCompilerPatch\(dialog, proposal, false\)/,
  "取消编辑只回到原建议，不写 Proposal 或 Wiki");
assert.match(bindings, /data-d2-confirm-edit[\s\S]*decide\("edit_accept", value\)/,
  "只有明确确认修改并接受才提交编辑后的正文");
assert.match(bindings, /data-d2-reject[\s\S]*decide\("reject"\)/,
  "拒绝只提交 reject 决定，不直接写入 Wiki");
assert.match(bindings, /wikiCompilerPatchHTML\(patch, beforeContent, scope, editing\)/,
  "审批页应把冻结原文和 proposed content 交给纯展示函数");
assert.doesNotMatch(bindings.split("async function renderCompilerPatch")[1].split("async function startCompiler")[0],
  /wiki\/compiler\/(?:execute|prepare)/,
  "查看、进入编辑与取消编辑不可以触发 Provider workflow");
const patchRefs = [{ kind: "raw_material", id: "raw-this-run", revision: 1, hash: "c".repeat(64) }];
const frozenRewrite = {
  id: "patch-private-id", operation: "rewrite", target_knowledge_id: "wiki-private-id",
  before_revision: 1, knowledge_type: "fact", content: "红色原型改为下周一提交。",
  reason: "新资料更新了提交安排。", scope_type: "project", scope_id: "project-private-id",
  source_refs: patchRefs,
};
const historyWithLaterRevision = [
  { revision: 1, content: "蓝色原型计划周五提交。" },
  { revision: 2, content: "不应冒充 before 的更新后内容。" },
];
const frozenBefore = wikiCompilerFrozenBefore(frozenRewrite, historyWithLaterRevision);
assert.equal(frozenBefore, "蓝色原型计划周五提交。",
  "rewrite before 必须取 Proposal 冻结的目标修订，不取后来的 current");
assert.throws(() => wikiCompilerFrozenBefore(frozenRewrite, [historyWithLaterRevision[1]]), /找不到建议对应的 Wiki 原始版本/,
  "冻结 revision 缺失时必须 fail closed");
const rewriteHTML = wikiCompilerPatchHTML(frozenRewrite, frozenBefore, "项目 · D2 虚构项目");
assert.match(rewriteHTML, /修改已有信息/);
assert.match(rewriteHTML, /原来<\/h4><pre class="preserve">蓝色原型计划周五提交。/);
assert.match(rewriteHTML, /建议改为<\/h4><pre class="preserve">红色原型改为下周一提交。/);
assert.match(rewriteHTML, /原因：/);
assert.match(rewriteHTML, /查看本轮原文/);
assert.match(rewriteHTML, /项目 · D2 虚构项目/);
assert.doesNotMatch(rewriteHTML, /rewrite|patch-private-id|wiki-private-id|project-private-id/,
  "正常 UI 不暴露英文操作枚举或内部对象 ID");
assert.equal((rewriteHTML.match(/data-d2-(?:accept|edit-accept|reject)(?:\s|>)/g) || []).length, 3,
  "正常建议恰好显示接受、编辑后接受、拒绝三个动作");
assert.doesNotMatch(rewriteHTML, /data-d2-edit(?:[\s\]"=])/,
  "正常建议不显示独立编辑按钮");

const addHTML = wikiCompilerPatchHTML({
  ...frozenRewrite, operation: "add", content: "内部评审应先于外部演示。",
}, undefined, "项目 · D2 虚构项目");
assert.match(addHTML, /新增信息/);
assert.match(addHTML, /建议新增<\/h4><pre class="preserve">内部评审应先于外部演示。/);
assert.doesNotMatch(addHTML, /原来|当前信息|蓝色原型计划/,
  "新增建议不显示空的原文区");

const retireHTML = wikiCompilerPatchHTML({
  ...frozenRewrite, operation: "retire", content: "", reason: "新资料证明这条安排已经失效。",
}, frozenBefore, "项目 · D2 虚构项目");
assert.match(retireHTML, /建议将这条信息标记为不再有效/);
assert.match(retireHTML, /当前信息<\/h4><pre class="preserve">蓝色原型计划周五提交。/);
assert.doesNotMatch(retireHTML, /删除/,
  "retire 只能说明退出当前，不说删除");

const editHTML = wikiCompilerPatchHTML(frozenRewrite, frozenBefore, "项目 · D2 虚构项目", true);
assert.match(editHTML, /原来<\/h4><pre class="preserve">蓝色原型计划周五提交。/,
  "编辑过程中仍可看到冻结的原文");
assert.match(editHTML, /建议改为<textarea data-d2-edit-value/,
  "编辑框仍明确标出正在修改的建议内容");
assert.match(editHTML, /data-d2-edit-value/);
assert.match(editHTML, /data-d2-confirm-edit>确认修改并接受/);
assert.match(editHTML, /data-d2-cancel-edit>取消编辑/);
assert.doesNotMatch(editHTML, /data-d2-accept(?:\s|>)/,
  "编辑状态必须通过明确确认修改并接受，不能误点普通接受");
assert.match(bindings, /editAcceptButton\.onclick = \(\) => void renderCompilerPatch\(dialog, proposal, true\)/,
  "编辑后接受进入本地编辑状态，没有先写 Proposal");
assert.match(bindings, /cancelEditButton\.onclick = \(\) => void renderCompilerPatch\(dialog, proposal, false\)/,
  "取消编辑回到原建议，且处理器不发请求");
assert.match(bindings, /confirmEditButton\.onclick = \(\) => \{[\s\S]*decide\("edit_accept", value\)/,
  "只有确认修改并接受才提交编辑后的内容");
assert.match(bindings, /const acceptButton = flow\.querySelector<HTMLButtonElement>\("\[data-d2-accept\]"\);\s*if \(acceptButton\) acceptButton\.onclick/,
  "编辑状态隐藏普通接受按钮时，其它编辑操作仍要继续绑定");
assert.match(bindings, /data-d2-reject[\s\S]*decide\("reject"\)/,
  "拒绝通过拒绝决定处理，不应用 Patch");
assert.match(bindings, /function finishCompilerReview[\s\S]*dialog\.close\(\)[\s\S]*render\(\)/,
  "审批完成后应关闭弹窗并重绘当前页面");
assert.match(bindings, /这组 Wiki 建议已经逐条处理完。[\s\S]*data-d2-finish[\s\S]*finishCompilerReview\(dialog\)/,
  "逐条审批结束并关闭弹窗后，应重绘已刷新的当前 Wiki 页面");
assert.match(ui, /function wikiCompilerPatchHTML[\s\S]*?编辑退役原因/);
assert.match(bindings, /if \(decision === "edit_accept"\) body\[patch\.operation === "retire" \? "reason" : "content"\]/,
  "退役 Patch 编辑的是审批原因，不会伪装成 Wiki 正文编辑");
assert.doesNotMatch(bindings + main, /location\.reload\s*\(/,
  "不能通过刷新整个浏览器页面更新 Wiki 状态");

const previewContext = {
  raw: { content: "D2 虚构新资料：原型改到下周一。", created_at: "2026-09-26T10:15:00+08:00" },
  scopes: [{ type: "project", minimal_identity: { name: "D2-WIKI-COMPILER-SMOKE-fake" } }],
  current_knowledge: [{
    type: "fact", content: "原型原计划周五提交。", tags: ["D2-smoke"],
    scope_type: "project", scope_identity: { name: "D2-WIKI-COMPILER-SMOKE-fake" },
  }, {
    type: "observation", content: "评审通常先看交互稿。", tags: ["评审"],
    scope_type: "project", scope_identity: { name: "D2-WIKI-COMPILER-SMOKE-fake" },
  }, {
    type: "hypothesis", content: "提前内部评审可能减少返工。", tags: [],
    scope_type: "project", scope_identity: { name: "D2-WIKI-COMPILER-SMOKE-fake" },
  }],
};
const previewDetails = {
  model: "DeepSeek", raw_count: 1, wiki_count: 3,
  scopes: ["项目 · D2-WIKI-COMPILER-SMOKE-fake"],
};
const previewContextBeforeRender = structuredClone(previewContext);
const previewHTML = wikiCompilerPreviewHTML(previewContext, previewDetails);
assert.deepEqual(previewContext, previewContextBeforeRender,
  "Preview 只读取安全 Context DTO，不修改发送内容或其冻结输入");
assert.match(previewHTML, /AI 会比较“新资料”和“Wiki 里已有的信息”，判断 Wiki 是否需要更新。/);
assert.match(previewHTML, /<h4>新资料<\/h4>/);
assert.match(previewHTML, /D2 虚构新资料：原型改到下周一。/);
assert.match(previewHTML, /资料记录时间：/);
assert.match(previewHTML, /<h4>所属项目 \/ 任职 \/ 人物<\/h4>/);
assert.match(previewHTML, /项目 · D2-WIKI-COMPILER-SMOKE-fake/);
assert.match(previewHTML, /<h4>Wiki 里已有的信息<\/h4>/);
assert.match(previewHTML, /已确认事实<\/small><pre class="d2-preview-content">原型原计划周五提交。/);
assert.match(previewHTML, /观察<\/small><pre class="d2-preview-content">评审通常先看交互稿。/);
assert.match(previewHTML, /待验证判断<\/small><pre class="d2-preview-content">提前内部评审可能减少返工。/);
assert.match(previewHTML, /标签：D2-smoke/);
assert.match(previewHTML, /标签：评审/);
assert.match(previewHTML, /有没有值得新增的信息/);
assert.match(previewHTML, /已有信息是否需要修改/);
assert.match(previewHTML, /有没有已经失效的信息/);
assert.match(previewHTML, /仅限上面这些内容，不会读取其他 Career 资料。/);
assert.match(previewHTML, /<details class="d2-preview-details"><summary>查看发送详情<\/summary>/);
assert.match(previewHTML, /模型：DeepSeek/);
assert.match(previewHTML, /当前知识：3/);
assert.match(previewHTML, /让 AI 整理/);
assert.match(previewHTML, /取消/);
assert.ok(previewHTML.indexOf("<h4>新资料</h4>") < previewHTML.indexOf("<h4>所属项目 / 任职 / 人物</h4>"));
assert.ok(previewHTML.indexOf("<h4>所属项目 / 任职 / 人物</h4>") < previewHTML.indexOf("<h4>Wiki 里已有的信息</h4>"));
assert.ok(previewHTML.indexOf("<h4>Wiki 里已有的信息</h4>") < previewHTML.indexOf("<h4>AI 会判断</h4>"));
const visiblePreviewText = previewHTML.split("<details")[0].replace(/<[^>]*>/g, " ");
assert.equal(visiblePreviewText.split("D2-WIKI-COMPILER-SMOKE-fake").length - 1, 1,
  "Project 名称只在所属范围展示一次，不在每条 Wiki 重复");
assert.doesNotMatch(visiblePreviewText, /Provider Preview|确认发送给 Provider|\bRaw\b|scope|wiki_count|\bFact\b|\bObservation\b|\bHypothesis\b|SECRET/i);
assert.doesNotMatch(previewHTML, /fake-project-id|other-career|resume-fixture/);
assert.match(bindings, /flow\.innerHTML = wikiCompilerPreviewHTML\(preview\.readable_context, preview\.preview_details\)/,
  "展示内容必须直接从实际预览使用的安全 Context DTO 投影");
assert.match(bindings, /data-d2-cancel[\s\S]*?onclick = \(\) => dialog\.close\(\)/,
  "取消只关闭预览，不会调用 execute");
assert.match(bindings, /data-d2-confirm[\s\S]*?api\("\/wiki\/compiler\/execute"[\s\S]*confirm_outbound: true/,
  "让 AI 整理仍调用原有的单独 confirm 接口");
const staleRenderer = bindings.split("function renderCompilerStale")[1].split("function renderCompilerPreview")[0];
assert.match(staleRenderer, /资料在预览后发生了变化，请重新确认发送内容。/);
assert.match(staleRenderer, /data-d2-repreview>重新预览/);
assert.doesNotMatch(staleRenderer, /prepared_request_stale|modalError/,
  "stale 技术码不能泄漏到普通界面");
assert.match(staleRenderer, /data-d2-repreview[\s\S]*?onclick = \(\) => \{[\s\S]*?startCompiler\(rawId, true\)/,
  "只有用户点击重新预览后才会创建新的 prepare");
assert.match(bindings, /if \(isPreparedRequestStale\(error\)\) \{[\s\S]*?renderCompilerStale\(dialog, rawId\);\s*return;\s*\}[\s\S]*?modalError\(error\)/,
  "stale 失败展示人话并终止当前确认处理，不自动重试或 prepare");
assert.match(bindings, /async function startCompiler\(rawId: string, freshPreview = false\)[\s\S]*?if \(!freshPreview\)[\s\S]*?const preview = await api\("\/wiki\/compiler\/prepare"/,
  "重新预览必须显式跳过旧 proposal 检查并获得新的 preview");
assert.match(readFileSync(new URL("../src/style.css", import.meta.url), "utf8"),
  /\.d2-preview-content\s*\{[^}]*max-height:[^}]*overflow:\s*auto/s,
  "长正文需在有界区域内滚动，不能截断正文或拉长弹窗");
const longBody = "虚构长资料。".repeat(12000);
assert.ok(wikiCompilerPreviewHTML({
  ...previewContext, raw: { content: longBody },
}, previewDetails).includes(longBody), "长 Raw 必须能查看实际发送全文");
assert.doesNotMatch(previewHTML, /sk-[A-Za-z0-9]{8,}|api[_-]?key/i,
  "Preview 不得展示 Secret");

console.log("wiki-semantic: ok");
