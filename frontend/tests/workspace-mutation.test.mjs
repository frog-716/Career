import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { mutateAndRefreshWorkspace } from "../src/workspace-mutation.ts";

const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");

function functionBody(name, nextName) {
  const start = main.indexOf(`function ${name}(`);
  const end = nextName ? main.indexOf(`function ${nextName}(`, start + 1) : main.length;
  assert.notEqual(start, -1, `${name} must exist`);
  return main.slice(start, end === -1 ? main.length : end);
}

function makePorts(initialState, route, options = {}) {
  let serverState = structuredClone(initialState);
  let renderedState = structuredClone(initialState);
  let renderedRoute = null;
  let currentRoute = structuredClone(route);
  let reloadCount = 0;
  let renderCount = 0;
  let afterSaveCount = 0;
  let refreshErrorCount = 0;
  const ports = {
    captureRoute: () => structuredClone(currentRoute),
    reload: async () => {
      reloadCount += 1;
      if (options.reload) await options.reload({ setRoute: (value) => { currentRoute = value; }, serverState });
      if (options.failReload) throw new Error("offline");
      renderedState = structuredClone(serverState);
    },
    restoreRoute: (snapshot) => { currentRoute = structuredClone(snapshot); },
    render: () => { renderCount += 1; renderedRoute = structuredClone(currentRoute); },
    afterSave: () => { afterSaveCount += 1; },
    onRefreshError: () => { refreshErrorCount += 1; },
  };
  return {
    ports,
    setRoute: (value) => { currentRoute = structuredClone(value); },
    get state() { return serverState; },
    get renderedState() { return renderedState; },
    get route() { return currentRoute; },
    get renderedRoute() { return renderedRoute; },
    get counts() { return { reloadCount, renderCount, afterSaveCount, refreshErrorCount }; },
  };
}

const employmentRoute = { page: "work", projectId: "", employmentId: "employment-a", hash: "#work/episode-a" };
const person = { id: "person-a", employment_id: "employment-a", name: "虚构旧名", role: "旧角色" };

{
  const ui = makePorts({ persons: [], participants: [] }, employmentRoute);
  let writes = 0;
  const outcome = await mutateAndRefreshWorkspace(async () => {
    writes += 1;
    ui.state.persons.push({ ...person });
    return person;
  }, ui.ports);
  assert.equal(outcome.status, "refreshed", "添加人物后应立即显示最新人物");
  assert.equal(writes, 1, "一次保存只能创建一条人物");
  assert.deepEqual(ui.renderedState.persons, [person]);
  assert.deepEqual(ui.route, employmentRoute, "当前 Employment 路由和选择应保留");
  assert.deepEqual(ui.renderedRoute, employmentRoute);
  assert.deepEqual(ui.counts, { reloadCount: 1, renderCount: 1, afterSaveCount: 1, refreshErrorCount: 0 });
}

{
  const ui = makePorts({ persons: [{ ...person }] }, employmentRoute);
  const outcome = await mutateAndRefreshWorkspace(async () => {
    ui.state.persons[0] = { ...ui.state.persons[0], name: "虚构新名", role: "新角色" };
    return ui.state.persons[0];
  }, ui.ports);
  assert.equal(outcome.status, "refreshed", "编辑人物后应立即显示修改内容");
  assert.deepEqual(ui.renderedState.persons, [{ ...person, name: "虚构新名", role: "新角色" }]);
  assert.equal(ui.renderedState.persons.length, 1, "编辑不得创建第二个人物");
  assert.equal(ui.renderedState.persons[0].id, person.id, "编辑后 Person ID 不变");
  assert.deepEqual(ui.route, employmentRoute);
}

{
  const projectRoute = { page: "projects", projectId: "project-a", employmentId: "", hash: "#projects/project-a" };
  const ui = makePorts({ persons: [{ ...person }], participants: [] }, projectRoute);
  const outcome = await mutateAndRefreshWorkspace(async () => {
    ui.state.participants.push({ id: "participant-a", project_id: "project-a", person_id: person.id, role: "Reviewer" });
    return ui.state.participants[0];
  }, ui.ports);
  assert.equal(outcome.status, "refreshed", "Project 关联人物后应立即显示最新关系");
  assert.deepEqual(ui.renderedState.participants, [{ id: "participant-a", project_id: "project-a", person_id: person.id, role: "Reviewer" }]);
  assert.equal(ui.renderedState.persons.length, 1, "关联 Project 不得复制 Person");
  assert.equal(ui.renderedState.participants[0].person_id, ui.renderedState.persons[0].id, "关系应指向原 Person ID");
  assert.deepEqual(ui.route, projectRoute, "当前 Project 路由和选择应保留");
}

{
  const projectRouteA = { page: "projects", projectId: "project-a", employmentId: "", hash: "#projects/project-a" };
  const projectRouteB = { page: "projects", projectId: "project-b", employmentId: "", hash: "#projects/project-b" };
  const ui = makePorts({ projects: [] }, projectRouteA);
  let sawRouteChange = false;
  const outcome = await mutateAndRefreshWorkspace(async () => {
    ui.setRoute(projectRouteB);
    ui.state.projects.push({ id: "project-a", name: "已保存项目" });
    return ui.state.projects[0];
  }, {
    ...ui.ports,
    afterSave: (_value, context) => { sawRouteChange = context.routeChangedDuringMutation; },
  });
  assert.equal(outcome.status, "refreshed");
  assert.equal(sawRouteChange, true, "写入期间用户切换对象时应识别新选择");
  assert.deepEqual(ui.route, projectRouteB, "刷新不能抢回用户刚选的 Project");
  assert.deepEqual(ui.renderedRoute, projectRouteB);
}

{
  const ui = makePorts({ persons: [] }, employmentRoute);
  const stale = Object.assign(new Error("stale"), { status: 409 });
  let closed = false;
  await assert.rejects(() => mutateAndRefreshWorkspace(async () => { throw stale; }, {
    ...ui.ports,
    afterSave: () => { closed = true; },
  }), (error) => error === stale, "CAS 冲突必须原样交给表单显示");
  assert.equal(closed, false);
  assert.equal(ui.counts.reloadCount, 0, "保存失败不能假装成功后刷新");
  assert.equal(ui.counts.renderCount, 0);
}

{
  const ui = makePorts({ persons: [] }, employmentRoute, { failReload: true });
  let writes = 0;
  const outcome = await mutateAndRefreshWorkspace(async () => {
    writes += 1;
    ui.state.persons.push({ ...person });
    return person;
  }, ui.ports);
  assert.equal(outcome.status, "refresh_failed");
  assert.equal(writes, 1, "保存成功但刷新失败时不得重发写入");
  assert.equal(ui.counts.afterSaveCount, 1);
  assert.equal(ui.counts.refreshErrorCount, 1);
  assert.deepEqual(ui.route, employmentRoute);
}

assert.match(main, /targetPage === "projects"[\s\S]*?api\("\/work-domain"\)/, "Project 页刷新必须重新读取 Work Domain");
assert.match(main, /mutateAndRefreshWorkspace/, "Phase B/C 写操作应统一走当前 workspace 刷新");
assert.doesNotMatch(main, /location\.reload\s*\(/, "不能用整页浏览器刷新解决状态更新");
for (const [name, nextName] of [
  ["editEpisode", "exportEpisode"],
  ["workForm", "editWorkProject"],
  ["editWorkProject", "createWorkProject"],
  ["linkExistingProject", "createWorkEvent"],
  ["addEmploymentPerson", "editEmploymentPerson"],
  ["confirmWorkPerson", "addWorkParticipant"],
]) {
  assert.match(functionBody(name, nextName), /refreshWorkspaceAfterMutation/, `${name} 成功后必须读取并显示最新对象`);
}
for (const [name, nextName] of [["editEmploymentPerson", "confirmWorkPerson"], ["addWorkParticipant", "changeJobStatus"]]) {
  assert.match(functionBody(name, nextName), /workForm\(/, `${name} 必须使用统一的 workspace 表单`);
}
assert.match(functionBody("editEpisode", "exportEpisode"), /refreshWorkspaceAfterMutation/, "任职保存后应读取最新对象");
assert.match(functionBody("editEpisode", "exportEpisode"), /history\.replaceState/, "创建或编辑任职后应保留正确的当前任职路由");
assert.doesNotMatch(functionBody("editEmploymentPerson", "confirmWorkPerson"), /身份确认状态/, "人物编辑表单不显示内部身份状态文案");
assert.match(functionBody("editWorkProject", "createWorkProject"), /requestKey[\s\S]*?api\("\/work\/projects"/, "单个项目创建表单的幂等键在重试时必须稳定");

console.log("workspace-mutation: ok");
