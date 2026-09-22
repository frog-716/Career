import assert from "node:assert/strict";

const storage = new Map();
const persistentStorage = new Map();
const requests = [];
let promptCount = 0;
const acceptedTokens = new Set(["peer-session-token"]);
const channels = new Set();

class FakeBroadcastChannel {
  constructor() {
    this.listeners = new Set();
    channels.add(this);
  }

  addEventListener(type, listener) {
    if (type === "message") this.listeners.add(listener);
  }

  postMessage(data) {
    for (const channel of channels) {
      if (channel === this) continue;
      queueMicrotask(() => {
        for (const listener of channel.listeners) listener({ data });
      });
    }
  }

  close() {
    channels.delete(this);
  }
}

globalThis.BroadcastChannel = FakeBroadcastChannel;
const pairedPeer = new FakeBroadcastChannel("career.local.session.v1");
pairedPeer.addEventListener("message", ({ data }) => {
  if (data?.type === "career-session-request") {
    pairedPeer.postMessage({
      type: "career-session-response",
      requestId: data.requestId,
      token: "peer-session-token",
    });
  }
});

globalThis.sessionStorage = {
  getItem(key) {
    return storage.get(key) ?? null;
  },
  setItem(key, value) {
    storage.set(key, String(value));
  },
  removeItem(key) {
    storage.delete(key);
  },
};

globalThis.localStorage = {
  getItem(key) {
    return persistentStorage.get(key) ?? null;
  },
  setItem(key, value) {
    persistentStorage.set(key, String(value));
  },
  removeItem(key) {
    persistentStorage.delete(key);
  },
};

globalThis.window = {
  location: { href: "http://127.0.0.1:8765/", origin: "http://127.0.0.1:8765" },
  prompt() {
    promptCount += 1;
    return "test-pairing-code";
  },
};

function response(status, body = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: new Headers({ "X-Career-Build-Id": "career-0.7.0-batch-f" }),
    async json() {
      return body;
    },
  };
}

globalThis.fetch = async (input, init = {}) => {
  const url = String(input);
  const authorization = new Headers(init.headers || {}).get("Authorization");
  requests.push({ url, authorization });

  if (url.endsWith("/api/state") && (!authorization || !acceptedTokens.has(authorization.replace("Bearer ", "")))) {
    return response(401, { detail: "pairing_required" });
  }
  if (url.endsWith("/api/pair")) {
    acceptedTokens.add("session-token");
    return response(200, { token: "session-token", resume_token: "resume-token" });
  }
  if (url.endsWith("/api/session/resume")) {
    acceptedTokens.add("resumed-session-token");
    return response(200, { token: "resumed-session-token", resume_token: "resume-token" });
  }
  if (url.endsWith("/api/state")) return response(200, { ok: true });
  return response(404, { detail: "not_found" });
};

const { clearLocalSession, requestWithSession } = await import("../src/local-session.ts");
const result = await requestWithSession("/api/state");

assert.equal(result.status, 200);
assert.equal(promptCount, 0, "normal Career startup must not reopen the native pairing prompt");
assert.equal(requests.some(({ url }) => url.endsWith("/api/pair")), false, "normal Career startup must not consume a pairing code");
assert.equal(requests.at(-1)?.authorization, "Bearer peer-session-token");

pairedPeer.close();
clearLocalSession();
const firstPair = await requestWithSession("/api/state");
assert.equal(firstPair.status, 200);
assert.equal(promptCount, 1, "without a paired peer, the initial authorization must still be explicit");
assert.equal(requests.filter(({ url }) => url.endsWith("/api/pair")).length, 1);

acceptedTokens.delete("session-token");
clearLocalSession();
const resumed = await requestWithSession("/api/state");
assert.equal(resumed.status, 200);
assert.equal(promptCount, 1, "a Career restart must use the local resume handle without prompting again");
assert.equal(requests.filter(({ url }) => url.endsWith("/api/session/resume")).length, 1);

const stalePeer = new FakeBroadcastChannel("career.local.session.v1");
stalePeer.addEventListener("message", ({ data }) => {
  if (data?.type === "career-session-request") {
    stalePeer.postMessage({
      type: "career-session-response",
      requestId: data.requestId,
      token: "stale-session-token",
    });
  }
});
clearLocalSession();
persistentStorage.delete("career.local.resume");
const afterStalePeer = await requestWithSession("/api/state");
assert.equal(afterStalePeer.status, 200);
assert.equal(promptCount, 2, "a stale peer token must fall back to explicit pairing");
assert.equal(requests.filter(({ url }) => url.endsWith("/api/pair")).length, 2);
stalePeer.close();
