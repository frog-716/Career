import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  eligiblePeopleForProject,
  participantsForProject,
  peopleForEmployment,
} from "../src/person-relations.ts";

const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
const ux3Workspace = readFileSync(new URL("../src/ux3-workspaces.ts", import.meta.url), "utf8");

assert.match(ux3Workspace, /data-add-employment-person/, "Employment 页面应提供添加人物入口");
assert.match(ux3Workspace, /data-edit-employment-person/, "Employment 人物卡片应提供编辑入口");
assert.doesNotMatch(ux3Workspace, /身份已确认/, "正常人物卡片不需要展示已确认状态标签");
assert.match(main, /identity_status/, "底层人物身份状态应继续保留给待解决身份流程使用");
assert.match(main, /\/work\/employments\/.*\/persons/, "手工新增人物必须落在指定 Employment");
assert.match(main, /function editEmploymentPerson/, "编辑人物应使用轻量编辑框");
assert.match(main, /expected_revision:\s*Number\(revision\)/, "人物编辑应使用 CAS revision");
assert.match(main, /eligiblePeopleForProject/, "Project 人物选择必须校验 Employment 与确认状态");
assert.doesNotMatch(main, /api\("\/work\/persons"/, "Project 入口不能创建全局 Person");

const persons = [
  { id: "person-a", employment_id: "employment:a", identity_status: "confirmed", name: "虚构甲", role: "直属领导" },
  { id: "person-b", employment_id: "employment:b", identity_status: "confirmed", name: "虚构乙", role: "同事" },
  { id: "person-unresolved", employment_id: "employment:a", identity_status: "unresolved", name: "虚构待确认" },
  { id: "person-global", identity_status: "confirmed", name: "旧虚构人物" },
];
const project = { id: "project-a", employment_id: "employment:a" };

assert.deepEqual(peopleForEmployment(persons, "employment:a").map((person) => person.id), [
  "person-a", "person-unresolved",
]);
assert.deepEqual(eligiblePeopleForProject(project, persons).map((person) => person.id), ["person-a"]);
assert.deepEqual(eligiblePeopleForProject({ id: "personal-project", employment_id: null }, persons), []);
assert.deepEqual(participantsForProject(project, persons, [
  { id: "link-good", project_id: "project-a", person_id: "person-a", role: "决策者" },
  { id: "link-wrong-employment", project_id: "project-a", person_id: "person-b", role: "Reviewer" },
  { id: "link-unresolved", project_id: "project-a", person_id: "person-unresolved", role: "Reviewer" },
]).map(({ person, role }) => [person.id, role]), [["person-a", "决策者"]]);

console.log("employment-person-relations: ok");
