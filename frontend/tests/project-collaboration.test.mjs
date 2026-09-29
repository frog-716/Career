import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { projectCollaborationHTML } from "../src/project-collaboration.ts";

const workspace = readFileSync(new URL("../src/workspace.ts", import.meta.url), "utf8");
const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");

const project = { id: "project-a", employment_id: "employment-a" };
const personA = {
  id: "person-a", employment_id: "employment-a", identity_status: "confirmed",
  name: "虚构人物甲", role: "测试角色",
};
const personB = {
  id: "person-b", employment_id: "employment-b", identity_status: "confirmed",
  name: "虚构人物乙", role: "另一任职人物",
};
const html = projectCollaborationHTML(project, [personA, personB], [
  { id: "participant-a", project_id: "project-a", person_id: "person-a", role: "Reviewer" },
  { id: "participant-b", project_id: "project-a", person_id: "person-b", role: "不应显示" },
]);

assert.match(html, /协作人物/);
assert.match(html, /虚构人物甲/);
assert.match(html, /测试角色/);
assert.match(html, /Reviewer/);
assert.doesNotMatch(html, /虚构人物乙|不应显示/);
assert.match(html, /data-work-participant="project-a">关联人物<\/button>/);
assert.doesNotMatch(html, /关联已确认人物|identity confirmed|scope|兼容/);
assert.equal(projectCollaborationHTML({ id: "personal", employment_id: null }, [personA], []), "");

const projectPage = workspace.slice(workspace.indexOf('if (page === "projects")'), workspace.indexOf('if (page === "work")'));
assert.ok(projectPage.indexOf("projectWorkspaceHTML") < projectPage.indexOf("legacyProjectHTML"), "Project 正式工作区应先于旧工作记录生成");
const legacySection = workspace.slice(workspace.indexOf("function legacyProjectHTML"), workspace.indexOf("export const SIDEBAR_MODULES"));
assert.match(legacySection, /const legacyCount = events\.length \+ achievements\.length \+ evidence\.length/);
assert.match(legacySection, /return legacyHistoryDisclosureHTML\(legacyCount, body\)/);
assert.doesNotMatch(legacySection, /work-domain-card/);
assert.doesNotMatch(legacySection, /<details[^>]*\bopen\b|任职协作人物|data-work-participant|关联已确认人物/);
assert.match(legacySection, /legacyHistoryDisclosureHTML/);
assert.doesNotMatch(legacySection, /data-work-(?:event|achievement|evidence|link-evidence|reuse)=/, "旧工作记录只回看，不再新增重复实体或授权复用");
assert.match(legacySection, /data-work-revoke=/, "既有授权仍可撤销未来复用");
assert.doesNotMatch(legacySection, /<summary>[^<]*(?:兼容|compatibility)/i, "用户可见折叠标题不暴露内部兼容状态");
assert.match(main, /eligiblePeopleForProject/, "人物选择仍按 Employment 和身份边界过滤");

console.log("project-collaboration: ok");
