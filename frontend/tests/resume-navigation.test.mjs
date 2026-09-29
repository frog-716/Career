import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createServer } from "vite";
import { SIDEBAR_MODULE_IDS, normalizeSidebarOrder, resolveSidebarHome } from "../src/sidebar-model.ts";

const root = new URL("..", import.meta.url).pathname;
const vite = await createServer({
  configFile: false,
  root,
  optimizeDeps: { noDiscovery: true, include: [] },
  server: { middlewareMode: true },
  appType: "custom",
});

const previousWindow = globalThis.window;
globalThis.window = { matchMedia: () => ({ matches: false }) };
try {
  const [opportunity, resumeWorkspace, nav, workspace] = await Promise.all([
    vite.ssrLoadModule("/src/opportunity-ui.ts"),
    vite.ssrLoadModule("/src/resume-workspace.ts"),
    vite.ssrLoadModule("/src/resume-navigation.ts"),
    vite.ssrLoadModule("/src/workspace.ts"),
  ]);

  assert.match(workspace.shell("resume", "", "", true), /<h1>简历<\/h1>/, "内部简历路由仍应标识简历");

  const workspaceSource = readFileSync(new URL("../src/workspace.ts", import.meta.url), "utf8");
  const sidebarBlock = workspaceSource.match(/export const SIDEBAR_MODULES: \[string, string\]\[\] = \[([\s\S]*?)\];/)?.[1];
  const modules = [...(sidebarBlock || "").matchAll(/\["([^"]+)", "([^"]+)"\]/g)].map((match) => [match[1], match[2]]);
  assert.deepEqual(modules, [["wiki", "Wiki"], ["jobs", "机会"], ["projects", "项目"], ["work", "任职"]]);
  assert.deepEqual(SIDEBAR_MODULE_IDS, ["wiki", "jobs", "projects", "work"]);
  assert.equal(resolveSidebarHome("resume", ["resume", "work", "wiki"]), "work");
  assert.deepEqual(normalizeSidebarOrder(["resume", "work", "wiki"]), ["work", "wiki", "jobs", "projects"]);

  for (const [phase, result] of [
    ["resume", "active"], ["submitted", "active"], ["interview", "active"], ["offer", "active"],
    ["offer", "accepted"], ["interview", "rejected"], ["resume", "withdrawn"],
  ]) {
    const id = `opportunity:test-${phase}-${result}`;
    const html = opportunity.opportunityHTML({
      state: { opportunities: [{ id, company: "虚构公司", title: "测试岗位", phase, result, revision: 3, jd: "虚构岗位资料" }] },
      domain: {}, journey: { plans: [], notes: [] }, id, filter: "all", anchor: "",
      communications: [], timeline: { items: [], unknown_date_items: [] }, interviews: [], offer: null,
    });
    assert.match(html, /id="op-resume-section"/, `${phase}/${result} 应保留稳定简历入口`);
    assert.match(html, /id="op-resume"[^>]*>打开本机会简历</,
      `${phase}/${result} 应从当前 Opportunity 打开它自己的 Resume`);
    assert.ok(html.indexOf('class="op-phase-strip"') < html.indexOf('id="op-resume-section"'));
    assert.ok(html.indexOf('id="op-resume-section"') < html.indexOf('class="op-stage"'));
  }

  assert.deepEqual(nav.resolveOpportunityResume({
    documentId: "resume-document:original", phase: "offer", result: "active", readOnly: false,
  }), { kind: "open", documentId: "resume-document:original" }, "已有简历必须打开原 document_id，不得复制");
  for (const [phase, result] of [["resume", "active"], ["submitted", "active"], ["interview", "active"], ["offer", "active"], ["offer", "accepted"], ["offer", "rejected"], ["offer", "withdrawn"]]) {
    assert.deepEqual(nav.resolveOpportunityResume({
      documentId: "resume-document:original", phase, result, readOnly: false,
    }), { kind: "open", documentId: "resume-document:original" }, `${phase}/${result} 必须沿用原简历`);
  }
  assert.deepEqual(nav.resolveOpportunityResume({
    documentId: "", phase: "interview", result: "active", readOnly: false,
  }), { kind: "unavailable" }, "面试阶段没有简历时不得自动创建");
  assert.deepEqual(nav.resolveOpportunityResume({
    documentId: "", phase: "resume", result: "active", readOnly: false,
  }), { kind: "create" }, "新建仍只服从现有写简历阶段规则");
  assert.deepEqual(nav.resolveOpportunityResume({
    documentId: "", phase: "resume", result: "active", readOnly: true,
  }), { kind: "unavailable" }, "只读历史机会不能创建工作稿");
  assert.equal(nav.resumeEditorHref("resume-document:original"), "/#resume?document_id=resume-document%3Aoriginal");
  assert.equal(nav.resumeEditorHref("resume-document:original", { submit: true }), "/#resume?document_id=resume-document%3Aoriginal&submit=1");
  assert.equal(nav.opportunityResumeHref("opportunity:offer-a"), "/#opportunities/opportunity%3Aoffer-a?tab=resume");

  const editor = resumeWorkspace.resumeWorkspaceHTML([{
    document_id: "resume-document:original", company: "虚构公司", title: "Offer 岗位",
    opportunity_id: "opportunity:offer-a", saved_at: "2026-09-29T00:00:00Z",
  }], "resume-document:original", false, "关系兼容区");
  assert.match(editor, /虚构公司 · Offer 岗位/);
  assert.match(editor, /href="\/#opportunities\/opportunity%3Aoffer-a\?tab=resume"[^>]*>返回所属机会/);
  for (const control of ["saveDraft", "openVersions", "previewPdf", "exportPdf", "openMaterials", "openSources", "aiOptimize", "openAiProposals", "recordSubmitted"])
    assert.ok(editor.includes(`id="${control}"`), `Resume 编辑能力入口 ${control} 应保留`);
  assert.match(editor, /resumeDocumentSelector/);

  const mainSource = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
  const legacyEntry = readFileSync(new URL("../src/editor/legacy-entry.ts", import.meta.url), "utf8");
  assert.match(mainSource, /opportunityAnchor === "resume"[\s\S]*?#op-resume-section[\s\S]*?scrollIntoView/,
    "?tab=resume 应进入机会简历区域");
  assert.match(mainSource, /"resume", "profile"/, "Resume 页面路由继续作为内部兼容入口");
  for (const parameter of ["document_id", "legacy", "submit", "job_id"])
    assert.ok(legacyEntry.includes(`source.get("${parameter}")`), `${parameter} 旧链接参数应继续兼容`);
  assert.match(legacyEntry, /#opportunities\/\$\{encodeURIComponent\(source\.get\("job_id"\)!\)\}/,
    "旧 job_id 链接应回到对应 Opportunity");

  const legacy = resumeWorkspace.resumeWorkspaceHTML([], "", true, "");
  assert.match(legacy, /历史全局稿（只读）/);
  assert.doesNotMatch(legacy, /返回所属机会/);
} finally {
  globalThis.window = previousWindow;
  await vite.close();
}

console.log("Resume navigation: passed");
