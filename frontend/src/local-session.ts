export const CLIENT_BUILD_ID = "career-0.7.0-batch-f";
const SESSION_KEY = "career.local.session";
let pairingInFlight: Promise<string> | null = null;

function readToken(): string | null {
  try {
    return sessionStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

function saveToken(token: string): void {
  try {
    sessionStorage.setItem(SESSION_KEY, token);
  } catch {
    throw new Error("浏览器无法保存本地会话，请启用 sessionStorage 后重试");
  }
}

export function clearLocalSession(): void {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // A private browsing context may reject storage access; the server token
    // is still invalidated by the explicit logout request when possible.
  }
}

function pairingCodeInput(): Promise<string> {
  try {
    const code = window.prompt("请输入 Career 终端显示的一次性本地配对码：");
    if (!code?.trim()) return Promise.reject(new Error("未完成本地配对；当前页面不会读取本地资料"));
    return Promise.resolve(code.trim());
  } catch {
    return new Promise((resolve, reject) => {
      const dialog = document.createElement("dialog");
      dialog.innerHTML = "<form method=dialog><h2>本地配对</h2><p>请在 Career 交互式终端读取一次性配对码，再输入到这里。</p><label>配对码<input required autocomplete=off spellcheck=false></label><p role=alert></p><button value=cancel>取消</button><button value=ok type=submit>配对</button></form>";
      document.body.append(dialog);
      const form = dialog.querySelector("form")!;
      const input = dialog.querySelector("input") as HTMLInputElement;
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        if (!input.value.trim()) return;
        dialog.close("ok");
      });
      dialog.addEventListener("close", () => {
        const value = dialog.returnValue === "ok" ? input.value.trim() : "";
        dialog.remove();
        value ? resolve(value) : reject(new Error("未完成本地配对；当前页面不会读取本地资料"));
      }, {once: true});
      dialog.showModal();
      input.focus();
    });
  }
}

async function pair(): Promise<string> {
  const code = await pairingCodeInput();
  const response = await fetch("/api/pair", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Career-Request": "1" },
    body: JSON.stringify({ code: code.trim() }),
    cache: "no-store",
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || typeof result.token !== "string") {
    throw new Error(result.detail || "本地配对失败，请确认配对码仍在有效期内");
  }
  saveToken(result.token);
  return result.token;
}

async function ensureToken(): Promise<string> {
  const existing = readToken();
  if (existing) return existing;
  if (!pairingInFlight) {
    pairingInFlight = pair().finally(() => {
      pairingInFlight = null;
    });
  }
  return pairingInFlight;
}

function sameOrigin(input: RequestInfo | URL): boolean {
  const url = new URL(typeof input === "string" ? input : input.toString(), window.location.href);
  return url.origin === window.location.origin;
}

async function send(input: RequestInfo | URL, init: RequestInit, token: string | null): Promise<Response> {
  const headers = new Headers(init.headers || {});
  if (token && sameOrigin(input)) headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

export async function requestWithSession(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  if (!sameOrigin(input)) return fetch(input, init);
  let token = readToken();
  let response = await send(input, init, token);
  if (response.status === 401 && new URL(typeof input === "string" ? input : input.toString(), window.location.href).pathname !== "/api/pair") {
    clearLocalSession();
    token = await ensureToken();
    response = await send(input, init, token);
  }
  const backendBuildId = response.headers.get("X-Career-Build-Id");
  if (backendBuildId && backendBuildId !== CLIENT_BUILD_ID) {
    throw new Error("本地前后端版本不一致，请重启 Career 并重新载入页面");
  }
  return response;
}

export async function logoutLocalSession(): Promise<void> {
  const token = readToken();
  if (token) {
    await send("/api/logout", { method: "POST", headers: { "Content-Type": "application/json", "X-Career-Request": "1" }, body: "{}" }, token).catch(() => undefined);
  }
  clearLocalSession();
}
