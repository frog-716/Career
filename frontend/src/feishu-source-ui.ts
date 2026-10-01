type Obj = Record<string, any>;

const esc = (value: unknown) => String(value ?? "").replace(/[&<>"']/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[character]!));

function safeFeishuUrl(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 2048) return null;
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase().replace(/\.$/, "");
    const allowed = host === "feishu.cn" || host.endsWith(".feishu.cn")
      || host === "larksuite.com" || host.endsWith(".larksuite.com");
    if (url.protocol !== "https:" || !allowed || url.username || url.password || url.port) return null;
    return url.toString();
  } catch {
    return null;
  }
}

export function feishuResultsHTML(items: Obj[], hasMore: boolean, searched = true): string {
  const rows = (items || []).map((item: Obj) => `<article class="feishu-resource-row"><div><strong>${esc(item.title)}</strong><small>${esc(item.resource_type === "docx" ? "飞书文档" : "文档")}${item.edited_at ? ` · ${esc(item.edited_at)}` : ""}</small></div><button class="secondary" type="button" data-feishu-select="${esc(item.selection_id)}">选择</button></article>`).join("");
  return `${rows}${searched && !rows && items.length === 0 ? '<p class="muted">没有找到匹配文档。</p>' : ""}${hasMore ? '<button class="text-btn" type="button" data-feishu-more>加载更多</button>' : ""}`;
}

export function feishuPreviewHTML(snapshot: Obj): string {
  const resource = snapshot.resource || {};
  const resourceType = resource.resource_type === "docx" ? "飞书文档" : "文档";
  const link = safeFeishuUrl(resource.url);
  return `<p class="muted">${esc(resource.title)} · ${resourceType}</p>${link ? `<p><a href="${esc(link)}" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">在飞书中打开</a></p>` : ""}<pre class="feishu-preview-content">${esc(snapshot.content)}</pre><div class="actions"><button class="primary" type="button" data-feishu-import>导入 Career</button><button class="secondary" type="button" data-feishu-back>返回搜索结果</button></div>`;
}

export function feishuImportRequest(previewId: string, scope: Obj, idempotencyKey: string): Obj {
  return {
    preview_id: previewId,
    scope_type: scope.scope_type,
    scope_id: scope.scope_id,
    idempotency_key: idempotencyKey,
  };
}

export async function readLocalTextFile(file: {
  name: string;
  size: number;
  arrayBuffer(): Promise<ArrayBuffer>;
}): Promise<{ title: string; content: string }> {
  if (!/\.(txt|md)$/i.test(file.name)) throw new Error("本地资料仅支持 TXT 或 Markdown 文件。");
  if (file.size > 400_000) throw new Error("本地文字文件不能超过 400 KB。");
  const content = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
  if (content.length > 100_000) throw new Error("本地原文不能超过 100,000 个字符。");
  return { title: file.name, content };
}
