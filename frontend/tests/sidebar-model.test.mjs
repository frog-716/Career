import assert from "node:assert/strict";
import {
  SIDEBAR_MODULE_IDS,
  applySidebarPin,
  normalizeSidebarOrder,
  persistSidebarPreferences,
  resolveSidebarHome,
} from "../src/sidebar-model.ts";

assert.deepEqual(normalizeSidebarOrder(["jobs", "jobs", "unknown", "wiki"]), ["jobs", "wiki", "resume", "work"]);
assert.deepEqual(normalizeSidebarOrder("bad-json"), [...SIDEBAR_MODULE_IDS]);
assert.deepEqual(applySidebarPin(["wiki", "jobs", "resume", "work"], "resume"), ["resume", "wiki", "jobs", "work"]);
assert.deepEqual(applySidebarPin(["resume", "wiki", "work", "jobs"], null), ["resume", "wiki", "work", "jobs"]);
assert.equal(resolveSidebarHome("missing", ["work", "wiki"]), "work");
assert.equal(resolveSidebarHome("jobs", ["work", "wiki"]), "jobs");

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
assert.equal(persistSidebarPreferences(storage, "home", "order", "resume", ["resume", "wiki", "jobs", "work"]), false);
assert.equal(storage.values.get("home"), "wiki");
assert.equal(storage.values.get("order"), '["wiki","jobs","resume","work"]');

const disabledStorage = {
  getItem() { throw new Error("storage disabled"); },
  setItem() { throw new Error("storage disabled"); },
  removeItem() { throw new Error("storage disabled"); },
};
assert.equal(persistSidebarPreferences(disabledStorage, "home", "order", null, ["wiki", "jobs", "resume", "work"]), false);

console.log("T15 sidebar model: 7 passed");
