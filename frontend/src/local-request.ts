export const CLIENT_BUILD_ID = "career-0.7.0-batch-f";

function clearRetiredBrowserCredentials(): void {
  try {
    window.sessionStorage.removeItem("career.local.session");
  } catch {
    // Browser storage may be unavailable; Career no longer reads this token.
  }
  try {
    window.localStorage.removeItem("career.local.resume");
  } catch {
    // Browser storage may be unavailable; Career no longer reads this handle.
  }
}

clearRetiredBrowserCredentials();

function sameOrigin(input: RequestInfo | URL): boolean {
  const url = new URL(
    typeof input === "string" ? input : input.toString(),
    window.location.href,
  );
  return url.origin === window.location.origin;
}

export async function requestLocal(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const response = await fetch(input, init);
  if (!sameOrigin(input)) return response;

  const backendBuildId = response.headers.get("X-Career-Build-Id");
  if (backendBuildId && backendBuildId !== CLIENT_BUILD_ID) {
    throw new Error("本地前后端版本不一致，请重启 Career 并重新载入页面");
  }
  return response;
}
