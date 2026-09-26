import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { projectWikiHTML, semanticWikiUI, sourceLabel, wikiSemanticView } from "../src/wiki-semantic-ui.ts";

const bindings = readFileSync(new URL("../src/wiki-semantic-bindings.ts", import.meta.url), "utf8");
const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
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
const wikiHtml = wikiSemanticView(data);
assert.match(wikiHtml, /Fact · 已确认事实/);
assert.match(wikiHtml, /周五提交方案。/);
assert.match(wikiHtml, /#D1/);
assert.match(wikiHtml, /data-d1-open-raw-kind="raw_material"/);
assert.match(wikiHtml, /data-d1-open-raw-id="raw-fixture"/);
assert.match(wikiHtml, /data-d1-open-raw-revision="1"/);
assert.match(wikiHtml, new RegExp(`data-d1-open-raw-hash="${raw.hash}"`));
assert.match(wikiHtml, /添加原始资料/);
assert.match(wikiHtml, /写入 Wiki/);

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
assert.doesNotMatch(projectHtml, /<details class="wiki-retired" open/);
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
assert.doesNotMatch(bindings + main, /location\.reload\s*\(/,
  "不能通过刷新整个浏览器页面更新 Wiki 状态");

console.log("wiki-semantic: ok");
