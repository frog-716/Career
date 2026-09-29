import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { cognitionExperiencePickerHTML, cognitionOutputErrorHTML, cognitionPreviewHTML, cognitionWikiHTML, knowledgeTypeLabel, projectWikiHTML, semanticWikiUI, sourceLabel, wikiCompilerAction, wikiCompilerFrozenBefore, wikiCompilerPatchHTML, wikiCompilerPreviewHTML, wikiHistoryStatusLabel, wikiSemanticView } from "../src/wiki-semantic-ui.ts";

const bindings = readFileSync(new URL("../src/wiki-semantic-bindings.ts", import.meta.url), "utf8");
const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
const workspace = readFileSync(new URL("../src/workspace.ts", import.meta.url), "utf8");
const ux3Workspace = readFileSync(new URL("../src/ux3-workspaces.ts", import.meta.url), "utf8");
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
assert.match(wikiHtml, /已确认事实/);
assert.match(wikiHtml, /项目 · 虚构项目/);
assert.match(wikiHtml, /周五提交方案。/);
assert.match(wikiHtml, /#D1/);
assert.match(wikiHtml, /data-d1-open-raw-kind="raw_material"/);
assert.match(wikiHtml, /data-d1-open-raw-id="raw-fixture"/);
assert.match(wikiHtml, /data-d1-open-raw-revision="1"/);
assert.match(wikiHtml, new RegExp(`data-d1-open-raw-hash="${raw.hash}"`));
assert.ok(wikiHtml.indexOf("周五提交方案。") < wikiHtml.indexOf("虚构会议原文"), "Wiki 正文先于来源显示");
assert.ok(wikiHtml.indexOf("虚构会议原文") < wikiHtml.indexOf("已确认事实"), "Wiki 来源先于知识性质显示");
assert.doesNotMatch(wikiHtml, /添加原始资料/);
assert.match(wikiHtml, /手工记一条/);
semanticWikiUI.scope = "all";
const allWithTitles = wikiSemanticView({
  ...data,
  wikiSemantic: {
    items: [knowledge], raw: [],
    sourceCatalog: [{ ...raw.source_ref, title: "虚构会议原文", source_kind: "manual_text", source_ref: raw.source_ref }],
  },
});
assert.match(allWithTitles, /虚构会议原文/,
  "全部 Wiki 范围也必须显示可区分的来源标题");
assert.doesNotMatch(allWithTitles, /手工原文（版本可能已变化）/,
  "有精确版本的来源不能误称版本可能变化");
semanticWikiUI.scope = "project:project-fixture";
assert.equal(knowledgeTypeLabel("fact"), "已确认事实");
assert.equal(knowledgeTypeLabel("observation"), "观察");
assert.equal(knowledgeTypeLabel("hypothesis"), "待验证判断");
assert.doesNotMatch(wikiHtml, /\bFact\b|\bObservation\b|\bHypothesis\b/);
assert.match(bindings, /Object\.entries\(knowledgeTypeLabels\)/,
  "编辑表单使用同一套中文知识类型名称");
assert.match(ui, /knowledgeTypeLabel\(item\.type\)/,
  "Preview 使用和 Wiki 当前页相同的类型映射");
assert.match(main, /include_source_titles/, "Wiki 当前页应请求当前可见来源的标题目录");
assert.match(main, /api\("\/wiki\/cognition\/experiences"\)/,
  "长期认知选择器必须从正式经历接口加载可选 Project / Employment");
assert.match(main, /experiences:\s*cognitionExperiencesResult\?\.experiences\s*\|\|\s*\[\]/,
  "长期认知工作区状态必须包含经历列表，而不只是 Cognition 条目");
assert.match(bindings, /保存到：/, "添加资料时必须显示目标对象的名称");
assert.match(bindings, /if \(cancelEditButton\)[\s\S]*?dialog\.dataset\.dirty = "false"/,
  "取消建议编辑后不应继续报告有未保存输入");
assert.match(bindings, /result\.status === "proposal_pending"[\s\S]*?await load\(\);\s*render\(\);/,
  "建议生成后应立即刷新底层资料行的待处理提示");

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
assert.match(ui, /wikiHistoryStatusLabel\(current, revisions\)/,
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
const sourcePanel = staleHtml.split('class="reading-section reading-sources"')[1].split("</section>")[0];
assert.match(sourcePanel, new RegExp(`data-d1-open-raw-hash="${raw.hash}"`),
  "已有 Wiki 必须保留它原来引用的 revision/hash");
assert.doesNotMatch(sourcePanel, new RegExp(newerRaw.hash),
  "不能因为来源 ID 相同就静默改指向最新 Raw 版本");

const projectHtml = projectWikiHTML(
  { id: "project-fixture", name: "虚构项目" },
  { raw: [raw], knowledge: [knowledge], retired: [{ ...knowledge, id: "old", status: "retired" }] },
);
assert.match(projectHtml, /虚构会议原文/);
assert.match(projectHtml, /<h2>当前理解<\/h2>/);
assert.match(projectHtml, /data-d1-add-wiki data-d1-scope-type="project"/);
assert.match(projectHtml, /<details class="wiki-retired">/);
assert.match(projectHtml, /已确认事实 · 不再有效/);
assert.doesNotMatch(projectHtml, /\bFact\b|\bObservation\b|\bHypothesis\b/);
assert.doesNotMatch(projectHtml, /<details class="wiki-retired" open/);
assert.match(projectHtml, /data-d2-compile="raw-fixture" data-d2-target-scope-type="project" data-d2-target-scope-id="project-fixture">整理到 Wiki/);
assert.equal(wikiCompilerAction({ kind: "work_event", source_kind: "work_event", id: "legacy" }), "",
  "旧兼容来源不能直接进入 D2 Compiler");
assert.equal(sourceLabel({ kind: "interview_raw", source_kind: "simulation_interview_transcript" }), "模拟面试转写");
assert.equal(sourceLabel({ kind: "raw_material", source_kind: "profile_archive" }), "旧基础资料原文");
const simulationProjectHtml = projectWikiHTML(
  { id: "project-fixture", name: "虚构项目" },
  { raw: [{ ...raw, kind: "interview_raw", source_kind: "simulation_interview_transcript" }] },
);
assert.match(simulationProjectHtml, /模拟面试转写/);
assert.doesNotMatch(simulationProjectHtml, /真实面试转写/);

assert.match(bindings, /function rawsFor\(d: Obj\)[\s\S]*d\.page === "projects"[\s\S]*d\.page === "work"[\s\S]*wikiSemantic\?\.raw/,
  "项目、任职人物和全局 Wiki 应使用各自范围的 Raw 清单，不能串页");
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
assert.match(bindings, /wikiCompilerPatchHTML\([\s\S]*displayPatch, beforeContent, scope, editing,[\s\S]*isCognition \? \{ cognition: true, supportingExperiences \}/,
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
assert.match(bindings, /cancelEditButton\.onclick = async \(\) => \{[\s\S]*?await renderCompilerPatch\(dialog, proposal, false\);[\s\S]*?dialog\.dataset\.dirty = "false"/,
  "取消编辑回到原建议，清除已丢弃输入的脏状态，且不发请求");
assert.match(bindings, /confirmEditButton\.onclick = \(\) => \{[\s\S]*decide\("edit_accept", value\)/,
  "只有确认修改并接受才提交编辑后的内容");
assert.match(bindings, /const acceptButton = flow\.querySelector<HTMLButtonElement>\("\[data-d2-accept\]"\);\s*if \(acceptButton\) acceptButton\.onclick/,
  "编辑状态隐藏普通接受按钮时，其它编辑操作仍要继续绑定");
assert.match(bindings, /data-d2-reject[\s\S]*decide\("reject"\)/,
  "拒绝通过拒绝决定处理，不应用 Patch");
assert.match(bindings, /function finishCompilerReview[\s\S]*dialog\.close\(\)[\s\S]*render\(\)/,
  "审批完成后应关闭弹窗并重绘当前页面");
assert.match(bindings, /这组 Wiki 建议已经逐条处理完。[\s\S]*data-d2-finish[\s\S]*finishCompilerReview\(dialog, accepted \?/,
  "逐条审批结束并关闭弹窗后，应重绘已刷新的当前 Wiki 页面");
assert.match(ui, /function wikiCompilerPatchHTML[\s\S]*?编辑退役原因/);
assert.match(bindings, /if \(decision === "edit_accept"\) body\[patch\.operation === "retire" \? "reason" : "content"\]/,
  "退役 Patch 编辑的是审批原因，不会伪装成 Wiki 正文编辑");
assert.doesNotMatch(bindings + main, /location\.reload\s*\(/,
  "不能通过刷新整个浏览器页面更新 Wiki 状态");

const cognitionExperienceA = {
  type: "project", id: "project-d4-a", name: "D4 虚构项目 A",
  current_knowledge: [{ knowledge_id: "wiki-a", type: "observation", content: "先划边界，再拆任务。", tags: ["#A"] }],
};
const cognitionExperienceB = {
  type: "employment", id: "employment:d4-b", name: "D4 虚构公司 / 产品角色",
  current_knowledge: [{ knowledge_id: "wiki-b", type: "hypothesis", content: "先确认系统边界，再分配工作。", tags: ["#B"] }],
};
const currentCognition = {
  id: "cognition-fixture", knowledge_type: "observation", status: "current",
  scope_type: "cognition", scope_id: "",
  source_refs: [{ kind: "wiki_knowledge", id: "wiki-d4-a", revision: 1, hash: "a".repeat(64) }],
  content: "不同经历中都先明确边界，再开始拆解。",
  supporting_experiences: [
    { type: "project", id: "project-d4-a", name: "D4 虚构项目 A" },
    { type: "employment", id: "employment:d4-b", name: "D4 虚构公司 / 产品角色" },
  ],
};
const cognitionPicker = cognitionExperiencePickerHTML([
  { type: "project", id: "project-d4-a", name: "D4 虚构项目 A", status: "completed", current_knowledge_count: 1 },
  { type: "employment", id: "employment:d4-b", name: "D4 虚构公司 / 产品角色", status: "ended", current_knowledge_count: 1 },
  { type: "project", id: "project-empty", name: "没有 Wiki 的项目", current_knowledge_count: 0 },
], [{ type: "project", id: "project-d4-a" }]);
assert.match(cognitionPicker, /至少两段、最多20段不同的项目或任职经历/);
assert.match(cognitionPicker, /checked/);
assert.match(cognitionPicker, /没有 Wiki 的项目/);
assert.match(cognitionPicker, /disabled/);

const cognitionPreview = cognitionPreviewHTML({
  task: "synthesize_long_term_cognition",
  selected_experiences: [cognitionExperienceA, cognitionExperienceB],
  existing_cognition: [{ id: "cognition-existing", type: "hypothesis", content: "这是虚构的已有认知。", revision: 1, supporting_experience_ids: ["project-old"] }],
}, { model: "测试模型", experiences: [cognitionExperienceA.name, cognitionExperienceB.name], wiki_count: 2 });
assert.match(cognitionPreview, /整理长期认知/);
assert.match(cognitionPreview, /AI 将比较 2 段经历/);
assert.match(cognitionPreview, /D4 虚构项目 A/);
assert.match(cognitionPreview, /D4 虚构公司 \/ 产品角色/);
assert.match(cognitionPreview, /先划边界，再拆任务/);
assert.match(cognitionPreview, /先确认系统边界，再分配工作/);
assert.match(cognitionPreview, /这是虚构的已有认知/);
assert.match(cognitionPreview, /已有长期认知（1）/);
assert.match(cognitionPreview, /<details class="d2-preview-details">/);
assert.doesNotMatch(cognitionPreview, /<details class="d2-preview-details" open/);
assert.match(cognitionPreview, /不会读取原始资料。/);
assert.match(cognitionPreview, /data-d4-confirm>让 AI 整理/);
assert.match(cognitionPreview, /data-d4-cancel>取消/);
assert.doesNotMatch(cognitionPreview, /工作方式或能力线索|AI 会判断|人格标签|Raw 原文、人物/);
assert.doesNotMatch(cognitionPreview, /source_ref:|selected_experiences|knowledge_id|revision=/,
  "Preview 不把 DTO 内部字段和标识直接展示给用户");
const emptyCognitionPreview = cognitionPreviewHTML({
  selected_experiences: [cognitionExperienceA, cognitionExperienceB], existing_cognition: [],
}, { model: "DeepSeek", experiences: [cognitionExperienceA.name, cognitionExperienceB.name], wiki_count: 2 });
assert.doesNotMatch(emptyCognitionPreview, /已有长期认知（0）|目前还没有长期认知/,
  "没有已有 Cognition 时不占据 Preview 空间");
assert.match(emptyCognitionPreview, /查看发送详情/);

// The real prepare response supplies model and names, but no summary wiki_count.
for (const details of [{ model: "DeepSeek" }, { model: "DeepSeek", wiki_count: 99 }]) {
  const preview = cognitionPreviewHTML({
    selected_experiences: [cognitionExperienceA, cognitionExperienceB], existing_cognition: [],
  }, details);
  assert.match(preview, /当前 Wiki：2 条/, "发送详情必须按实际 DTO 的当前 Wiki 计数");
}

const cognitionProposalHTML = wikiCompilerPatchHTML({
  operation: "add", knowledge_type: "observation", content: "在多个虚构项目中先明确边界再开始实现。",
  reason: "两个独立项目的当前 Wiki 都描述了这一顺序。",
  source_refs: [
    { kind: "wiki_knowledge", id: "wiki-a", revision: 1, hash: "a".repeat(64) },
    { kind: "wiki_knowledge", id: "wiki-b", revision: 1, hash: "b".repeat(64) },
  ],
}, undefined, "", false, {
  cognition: true,
  supportingExperiences: [
    { type: "project", name: "D4 虚构项目 A" },
    { type: "project", name: "D4 虚构项目 B" },
  ],
});
assert.match(cognitionProposalHTML, /观察/);
assert.match(cognitionProposalHTML, /在多个虚构项目中先明确边界再开始实现。/);
assert.match(cognitionProposalHTML, /支持经历/);
assert.match(cognitionProposalHTML, /D4 虚构项目 A/);
assert.match(cognitionProposalHTML, /D4 虚构项目 B/);
assert.match(cognitionProposalHTML, /<details><summary>为什么？<\/summary>/);
assert.doesNotMatch(cognitionProposalHTML, /wiki-a|wiki-b|source_refs|scope_type|operation/);
assert.match(ui, /AI 返回的结果无法安全使用，本次没有修改长期认知。/);
const cognitionOutputError = cognitionOutputErrorHTML();
assert.match(cognitionOutputError, /AI 返回的结果无法安全使用，本次没有修改长期认知。/);
assert.match(cognitionOutputError, /data-d4-output-invalid>关闭/);
assert.doesNotMatch(cognitionOutputError, /重试|重新发送/);
assert.match(bindings, /data-d4-output-invalid[\s\S]*关闭/);
assert.doesNotMatch(bindings.split("async function startCognitionCompiler")[1].split("on(\"[data-d4-wiki-all]")[0],
  /重试|重新发送/,
  "模型结果违反合同后只能关闭，不能出现重试入口");
const cognitionRewriteProposal = wikiCompilerPatchHTML({
  operation: "rewrite", knowledge_type: "hypothesis", content: "更谨慎的虚构判断。",
  reason: "两个来源都支持，但仍然是待验证判断。", source_refs: [],
}, "原有虚构判断。", "", false, {
  cognition: true, supportingExperiences: [{ type: "project", name: "D4 虚构项目 A" }],
});
assert.match(cognitionRewriteProposal, /待验证判断 · 修改已有信息/);
assert.match(cognitionRewriteProposal, /原有虚构判断。/);
assert.match(cognitionRewriteProposal, /更谨慎的虚构判断。/);
assert.match(cognitionRewriteProposal, /为什么？/);
assert.doesNotMatch(cognitionRewriteProposal, /reason：|wiki.*id/);
const cognitionRetireProposal = wikiCompilerPatchHTML({
  operation: "retire", knowledge_type: "fact", reason: "不再适用。", source_refs: [],
}, "旧的虚构事实。", "", false, {
  cognition: true, supportingExperiences: [{ type: "employment", name: "D4 虚构任职" }],
});
assert.match(cognitionRetireProposal, /已确认事实 · 标记为不再有效/);
assert.match(cognitionRetireProposal, /旧的虚构事实。/);

const cognitionView = cognitionWikiHTML({
  knowledge: [currentCognition], retired: [], proposals: [],
}, "current", currentCognition.id);
assert.match(cognitionView, /class="reading-owner">长期认知<\/p>/);
assert.match(cognitionView, /不同经历中都先明确边界/);
assert.match(cognitionView, /支持这个判断的经历/);
assert.match(cognitionView, /D4 虚构项目 A/);
assert.match(cognitionView, /data-d4-open-experience-type="project"/);
assert.match(cognitionView, /data-d4-open-source-tree=/);
assert.doesNotMatch(cognitionView, /data-d4-start/, "详情以阅读为主，整理入口在长期认知列表");
assert.doesNotMatch(cognitionView, /原文正文|D4 RAW MUST NOT BE SENT/,
  "默认页面只显示来源经历，不铺开 Raw 原文");
assert.match(ui, /data-d4-resume-proposal/);
assert.match(bindings, /api\("\/wiki\/cognition\/compiler\/prepare"/);
assert.match(bindings, /api\("\/wiki\/cognition\/compiler\/execute"[\s\S]*confirm_outbound: true/);
assert.match(bindings, /api\(`\/wiki\/cognition\/knowledge\/\$\{encodeURIComponent\(identifier\)\}\/sources`\)/);
assert.match(bindings, /data-d4-open-wiki-source[\s\S]*openWikiSource/);
assert.equal((bindings.match(/on\("\[data-d4-open-source-tree\]"/g) || []).length, 1,
  "长期认知来源按钮只绑定一次，避免打开来源时重复发请求");
const cognitionSourceTree = bindings.split("async function openCognitionSourceTree")[1].split('on("[data-d4-open-source-tree]"')[0];
assert.match(cognitionSourceTree, /<details class="d4-raw-sources"><summary>需要时查看原始资料/,
  "来源先显示经历和其 Wiki，原始资料入口默认折叠");
assert.doesNotMatch(cognitionSourceTree, /raw\.title|raw\.content|api\([^)]*\/raw\//,
  "打开来源目录不会读取或展示 Raw，只有用户点击原始资料按钮后才读取");
assert.match(bindings, /startCognitionCompiler\(selected\)/,
  "用户明确选择经历后才会准备长期认知 Preview");
assert.match(bindings, /selected\.length > 20[\s\S]*最多选择20段不同的经历/,
  "经历选择超过后端支持上限时会在本地给出明确反馈");
assert.doesNotMatch(ui, /data-d4-start/,
  "REMOVE 后不再从 Wiki 触发新的 D4 自动整理");
assert.doesNotMatch(workspace, /data-d4-start/,
  "任职页不再触发新的 D4 自动整理");
assert.doesNotMatch(ux3Workspace, /data-d4-start/,
  "项目页不再触发新的 D4 自动整理");
assert.match(ux3Workspace, /<details class="ux3-more"[\s\S]*input\.actionsHTML/,
  "任职复盘入口保留在默认折叠的次级区域");
const cognitionStartFlow = bindings.split('on("[data-d4-start]"')[1].split("function sourceChoices")[0];
assert.match(cognitionStartFlow, /data-d4-prepare[\s\S]*?void startCognitionCompiler\(selected\)/,
  "用户明确选择经历后才准备 Preview");
assert.doesNotMatch(cognitionStartFlow, /\/wiki\/cognition\/compiler\/execute/,
  "打开经历选择和启动 Preview 不会执行 Provider 请求");
assert.match(bindings, /\[data-d4-confirm\][\s\S]*?onclick = async[\s\S]*?api\("\/wiki\/cognition\/compiler\/execute"/,
  "只有用户点击‘让 AI 整理’才执行 Provider 请求");
const cognitionConfirmFlow = bindings.split("async function startCognitionCompiler")[1].split('on("[data-d4-wiki-all]')[0];
assert.match(cognitionConfirmFlow, /if \(button\.disabled\) return;[\s\S]*button\.disabled = true/,
  "同一个 Preview 只允许一次确认点击");
assert.doesNotMatch(bindings + main, /location\.reload\s*\(/,
  "Cognition 页面刷新也不能整页重载");

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
assert.match(staleRenderer, /data-d2-repreview[\s\S]*?onclick = \(\) => \{[\s\S]*?startCompiler\(rawId, true, targetScope\)/,
  "只有用户点击重新预览后才会创建新的 prepare");
assert.match(bindings, /if \(isPreparedRequestStale\(error\)\) \{[\s\S]*?renderCompilerStale\(dialog, rawId, targetScope\);\s*return;\s*\}[\s\S]*?modalError\(error\)/,
  "stale 失败展示人话并终止当前确认处理，不自动重试或 prepare");
assert.match(bindings, /async function startCompiler\(rawId: string, freshPreview = false, targetScope\?: Obj\)[\s\S]*?if \(!freshPreview\)[\s\S]*?const preview = await api\("\/wiki\/compiler\/prepare"/,
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
