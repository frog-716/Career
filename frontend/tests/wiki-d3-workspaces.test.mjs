import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  projectWikiHTML,
  scopeRawHTML,
  sortCurrentWikiKnowledge,
  wikiCompilerAction,
  wikiCurrentUnderstandingHTML,
} from "../src/wiki-semantic-ui.ts";

const project = { id: "project-a", name: "虚构项目 A" };
const employment = { id: "employment-a" };
const person = { id: "person-p" };
const raw = {
  id: "raw-a", kind: "raw_material", revision: 1, hash: "a".repeat(64),
  title: "虚构会议记录", source_kind: "manual_text", created_at: "2026-09-26T08:00:00Z",
  scope_type: "project", scope_id: project.id,
  source_ref: { kind: "raw_material", id: "raw-a", revision: 1, hash: "a".repeat(64) },
};
const fact = {
  id: "wiki-fact", scope_type: "project", scope_id: project.id,
  knowledge_type: "fact", status: "current", revision: 2,
  updated_at: "2026-09-25T10:00:00Z", content: "项目的虚构已确认事实。", tags: ["#D3"],
  source_refs: [raw.source_ref],
};
const observation = {
  id: "wiki-observation", scope_type: "project", scope_id: project.id,
  knowledge_type: "observation", status: "current", revision: 1,
  updated_at: "2026-09-26T10:00:00Z", content: "项目的虚构观察。", tags: [],
  source_refs: [raw.source_ref],
};
const hypothesis = {
  id: "wiki-hypothesis", scope_type: "project", scope_id: project.id,
  knowledge_type: "hypothesis", status: "current", revision: 1,
  updated_at: "2026-09-27T10:00:00Z", content: "项目的虚构待验证判断。", tags: [],
  source_refs: [raw.source_ref],
};

const projectHTML = projectWikiHTML(project, {
  knowledge: [hypothesis, fact, observation], retired: [], raw: [raw],
});
assert.match(projectHTML, /<h2>资料<\/h2>/, "Project 应有轻量资料区域");
assert.match(projectHTML, /<h2>当前理解<\/h2>/, "Project 应显示 Wiki 当前态投影");
assert.match(projectHTML, /整理到 Wiki/, "Project Raw 应能共用 D2 Compiler 入口");
assert.match(projectHTML, /data-d1-open-raw-kind/, "Project Raw 应能打开原文");
assert.ok(projectHTML.indexOf("<h2>当前理解</h2>") < projectHTML.indexOf("<h2>资料</h2>"),
  "Project 页面应先显示当前理解，再显示原始资料");
const visibleProjectText = projectHTML.replace(/<[^>]*>/g, " ");
assert.ok(!visibleProjectText.includes("wiki-fact"), "知识 ID 不应出现在可见正文");
assert.ok(!visibleProjectText.includes("a".repeat(64)), "Raw hash 不应显示");

const currentHTML = wikiCurrentUnderstandingHTML("person", person.id, [
  { ...hypothesis, scope_type: "person", scope_id: person.id },
  { ...fact, scope_type: "person", scope_id: person.id },
  { ...observation, scope_type: "person", scope_id: person.id },
], [raw]);
assert.match(currentHTML, /当前理解/);
assert.ok(currentHTML.indexOf("已确认事实") < currentHTML.indexOf("观察"));
assert.ok(currentHTML.indexOf("观察") < currentHTML.indexOf("待验证判断"));
assert.match(currentHTML, /虚构会议记录/);
assert.match(currentHTML, /在 Wiki 查看历史/);
const sortedKnowledge = sortCurrentWikiKnowledge([
  { ...fact, id: "fact-old", updated_at: "2026-09-20T10:00:00Z", content: "较早事实。" },
  { ...fact, id: "fact-new", updated_at: "2026-09-26T10:00:00Z", content: "较新事实。" },
  { ...fact, id: "fact-retired", status: "retired", updated_at: "2026-09-27T10:00:00Z", content: "退役事实。" },
]);
assert.deepEqual(sortedKnowledge.map((item) => item.content), ["较新事实。", "较早事实。"],
  "同类当前知识按最近更新时间倒序，retired 默认隐藏");

const employmentHTML = wikiCurrentUnderstandingHTML("employment", employment.id, [
  { ...fact, scope_type: "employment", scope_id: employment.id },
], []);
assert.match(employmentHTML, /已确认事实/);
assert.ok(!employmentHTML.includes("项目的虚构观察"), "Employment 只显示输入给它的当前知识");

const rawsHTML = scopeRawHTML("person", person.id, [raw]);
assert.match(rawsHTML, /资料/);
assert.match(rawsHTML, /虚构会议记录/);
assert.match(rawsHTML, /2026|09\/26|9\/26/, "Raw 时间应显示在资料列表");
const pendingRawHTML = scopeRawHTML("project", project.id, [{ ...raw, pending_patch_count: 1 }]);
assert.match(pendingRawHTML, /1 条建议待处理/,
  "返回项目后应看见已有待处理建议");
assert.match(pendingRawHTML, /继续处理建议/,
  "待处理建议应有明确的恢复入口");
assert.doesNotMatch(rawsHTML, /继续处理建议/,
  "没有建议时仍显示整理入口");

const targetAction = wikiCompilerAction(raw, { scope_type: "person", scope_id: person.id });
assert.match(targetAction, /data-d2-target-scope-type="person"/);
assert.match(targetAction, /data-d2-target-scope-id="person-p"/);
assert.doesNotMatch(wikiCompilerAction(raw), /data-d2-target-scope-/,
  "普通 Wiki 入口应保留 D2 多范围合同；业务对象页才传入明确目标范围");

const employmentView = readFileSync(new URL("../src/workspace.ts", import.meta.url), "utf8");
const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
const bindings = readFileSync(new URL("../src/wiki-semantic-bindings.ts", import.meta.url), "utf8");
assert.match(employmentView, /employmentWiki/);
assert.match(employmentView, /personWiki/);
assert.match(main, /scope_type=employment/);
assert.match(main, /scope_type=person/);
assert.match(bindings, /target_scope/);
assert.match(bindings, /await load\(\)/, "审批后必须重新读取业务页面的数据");
assert.doesNotMatch(bindings + employmentView + main, /location\.reload\s*\(/);
assert.equal((bindings.match(/\/wiki\/compiler\/prepare/g) || []).length, 1,
  "Project、Employment、Person 应复用唯一的 Compiler prepare 入口");
const workBranch = employmentView.slice(employmentView.indexOf('if (page === "work")'), employmentView.indexOf('if (page === "resume")'));
assert.match(workBranch, /wikiCurrentUnderstandingHTML\("employment", employmentId/);
assert.match(workBranch, /wikiCurrentUnderstandingHTML\("person", selectedPerson\.id/);
assert.match(workBranch, /scopeRawHTML\("employment", employmentId/);
assert.match(workBranch, /scopeRawHTML\("person", selectedPerson\.id/);
assert.ok(workBranch.indexOf("${employmentWikiView}") < workBranch.indexOf("${employmentRawView}"),
  "Employment 页面应先显示当前理解，再显示任职资料");
assert.match(main, /ui\.personId = person\.id[\s\S]*?void load\(\)\.then\(render\)/,
  "打开 Person 详情时应读取该人物自己的 Wiki 并保留当前路由");
assert.match(main, /ui\.personId = ""[\s\S]*?personWiki = \{ knowledge: \[\], retired: \[\], raw: \[\] \}/,
  "收起 Person 详情后应清除选中人物的数据");

console.log("wiki-d3-workspaces: ok");
