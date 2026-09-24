import "./editor/legacy.css";
import { requestLocal } from "./local-request";

type Row = Record<string, any>;

const escape = (value: unknown): string =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (character) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        character
      ]!,
  );

export interface ResumeEditorController {
  documentId: string;
  hasUnsavedChanges(): boolean;
  requestClose(): Promise<boolean>;
  destroy(): void;
}

export function resumeWorkspaceHTML(
  documents: Row[],
  selectedDocumentId: string,
  legacy: boolean,
  relationHTML: string,
): string {
  const selected = documents.find((document) => document.document_id === selectedDocumentId);
  const options = documents
    .map(
      (document) =>
        `<option value="${escape(document.document_id)}" ${document.document_id === selectedDocumentId ? "selected" : ""}>${escape(document.company)} · ${escape(document.title)}</option>`,
    )
    .join("");

  if (!selected && !legacy) {
    return `<section class="resume-catalogue">
      <div class="pane-heading"><div><h2>简历工作台</h2><p class="muted">选择一份简历后，直接在这里编辑、保存、处理 AI 建议和管理版本。</p></div><button class="secondary" data-page="jobs">从机会开始新简历</button></div>
      <div class="resume-document-list">
        ${documents.map((document) => `<button class="resume-document-card" data-resume-document="${escape(document.document_id)}"><span><b>${escape(document.company)} · ${escape(document.title)}</b><small>最近编辑 ${escape(new Date(document.saved_at).toLocaleString("zh-CN"))}</small></span><strong>打开并编辑</strong></button>`).join("") || '<div class="empty">还没有工作稿。请从具体机会选择来源并创建。</div>'}
      </div>
      <button class="text-btn" data-resume-legacy>查看历史全局稿（只读）</button>
    </section>`;
  }

  return `<section class="resume-workspace-page">
    <div class="resume-editor" data-resume-editor-host>
      <header class="app-bar resume-workspace-controls">
        <div class="resume-context-row">
          <div class="resume-context-main">
            <label class="resume-document-selector">当前简历<select id="resumeDocumentSelector"><option value="legacy" ${legacy ? "selected" : ""}>历史全局稿（只读）</option>${options}</select></label>
            <span id="saveStatus" class="save-status" role="status">正在载入</span>
            <span id="pageStatus" class="page-status">A4 检查中</span>
          </div>
          <details class="resume-relation-menu"><summary>与机会的关系</summary><div class="resume-relations">${relationHTML}</div></details>
        </div>
        <div class="resume-command-row" aria-label="简历操作">
          <div class="resume-tool-group" aria-label="编辑与保存"><span class="resume-tool-label">编辑</span>
            <button id="undo" class="icon-button" title="上一步（⌘Z）" aria-label="上一步" disabled><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M3 10h10a8 8 0 0 1 8 8v2M3 10l6 6m-6-6 6-6"/></svg></button>
            <button id="redo" class="icon-button" title="下一步（⇧⌘Z）" aria-label="下一步" disabled><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M21 10H11a8 8 0 0 0-8 8v2m18-10-6 6m6-6-6-6"/></svg></button>
            <button id="saveDraft" class="primary" title="保存当前工作稿，不创建正式版本">保存草稿</button>
          </div>
          <div class="resume-tool-group" aria-label="AI 建议"><span class="resume-tool-label">AI</span>
            <button id="aiOptimize" title="根据当前岗位生成待确认的简历优化建议">优化当前稿</button>
            <button id="openAiProposals" title="查看已生成但尚未处理的简历建议" hidden>待处理建议</button>
          </div>
          <div class="resume-tool-group" aria-label="版本"><span class="resume-tool-label">版本</span>
            <button id="saveVersion" title="保存可编辑简历和 PDF 到本地历史版本"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M8 7H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3m-1 4-3 3m0 0-3-3m3 3V4"/></svg><span>保存版本</span></button>
            <button id="openVersions" title="查看、恢复或下载历史版本"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg><span>历史版本</span></button>
          </div>
          <div class="resume-tool-group" aria-label="PDF"><span class="resume-tool-label">PDF</span>
            <button id="previewPdf" title="在当前工作台预览真实文字 PDF">预览</button>
            <button id="exportPdf" title="仅导出当前 PDF，不创建历史版本">导出</button>
          </div>
          <div class="resume-tool-group resume-submission-group" aria-label="投递"><span class="resume-tool-label">投递</span>
            <button id="recordSubmitted">记录已投递</button>
          </div>
          <details class="resume-more-menu">
            <summary>更多</summary>
            <div class="resume-more-menu-panel">
              <button id="openMaterials" title="从 Wiki 选择事实导入当前工作稿">从 Wiki 选材</button>
              <button id="openSources" title="查看当前工作稿引用的材料来源">材料来源</button>
              <button id="exportMarkdown" title="导出当前简历为 Markdown">导出 MD</button>
              <button id="exportJson" title="导出结构化 JSON 备份">导出 JSON</button>
            </div>
          </details>
        </div>
      </header>
      <div id="versionRetry" class="version-retry" hidden><span id="versionRetryMessage"></span><button id="retryVersion">重试保存同一版本</button><button id="cancelVersion">关闭此次保存提示</button></div>
      <main class="resume-canvas"><section class="paper" id="paper" aria-label="A4 简历"></section></main>
      <dialog id="versionDialog"><form method="dialog" class="dialog-head"><div><h2>历史版本</h2><p>每个版本都包含可恢复的简历内容和可下载的 PDF。</p></div><button aria-label="关闭">关闭</button></form><div id="versionList" class="version-list"></div></dialog>
      <dialog id="restoreDialog" class="restore-dialog"><div class="dialog-head"><div><h2>恢复历史版本</h2><p id="restoreDialogMessage">当前内容如何处理？</p></div></div><div class="restore-actions"><button id="discardCurrent" class="danger" type="button">放弃当前内容并恢复</button><button id="saveCurrent" type="button">先保存当前内容</button><button id="cancelRestore" type="button">取消</button></div></dialog>
      <dialog id="materialsDialog" class="materials-dialog"><form method="dialog" class="dialog-head"><div><h2>从 Wiki 选材</h2><p>只导入你明确勾选的条目和分区；当前输入会先保存。</p></div><button aria-label="关闭">关闭</button></form><div class="materials-toolbar"><span id="materialsScope"></span><button id="reloadMaterials" type="button">重新读取</button></div><div id="materialsList" class="materials-list"><div class="empty-state">正在读取…</div></div><div class="materials-actions"><button id="cancelMaterials" type="button">取消</button><button id="importMaterials" class="primary" type="button">导入选中材料</button></div></dialog>
      <dialog id="sourcesDialog" class="sources-dialog"><form method="dialog" class="dialog-head"><div><h2>材料来源</h2><p>来源变化只提示，不会自动同步到当前稿。</p></div><button aria-label="关闭">关闭</button></form><div id="sourcesList" class="sources-list"><div class="empty-state">正在读取…</div></div></dialog>
      <div id="toast" class="toast" role="status" aria-live="polite"></div>
    </div>
  </section>`;
}

export async function mountResumeWorkspaceEditor(options: {
  documentId: string;
  legacy: boolean;
  submit: boolean;
}): Promise<ResumeEditorController> {
  const root = document.querySelector<HTMLElement>("[data-resume-editor-host]");
  if (!root) throw new Error("简历编辑区域不存在");
  const module = await import("./editor/legacy-app.js");
  return module.mountResumeEditor({...options, root, request: requestLocal}) as Promise<ResumeEditorController>;
}
