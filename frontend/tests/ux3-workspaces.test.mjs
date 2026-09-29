import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createServer } from "vite";

const root = new URL("..", import.meta.url).pathname;
const vite = await createServer({
  configFile: false,
  root,
  optimizeDeps: { noDiscovery: true, include: [] },
  server: { middlewareMode: true },
  appType: "custom",
});

try {
  const {
    projectWorkspaceHTML,
    employmentWorkspaceHTML,
    personWorkspaceHTML,
    legacyHistoryDisclosureHTML,
  } = await vite.ssrLoadModule("/src/ux3-workspaces.ts");

  assert.equal(legacyHistoryDisclosureHTML(0, "legacy body"), "",
    "没有旧历史时整个区域都不应渲染");
  assert.equal(legacyHistoryDisclosureHTML(5, "legacy body"),
    '<details class="ux3-more project-compatibility"><summary>历史工作记录 · 5 条 →</summary>legacy body</details>',
    "有旧历史时默认只显示一条紧凑入口");

  const employmentA = {
    id: "employment:a", legacy_episode_id: "episode-a", company: "虚构公司 A",
    role: "产品总监", start_date: "2024-03-01", end_date: null, focus: "推进虚构工作台试点。",
  };
  const employmentB = {
    id: "employment:b", legacy_episode_id: "episode-b", company: "虚构公司 B",
    role: "设计顾问", start_date: "2022-01-01", end_date: "2024-06-30", focus: "完成虚构协作流程交接。",
  };
  const project = {
    id: "project:a", name: "虚构 Career 工作台", description: "长期整理个人职业资料。",
    tags: ["#AI", "#个人项目"], status: "active", employment_id: employmentA.id,
  };
  const personA = {
    id: "person:a", name: "虚构人物 A", role: "产品总监",
    employment_id: employmentA.id, identity_status: "confirmed",
  };
  const personB = {
    id: "person:b", name: "不应显示的人物", role: "另一任职角色",
    employment_id: employmentB.id, identity_status: "confirmed",
  };
  const rawProject = {
    id: "raw:project", kind: "raw_material", revision: 1, hash: "a".repeat(64),
    title: "虚构项目评审记录", source_kind: "manual_text", created_at: "2026-09-27T03:00:00Z",
    source_ref: { kind: "raw_material", id: "raw:project", revision: 1, hash: "a".repeat(64) },
  };
  const wikiProject = [
    { id: "wiki:focus", knowledge_type: "observation", status: "current", content: "先梳理边界，再开始实现。", updated_at: "2026-09-27T04:00:00Z", tags: ["#工作方式"] },
    { id: "wiki:secondary", knowledge_type: "fact", status: "current", content: "评审安排在周五。", updated_at: "2026-09-26T04:00:00Z", tags: [] },
  ];
  const wikiEmployment = [
    { id: "wiki:employment", knowledge_type: "fact", status: "current", content: "团队正在试点新的交付流程。", updated_at: "2026-09-27T04:00:00Z", tags: [] },
  ];
  const directPersonRaw = {
    ...rawProject, id: "raw:person", scope_type: "person", scope_id: personA.id,
    title: "只属于人物的虚构资料",
    source_ref: { kind: "raw_material", id: "raw:person", revision: 1, hash: "c".repeat(64) },
  };
  const relatedEmploymentRaw = {
    ...rawProject, id: "raw:employment", scope_type: "employment", scope_id: employmentA.id,
    title: "明确引用的任职来源",
    source_ref: { kind: "raw_material", id: "raw:employment", revision: 1, hash: "b".repeat(64) },
  };
  const relatedProjectRaw = {
    ...rawProject, id: "raw:linked-project", scope_type: "project", scope_id: project.id,
    title: "同任职项目的其他资料",
    source_ref: { kind: "raw_material", id: "raw:linked-project", revision: 1, hash: "d".repeat(64) },
  };
  const wikiPerson = [
    { id: "wiki:person-fact", knowledge_type: "fact", status: "current", content: "重要方案先给结论，再补证据。", updated_at: "2026-09-27T04:00:00Z", tags: [], source_refs: [relatedEmploymentRaw.source_ref] },
    { id: "wiki:person-observation", knowledge_type: "observation", status: "current", content: "评审前会主动核对风险。", updated_at: "2026-09-26T04:00:00Z", tags: [] },
  ];
  const participant = { id: "participant:a", project_id: project.id, person_id: personA.id, role: "Reviewer" };

  const projectHTML = projectWorkspaceHTML({
    project, employment: employmentA, people: [personA, personB], participants: [participant],
    knowledge: wikiProject, raw: [rawProject],
    legacyHTML: '<details class="ux3-more"><summary>更多 · 历史工作记录</summary>旧记录</details>',
  });
  const projectText = projectHTML.replace(/<[^>]*>/g, " ");
  for (const label of ["最近更新", "最近变化", "当前理解", "资料", "协作人物"]) assert.ok(projectText.includes(label), `Project 缺少 ${label}`);
  assert.doesNotMatch(projectHTML, /<h3>当前重点<\/h3>/,
    "没有正式 Project focus 字段时，最近 Wiki 更新不能被标成当前重点");
  const projectUpdatePanel = projectHTML.slice(
    projectHTML.indexOf('<section class="ux3-current-focus"'),
    projectHTML.indexOf("</section>", projectHTML.indexOf('<section class="ux3-current-focus"')),
  );
  assert.match(projectUpdatePanel, /<h3>最近更新<\/h3>[\s\S]*先梳理边界，再开始实现。/,
    "最近的 Wiki 内容应明确标记为最近更新");
  const sectionOrder = ["最近更新", "最近变化", "当前理解", "资料", "协作人物"].map((label) =>
    projectHTML.indexOf(`<h3>${label}</h3>`),
  );
  assert.ok(sectionOrder.every((position) => position >= 0), "主要区块标题应使用稳定层级");
  assert.ok(sectionOrder.every((position, index) => index === 0 || sectionOrder[index - 1] < position),
    "Project 的区块应按工作优先级排序");
  assert.match(projectHTML, /先梳理边界，再开始实现。/);
  assert.match(projectHTML, /虚构项目评审记录/);
  assert.match(projectText, /项目角色[：:]\s*Reviewer/);
  assert.match(projectText, /任职角色[：:]\s*产品总监/);
  assert.match(projectHTML, /data-open-person="person:a"/);
  assert.doesNotMatch(projectText, /不应显示的人物|scope|revision|source_ref|Participant|Event|Achievement|Evidence/);
  assert.match(projectHTML, /<details[^>]*class="[^"]*ux3-more/);
  assert.doesNotMatch(projectHTML, /<details[^>]*\bopen\b/);
  assert.equal((projectHTML.match(/class="(?:primary|[^\"]* primary)"/g) || []).length, 0,
    "对象详情只保留次级编辑入口，不新增第二个主操作");

  const personalProjectHTML = projectWorkspaceHTML({
    project: { ...project, id: "project:personal", employment_id: null },
    employment: null, people: [personA, personB], participants: [participant],
    knowledge: [], raw: [],
  });
  assert.doesNotMatch(personalProjectHTML, /协作人物|data-work-participant/,
    "没有 Employment 的 Project 不要求 Person / Participant");

  const activeHTML = employmentWorkspaceHTML({
    employment: employmentA, projects: [project], people: [personA],
    knowledge: wikiEmployment, raw: [rawProject], notes: [],
  });
  assert.ok(activeHTML.indexOf("当前重点") < activeHTML.indexOf("关联项目"));
  assert.ok(activeHTML.indexOf("关联项目") < activeHTML.indexOf("重要人物"));
  assert.ok(activeHTML.indexOf("重要人物") < activeHTML.indexOf("资料"));
  assert.match(activeHTML, /虚构 Career 工作台/);
  assert.match(activeHTML, /data-open-project="project:a"/);
  assert.match(activeHTML, /data-open-person="person:a"/);
  assert.doesNotMatch(activeHTML.replace(/<[^>]*>/g, " "), /人物 ID|身份已确认|scope|revision/);

  const noFocusEmploymentHTML = employmentWorkspaceHTML({
    employment: { ...employmentA, focus: "  " }, projects: [], people: [],
    knowledge: wikiEmployment, raw: [], notes: [],
  });
  const employmentFocusPanel = noFocusEmploymentHTML.slice(
    noFocusEmploymentHTML.indexOf('<section class="ux3-current-focus"'),
    noFocusEmploymentHTML.indexOf("</section>", noFocusEmploymentHTML.indexOf('<section class="ux3-current-focus"')),
  );
  assert.match(employmentFocusPanel, /<h3>当前重点<\/h3>[\s\S]*还没有填写当前重点/,
    "Employment 没有明确重点时应显示空态，而不是填入最近的 Wiki");
  assert.doesNotMatch(employmentFocusPanel, /团队正在试点新的交付流程/);
  assert.match(noFocusEmploymentHTML, /团队正在试点新的交付流程/,
    "空重点时，Wiki 内容仍留在当前理解区域");

  const recentRaw = Array.from({ length: 5 }, (_, index) => ({
    ...rawProject, id: `raw:employment:${index}`, title: `任职资料 ${index}`,
    created_at: `2026-09-${String(28 - index).padStart(2, "0")}T03:00:00Z`,
  }));
  const recentMaterialsHTML = employmentWorkspaceHTML({
    employment: employmentA, projects: [], people: [], knowledge: [], raw: recentRaw,
  });
  assert.match(recentMaterialsHTML, /最近资料/);
  for (const expected of ["任职资料 0", "任职资料 1", "任职资料 2"]) assert.match(recentMaterialsHTML, new RegExp(expected));
  for (const omitted of ["任职资料 3", "任职资料 4"]) assert.doesNotMatch(recentMaterialsHTML, new RegExp(omitted));

  const endedHTML = employmentWorkspaceHTML({
    employment: employmentB, projects: [], people: [personB], knowledge: [], raw: [], notes: [],
  });
  assert.match(endedHTML, /已结束/);
  assert.doesNotMatch(endedHTML, /警告|失效|已删除/);

  const personHTML = personWorkspaceHTML({
    person: personA, employment: employmentA,
    projects: [{ project, role: "Reviewer" }], knowledge: wikiPerson,
    raw: [directPersonRaw, relatedEmploymentRaw, relatedProjectRaw],
  });
  assert.match(personHTML, /虚构人物 A/);
  assert.match(personHTML, /任职角色[：:]\s*产品总监/);
  assert.match(personHTML, /重要方案先给结论，再补证据。/);
  assert.match(personHTML, /观察/);
  assert.match(personHTML, /评审前会主动核对风险。/);
  const personObservationSection = personHTML.slice(
    personHTML.indexOf('class="ux3-section ux3-person-observations"'),
    personHTML.indexOf("</section>", personHTML.indexOf('class="ux3-section ux3-person-observations"')),
  );
  assert.doesNotMatch(personObservationSection, /ux3-knowledge-type/,
    "Person 的观察区标题已经表达知识类型，条目里不应重复显示一次");
  assert.match(personHTML, /项目角色[：:]\s*Reviewer/);
  assert.match(personHTML, /data-open-project="project:a"/);
  assert.match(personHTML, /只属于人物的虚构资料/);
  assert.match(personHTML, /明确引用的任职来源/,
    "人物 Wiki 明确引用任职资料时仍能打开来源");
  const personMaterials = personHTML.slice(personHTML.indexOf('data-ux3-material-scope="person:'), personHTML.indexOf("</section>", personHTML.indexOf('data-ux3-material-scope="person:')));
  assert.match(personMaterials, /只属于人物的虚构资料/);
  assert.doesNotMatch(personMaterials, /明确引用的任职来源|同任职项目的其他资料/,
    "人物资料列表只显示直接属于人物的 Raw；范围兼容来源仍只用于明确知识引用");
  assert.doesNotMatch(personHTML.replace(/<[^>]*>/g, " "), /identity_status|confirmed|Person ID|scope|source_ref/);

  const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
  const workspace = readFileSync(new URL("../src/workspace.ts", import.meta.url), "utf8");
  assert.match(main, /targetPage === "person"[\s\S]*?scope_type=person/);
  assert.match(main, /navigate\("person",/);
  assert.match(main, /requested === "person"/);
  assert.match(workspace, /page === "person"/);

  console.log("ux3-workspaces: ok");
} finally {
  await vite.close();
}
