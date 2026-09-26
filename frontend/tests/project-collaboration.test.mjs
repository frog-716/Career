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
assert.ok(projectPage.indexOf("projectCollaborationHTML") < projectPage.indexOf("legacyProjectHTML"), "正式协作人物区域应在旧工作记录之前且独立可见");
const legacySection = workspace.slice(workspace.indexOf("function legacyProjectHTML"), workspace.indexOf("export const SIDEBAR_MODULES"));
assert.match(legacySection, /<details class="work-domain-card project-compatibility">/);
assert.doesNotMatch(legacySection, /<details[^>]*\bopen\b|任职协作人物|data-work-participant|关联已确认人物/);
assert.match(legacySection, /<summary>历史工作记录/);
assert.doesNotMatch(legacySection, /<summary>[^<]*(?:兼容|compatibility)/i, "用户可见折叠标题不暴露内部兼容状态");
assert.match(main, /eligiblePeopleForProject/, "人物选择仍按 Employment 和身份边界过滤");

console.log("project-collaboration: ok");
