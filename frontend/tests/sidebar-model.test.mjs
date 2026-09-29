import assert from "node:assert/strict";
import {
  SIDEBAR_MODULE_IDS,
  applySidebarPin,
  normalizeSidebarOrder,
  persistSidebarPreferences,
  resolveSidebarHome,
} from "../src/sidebar-model.ts";

assert.deepEqual(normalizeSidebarOrder(["jobs", "jobs", "unknown", "wiki"]), ["jobs", "wiki", "projects", "work"]);
assert.deepEqual(normalizeSidebarOrder(["wiki", "jobs", "resume", "work"]), ["wiki", "jobs", "work", "projects"]);
assert.deepEqual(normalizeSidebarOrder("bad-json"), [...SIDEBAR_MODULE_IDS]);
assert.deepEqual(applySidebarPin(["wiki", "jobs", "projects", "resume", "work"], "resume"), ["wiki", "jobs", "projects", "work"]);
assert.deepEqual(applySidebarPin(["resume", "wiki", "work", "jobs", "projects"], null), ["wiki", "work", "jobs", "projects"]);
assert.equal(resolveSidebarHome("missing", ["work", "wiki"]), "work");
assert.equal(resolveSidebarHome("jobs", ["work", "wiki"]), "jobs");
assert.equal(resolveSidebarHome("resume", ["resume", "work", "wiki"]), "work",
  "旧 home=resume 必须退回第一个仍有效的旧导航项");
assert.deepEqual(normalizeSidebarOrder(["resume", "work", "wiki"]), ["work", "wiki", "jobs", "projects"],
  "旧顺序里的 resume 应丢弃，其他合法顺序保留");

const storage = {
  values: new Map([["home", "wiki"], ["order", '["wiki","jobs","resume","work"]']]),
  writes: 0,
  getItem(key) { return this.values.get(key) ?? null; },
  setItem(key, value) {
    this.writes += 1;
    if (this.writes === 2) throw new Error("storage disabled during write");
    this.values.set(key, value);
  },
  removeItem(key) { this.values.delete(key); },
};
assert.equal(persistSidebarPreferences(storage, "home", "order", "resume", ["resume", "wiki", "jobs", "projects", "work"]), false);
assert.equal(storage.values.get("home"), "wiki");
assert.equal(storage.values.get("order"), '["wiki","jobs","resume","work"]');

const disabledStorage = {
  getItem() { throw new Error("storage disabled"); },
  setItem() { throw new Error("storage disabled"); },
  removeItem() { throw new Error("storage disabled"); },
};
assert.equal(persistSidebarPreferences(disabledStorage, "home", "order", null, ["wiki", "jobs", "projects", "work"]), false);

console.log("Sidebar model: 8 passed");
