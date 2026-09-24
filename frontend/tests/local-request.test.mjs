import assert from "node:assert/strict";

function storage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    values,
    getItem(key) { return values.get(key) ?? null; },
    setItem(key, value) { values.set(key, value); },
    removeItem(key) { values.delete(key); },
  };
}

const session = storage({"career.local.session": "retired-session"});
const persistent = storage({"career.local.resume": "retired-resume"});
let promptCount = 0;
const calls = [];
globalThis.window = {
  location: {
    href: "http://127.0.0.1:8765/",
    origin: "http://127.0.0.1:8765",
  },
  sessionStorage: session,
  localStorage: persistent,
  prompt() { promptCount += 1; return "should-not-be-called"; },
};
globalThis.fetch = async (input, init = {}) => {
  calls.push({input, init});
  return new Response("{}", {
    status: 200,
    headers: {"X-Career-Build-Id": "career-0.7.0-batch-f"},
  });
};

const {requestLocal} = await import("../src/local-request.ts");
const response = await requestLocal("/api/state");

assert.equal(response.status, 200);
assert.equal(calls.length, 1, "a local request must not retry through an auth flow");
assert.equal(new Headers(calls[0].init.headers).has("Authorization"), false);
assert.equal(promptCount, 0);
assert.equal(session.getItem("career.local.session"), null);
assert.equal(persistent.getItem("career.local.resume"), null);

await requestLocal("https://example.invalid/public");
assert.equal(calls.length, 2, "external requests stay on their ordinary fetch path");

globalThis.fetch = async () => new Response("{}", {
  status: 200,
  headers: {"X-Career-Build-Id": "stale-build"},
});
await assert.rejects(
  requestLocal("/api/state"),
  /本地前后端版本不一致/,
);

console.log("local request without pairing: 3 passed");
