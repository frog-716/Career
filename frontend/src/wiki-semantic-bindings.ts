import { beginAIProcessing, processingHTML, operationErrorHTML, previewExpired, isPreparationExpired, watchPreviewExpiry } from "./ai-activity";
import {
  proposalScopeLabel, knowledgeTypeLabel, knowledgeTypeLabels, semanticWikiUI, sourceLabel,
  cognitionExperiencePickerHTML, cognitionPreviewHTML, cognitionOutputErrorHTML,
  wikiCompilerFrozenBefore, wikiCompilerPatchHTML, wikiCompilerPreviewHTML,
  wikiReadingQuery,
} from "./wiki-semantic-ui";
import { feishuImportRequest, feishuPreviewHTML, feishuResultsHTML, readLocalTextFile } from "./feishu-source-ui";

type Obj = Record<string, any>;

const esc = (v: any) =>
  String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
      c
    ]!,
  );
const sourceNames: Record<string, string> = {
  raw_material: "手工原文", knowledge_source: "原始资料",
  work_project_source: "项目原文", work_event: "工作事件原文",
  work_evidence: "证据原文", journey_note: "任职 / 机会原文",
  interview_raw: "面试转写", communication: "沟通记录",
};
const sourceRefKey = (value: Obj) => {
  const ref = value.source_ref || value;
  return JSON.stringify([ref.kind, ref.id, ref.revision, ref.hash]);
};
const cognitionResultErrorCodes = new Set([
  "invalid_json", "truncated_result", "invalid_result", "empty_result", "invalid_envelope",
  "top_level_invalid", "patches_missing", "patch_wrong_type", "operation_invalid",
  "knowledge_type_invalid", "content_missing", "content_empty", "content_wrong_type",
  "source_experiences_missing", "source_experiences_insufficient", "source_experience_unknown",
  "source_wiki_invalid", "target_missing", "target_revision_mismatch", "extra_field",
  "content_policy_violation", "reason_missing", "reason_empty", "reason_wrong_type",
  "reason_invalid_length", "tag_wrong_type", "tag_empty", "tag_invalid_length", "tags_invalid",
  "content_invalid_length",
]);

function isCognitionResultError(error: unknown) {
  const code = (error as Obj | null)?.data?.code;
  return typeof code === "string" && cognitionResultErrorCodes.has(code);
}

function selectedScope(element: HTMLElement) {
  const type = element.dataset.d1ScopeType;
  if (type) return { scope_type: type, scope_id: element.dataset.d1ScopeId || "" };
  const key = semanticWikiUI.scope;
  if (key === "all") return null;
  const split = key.indexOf(":");
  return split < 0
    ? { scope_type: key, scope_id: "" }
    : { scope_type: key.slice(0, split), scope_id: key.slice(split + 1) };
}

function entriesFor(d: Obj) {
  return [
    ...(d.wikiSemantic?.items || []),
    ...(d.projectWiki?.knowledge || []),
    ...(d.projectWiki?.retired || []),
    ...(d.employmentWiki?.knowledge || []),
    ...(d.employmentWiki?.retired || []),
    ...(d.personWiki?.knowledge || []),
    ...(d.personWiki?.retired || []),
  ];
}

function rawsFor(d: Obj) {
  if (d.page === "projects") return d.projectWiki?.raw || [];
  if (d.page === "person") return d.personWiki?.raw || [];
  if (d.page === "work") return [
    ...(d.employmentWiki?.raw || []), ...(d.personWiki?.raw || []),
  ];
  return d.wikiSemantic?.raw || [];
}

function scopeLabel(d: Obj, value: Obj) {
  if (value.scope_type === "project") {
    const item = d.workDomain.projects?.find((x: Obj) => x.id === value.scope_id);
    return `项目 · ${item?.name || "项目"}`;
  }
  if (value.scope_type === "employment") {
    const item = d.workDomain.employments?.find((x: Obj) => x.id === value.scope_id);
    return `任职 · ${item ? `${item.company} / ${item.role}` : "任职"}`;
  }
  if (value.scope_type === "person") {
    const item = d.workDomain.persons?.find((x: Obj) => x.id === value.scope_id);
    const employment = d.workDomain.employments?.find((x: Obj) => x.id === item?.employment_id);
    return `人物 · ${item?.name || "人物"}${employment ? `（${employment.company}）` : ""}`;
  }
  if (value.scope_type === "opportunity") {
    const item = d.state.opportunities?.find((x: Obj) => x.id === value.scope_id);
    return `机会 · ${item ? `${item.company} / ${item.title}` : "机会"}`;
  }
  return value.scope_type === "cognition" ? "长期认知" : "个人职业资料";
}

export function bindWikiSemantic(ctx: Obj) {
  const { api, modal, modalError, render, load, getData } = ctx;
  const on = (selector: string, fn: (el: HTMLElement) => void) =>
    document.querySelectorAll<HTMLElement>(selector).forEach((el) => {
      el.onclick = () => fn(el);
    });
  const change = (selector: string, fn: (value: string) => void) =>
    document.querySelectorAll<HTMLSelectElement>(selector).forEach((el) => {
      el.onchange = () => fn(el.value);
    });

  on("[data-open-legacy-wiki]", () => {
    semanticWikiUI.legacyView = true;
    void load().then(render).catch(ctx.failure);
  });
  on("[data-open-semantic-wiki]", () => {
    semanticWikiUI.legacyView = false;
    void load().then(render).catch(ctx.failure);
  });
  on("[data-d3-open-wiki-scope-type]", (el) => {
    semanticWikiUI.legacyView = false;
    semanticWikiUI.scope = `${el.dataset.d3OpenWikiScopeType}:${el.dataset.d3OpenWikiScopeId || ""}`;
    semanticWikiUI.status = "current";
    semanticWikiUI.selected = "";
    semanticWikiUI.historyId = "";
    if (typeof ctx.navigate === "function") void ctx.navigate("wiki").catch(ctx.failure);
  });
  function readAt(changes: Obj, reload = true) {
    Object.assign(semanticWikiUI, changes);
    history.pushState(null, "", "#wiki?" + wikiReadingQuery());
    if (reload) void load().then(render).catch(ctx.failure);
    else render();
  }
  on("[data-wiki-browse]", (el) => {
    const browse = el.dataset.wikiBrowse || "recent";
    readAt({ browse, scope: browse === "cognition" ? "cognition" : "all", status: "current", selected: "", historyId: "" });
  });
  on("[data-wiki-object]", el => readAt({ scope: el.dataset.wikiObject || "all", selected: "", historyId: "" }));
  on("[data-wiki-personal]", () => readAt({ browse: "recent", scope: "personal", status: "current", selected: "", historyId: "" }));
  on("[data-wiki-back]", () => readAt({ selected: "", historyId: "" }, false));
  on("[data-wiki-history-back]", () => readAt({ historyId: "" }, false));
  change("#d1-wiki-scope", value => readAt({ scope: value, selected: "" }));
  change("#d1-wiki-status", value => readAt({ status: value, selected: "" }));
  on("[data-d1-select-wiki]", el => readAt({ selected: el.dataset.d1SelectWiki || "" }, false));

  async function openRaw(el: HTMLElement) {
    const kind = el.dataset.d1OpenRawKind || "";
    const id = el.dataset.d1OpenRawId || "";
    const revision = el.dataset.d1OpenRawRevision || "";
    const hash = el.dataset.d1OpenRawHash || "";
    if (!kind || !id || !revision || !hash) return;
    try {
      const params = new URLSearchParams({ revision, hash });
      const value = await api(`/raw/${encodeURIComponent(kind)}/${encodeURIComponent(id)}?${params}`);
      modal(
        "原始资料",
        `<article class="reading-surface reading-source"><h3>${esc(value.title)}</h3><p class="reading-meta">${esc(scopeLabel(getData(), value).replace(/^(项目|任职|人物) · /, ""))}</p><div class="reading-body preserve">${esc(value.content)}</div></article>`,
      );
    } catch (error) {
      ctx.failure(error);
    }
  }
  on("[data-d1-open-raw-kind]", (el) => void openRaw(el));

  async function openWikiSource(identifier: string, revision: number) {
    try {
      const response = await api(`/wiki/${encodeURIComponent(identifier)}/history`);
      const item = (response.revisions || []).find((value: Obj) => value.revision === revision);
      if (!item) throw new Error("找不到这段经历当时的 Wiki 版本，已停止显示。");
      const rawRefs = (item.source_refs || []).filter((ref: Obj) => ref.kind !== "wiki_knowledge");
      const html = `<article class="reading-surface"><h3>${esc(scopeLabel(getData(), item).replace(/^(项目|任职|人物) · /, ""))}</h3><p class="reading-kind">${esc(knowledgeTypeLabel(item.knowledge_type))}</p><div class="reading-body preserve">${esc(item.content)}</div><section class="reading-section"><h4>来源</h4>${rawRefs.length ? rawRefs.map((ref: Obj) => `<p>${openRawButton(ref)}</p>`).join("") : '<p class="reading-meta">由你记录，未关联资料。</p>'}</section></article>`;
      modal("支撑知识", html, (dialog: HTMLDialogElement) => {
        dialog.querySelectorAll<HTMLElement>("[data-d1-open-raw-kind]").forEach((button) => {
          button.onclick = () => void openRaw(button);
        });
      });
    } catch (error) {
      ctx.failure(error);
    }
  }
  on("[data-d4-open-wiki-source]", (el) => {
    void openWikiSource(el.dataset.d4OpenWikiSource || "", Number(el.dataset.d4SourceRevision || 0));
  });

  async function openCognitionSourceTree(identifier: string) {
    try {
      const response = await api(`/wiki/cognition/knowledge/${encodeURIComponent(identifier)}/sources`);
      const rows = (response.sources || []).map((trace: Obj) => {
        const knowledge = trace.wiki_knowledge || {};
        const raws = (trace.raw_sources || []).map((raw: Obj) =>
          `<li>${openRawButton(raw.source_ref, "打开原始资料 →")}</li>`,
        ).join("");
        const rawDetails = raws
          ? `<details class="d4-raw-sources"><summary>需要时查看原始资料 · ${Number(trace.raw_sources.length)} 条</summary><ul>${raws}</ul></details>`
          : '<p class="muted">这条经历 Wiki 没有关联原始资料。</p>';
        return `<section class="reading-surface reading-version"><button class="text-btn" data-d4-open-experience-type="${esc(trace.experience?.type)}" data-d4-open-experience-id="${esc(trace.experience?.id)}">支持经历：${esc(trace.experience?.name || "经历")}</button><p class="reading-kind">${esc(knowledgeTypeLabel(knowledge.type))}</p><div class="reading-body preserve">${esc(knowledge.content)}</div>${knowledge.version_changed ? '<p class="muted">这段经历 Wiki 后来已修改；这里仍显示当时被引用的版本。</p>' : ""}${rawDetails}</section>`;
      }).join("");
      modal("支持这个判断的经历", rows || '<p class="muted">暂时找不到可读取的经历来源。</p>', (dialog: HTMLDialogElement) => {
        dialog.querySelectorAll<HTMLElement>("[data-d1-open-raw-kind]").forEach((button) => {
          button.onclick = () => void openRaw(button);
        });
        dialog.querySelectorAll<HTMLElement>("[data-d4-open-experience-type]").forEach((button) => {
          button.onclick = () => void openExperience(button.dataset.d4OpenExperienceType || "", button.dataset.d4OpenExperienceId || "");
        });
      });
    } catch (error) {
      ctx.failure(error);
    }
  }
  on("[data-d4-open-source-tree]", (el) => void openCognitionSourceTree(el.dataset.d4OpenSourceTree || ""));

  async function openExperience(type: string, identifier: string) {
    const data = getData();
    if (type === "project") {
      if (typeof ctx.navigate === "function") await ctx.navigate("projects", identifier);
      return;
    }
    const employment = data.workDomain.employments?.find((item: Obj) => item.id === identifier);
    if (employment && typeof ctx.navigate === "function") {
      await ctx.navigate("work", employment.legacy_episode_id || identifier.replace(/^employment:/, ""));
    }
  }
  on("[data-d4-open-experience-type]", (el) => {
    void openExperience(el.dataset.d4OpenExperienceType || "", el.dataset.d4OpenExperienceId || "");
  });

  function showOperationError(flow: HTMLElement, error: unknown) {
    flow.innerHTML = operationErrorHTML(error);
    window.dispatchEvent(new Event("career-ai-activity-change"));
  }

  function renderExpiredPreview(dialog: HTMLDialogElement, repreview: () => void) {
    const flow = dialog.querySelector<HTMLElement>("[data-d2-flow], [data-d4-flow]");
    if (!flow) return;
    flow.innerHTML = '<section role="status"><p>预览已过期，尚未发送。</p><button type="button" class="primary" data-preview-again>重新预览</button></section>';
    flow.querySelector<HTMLButtonElement>('[data-preview-again]')!.onclick = () => { dialog.close(); repreview(); };
    window.dispatchEvent(new Event("career-ai-activity-change"));
  }

  async function startCognitionCompiler(selectedExperiences: Obj[]) {
    const key = crypto.randomUUID();
    const dialog = modal("整理长期认知", `<section data-d4-flow><p>正在准备所选经历中的 Wiki 信息…</p></section>`) as HTMLDialogElement;
    try {
      const preview = await api("/wiki/cognition/compiler/prepare", {
        selected_experiences: selectedExperiences, idempotency_key: key,
      });
      const flow = dialog.querySelector<HTMLElement>("[data-d4-flow]");
      if (!flow) return;
      dialog.classList.add("d2-preview-dialog");
      flow.innerHTML = cognitionPreviewHTML(preview.readable_context, preview.preview_details);
      const expire = () => renderExpiredPreview(dialog, () => { void startCognitionCompiler(selectedExperiences); });
      watchPreviewExpiry(dialog, preview.expires_at, expire);
      flow.querySelector<HTMLButtonElement>("[data-d4-cancel]")!.onclick = () => dialog.close();
      flow.querySelector<HTMLButtonElement>("[data-d4-confirm]")!.onclick = async (event: MouseEvent) => {
        const button = event.currentTarget as HTMLButtonElement;
        if (button.disabled) return;
        if (previewExpired(preview.expires_at)) { expire(); return; }
        button.disabled = true;
        try {
          const result = await beginAIProcessing<Obj>(() => { flow.innerHTML = processingHTML(); dialog.dataset.dirty = "false"; window.dispatchEvent(new Event("career-ai-activity-change")); }, () => api("/wiki/cognition/compiler/execute", {
            selected_experiences: preview.selected_experiences,
            idempotency_key: key,
            prepared_id: preview.prepared_id,
            payload_hash: preview.payload_hash,
            confirm_outbound: true,
          }));
          window.dispatchEvent(new Event("career-ai-activity-change"));
          if (result.status === "no_changes") {
            flow.innerHTML = `<section class="notice"><b>这些经历中暂时没有发现值得沉淀为长期认知的新模式。</b><p>没有写入任何长期认知。</p><button type="button" class="primary" data-d4-finish>完成</button></section>`;
            flow.querySelector<HTMLButtonElement>("[data-d4-finish]")!.onclick = () => {
              dialog.close();
              ctx.inform?.(result.message || "没有新增长期认知。");
              render();
            };
            return;
          }
          if (result.status === "proposal_pending" && result.proposal) {
            await load();
            render();
            await renderCompilerPatch(dialog, result.proposal);
            return;
          }
          flow.innerHTML = `<section class="notice"><b>${esc(result.message || "操作状态需要检查")}</b></section>`;
        } catch (error) {
          if (isPreparationExpired(error)) { expire(); return; }
          if (error instanceof Error && error.message.includes("prepared_request_stale")) {
            flow.innerHTML = `<section class="notice"><b>所选经历或 Wiki 信息在预览后发生了变化。</b><p>重新预览前不会发送。</p><button type="button" class="primary" data-d4-repreview>重新预览</button><button type="button" class="text-btn" data-d4-cancel>取消</button></section>`;
            flow.querySelector<HTMLButtonElement>("[data-d4-repreview]")!.onclick = () => {
              dialog.close();
              void startCognitionCompiler(selectedExperiences);
            };
            flow.querySelector<HTMLButtonElement>("[data-d4-cancel]")!.onclick = () => dialog.close();
            return;
          }
          if (isCognitionResultError(error)) {
            flow.innerHTML = cognitionOutputErrorHTML();
            flow.querySelector<HTMLButtonElement>("[data-d4-output-invalid]")!.onclick = () => dialog.close();
            return;
          }
          showOperationError(flow, error);
        }
      };
    } catch (error) {
      modalError(error);
    }
  }

  on("[data-d4-wiki-all]", () => {
    semanticWikiUI.scope = "all";
    semanticWikiUI.selected = "";
    void load().then(render).catch(ctx.failure);
  });

  on("[data-d4-start]", (el) => {
    const experiences = getData().wikiSemantic.cognition?.experiences || [];
    const preselected = el.dataset.d4PrefillType && el.dataset.d4PrefillId
      ? [{ type: el.dataset.d4PrefillType, id: el.dataset.d4PrefillId }]
      : [];
    const dialog = modal("整理长期认知", cognitionExperiencePickerHTML(experiences, preselected), (opened: HTMLDialogElement) => {
      opened.querySelector<HTMLButtonElement>("[data-d4-cancel]")!.onclick = () => opened.close();
      opened.querySelector<HTMLButtonElement>("[data-d4-prepare]")!.onclick = () => {
        const selected = [...opened.querySelectorAll<HTMLInputElement>("[data-d4-experience]:checked")]
          .map((input) => JSON.parse(decodeURIComponent(input.value)));
        const error = opened.querySelector<HTMLElement>("[data-d4-selection-error]")!;
        if (selected.length < 2) {
          error.textContent = "请至少选择两段不同的经历。";
          error.hidden = false;
          return;
        }
        if (selected.length > 20) {
          error.textContent = "最多选择20段不同的经历。";
          error.hidden = false;
          return;
        }
        opened.close();
        void startCognitionCompiler(selected);
      };
    });
    return dialog;
  });

  function sourceChoices(rawItems: Obj[], selectedRefs: Obj[]) {
    const selected = new Set(selectedRefs.map(sourceRefKey));
    const rows = rawItems.map((item: Obj) => ({
      ref: item.source_ref,
      title: item.title,
      label: sourceLabel(item),
    }));
    for (const ref of selectedRefs) {
      if (!rows.some((row) => sourceRefKey(row.ref || {}) === sourceRefKey(ref))) {
        rows.push({ ref, title: "原来源版本已变化（取消勾选可移除）", label: sourceNames[ref.kind] || "历史来源" });
      }
    }
    return `<fieldset class="wiki-source-choices"><legend>来源（可多选）</legend>${rows.map((row) => {
      const ref = row.ref || {};
      const key = sourceRefKey(ref);
      return `<label class="wiki-choice"><input type="checkbox" data-d1-source-choice value="${esc(encodeURIComponent(JSON.stringify(ref)))}" ${selected.has(key) ? "checked" : ""}><span>${esc(row.title)}<small>${esc(row.label)}</small></span></label>`;
    }).join("") || '<p class="muted">当前范围没有可引用的 Raw。可以不选来源，由用户直接写入 Wiki。</p>'}</fieldset>`;
  }

  function setMaterialPage(dialog: HTMLDialogElement, title: string, content: string) {
    const heading = dialog.querySelector<HTMLElement>(".modal-head h2");
    const outlet = dialog.querySelector<HTMLElement>("[data-material-flow]");
    const error = dialog.querySelector<HTMLElement>("#modal-error");
    if (heading) heading.textContent = title;
    if (outlet) outlet.innerHTML = content;
    if (error) { error.textContent = ""; error.hidden = true; }
    dialog.dataset.dirty = "false";
    delete dialog.dataset.untrackedDirty;
  }

  function showRawChoice(scope: Obj) {
    if (!scope) return;
    const dialog = modal("添加资料", '<div data-material-flow></div>');
    showRawChoiceInDialog(scope, dialog);
  }

  function showRawChoiceInDialog(scope: Obj, dialog: HTMLDialogElement) {
    if (!scope) return;
    const destination = scopeLabel(getData(), scope);
    setMaterialPage(dialog, "添加资料", `<p class="muted">保存到：${esc(destination)}</p><div class="feishu-material-choices"><button class="secondary" type="button" data-material-paste>粘贴文字</button><button class="secondary" type="button" data-material-local>本地资料</button><button class="secondary" type="button" data-material-feishu>从飞书选择</button></div>`);
    dialog.querySelector<HTMLElement>("[data-material-paste]")?.addEventListener("click", () => showRawFormInDialog(scope, dialog));
    dialog.querySelector<HTMLElement>("[data-material-local]")?.addEventListener("click", () => showLocalFile(scope, dialog));
    dialog.querySelector<HTMLElement>("[data-material-feishu]")?.addEventListener("click", () => showFeishuSearch(scope, dialog));
  }

  function showRawFormInDialog(
    scope: Obj, dialog: HTMLDialogElement,
    initial?: { title: string; content: string }, pageTitle = "粘贴文字",
  ) {
    if (!scope) return;
    const destination = scopeLabel(getData(), scope);
    const html = `<p class="muted">保存到：${esc(destination)}</p><form class="knowledge-form"><fieldset><label>标题<input name="title" required maxlength="500" value="${esc(initial?.title)}"></label><label>原始资料<textarea name="content" required maxlength="100000" placeholder="粘贴需要保留的原文">${esc(initial?.content)}</textarea></label><p class="muted">保存后原文不会被 Wiki 修改。</p></fieldset><button class="primary full" type="submit">保存原文</button><button class="text-btn" type="button" data-material-back>返回</button></form>`;
    setMaterialPage(dialog, pageTitle, html);
    if (initial?.content) dialog.dataset.dirty = "true";
    {
      const form = dialog.querySelector<HTMLFormElement>("form")!;
      const button = form.querySelector<HTMLButtonElement>("button[type=submit]")!;
      const fields = form.querySelector("fieldset")!;
      let request: Obj | null = null;
      let saved = false;
      form.onsubmit = async (event) => {
        event.preventDefault();
        if (button.disabled) return;
        if (!request) {
          const values = Object.fromEntries(new FormData(form).entries());
          request = { ...scope, ...values, source_kind: "manual_text", idempotency_key: crypto.randomUUID() };
        }
        button.disabled = true;
        fields.disabled = true;
        try {
          if (!saved) {
            await api("/raw", request);
            saved = true;
          }
          await load();
          dialog.close();
          render();
          ctx.inform?.(`原文已保存到${destination}。`);
        } catch (error) {
          modalError(saved ? new Error("原文已保存，页面未能更新；重试只重新读取。") : error);
          button.textContent = saved ? "重试刷新" : "重试同一保存";
          fields.disabled = saved;
        } finally {
          button.disabled = false;
        }
      };
      dialog.querySelector<HTMLElement>("[data-material-back]")?.addEventListener("click", () => {
        const values = new FormData(form);
        const hasInput = [...values.values()].some((value) => String(value).trim());
        if (hasInput && !window.confirm("放弃尚未保存的粘贴内容并返回？")) return;
        showRawChoiceInDialog(scope, dialog);
      });
    }
  }

  function showLocalFile(scope: Obj, dialog: HTMLDialogElement) {
    if (!scope) return;
    const html = `<p class="muted">只在本机读取 TXT 或 Markdown 文件；选择后可检查并编辑原文，再明确保存到当前范围。</p><form data-local-file-form><label>选择本地资料<input name="file" type="file" accept=".txt,.md,text/plain,text/markdown" required></label><button class="text-btn" type="button" data-material-back>返回</button></form>`;
    setMaterialPage(dialog, "本地资料", html);
    const form = dialog.querySelector<HTMLFormElement>("[data-local-file-form]")!;
    const input = form.querySelector<HTMLInputElement>('input[type="file"]')!;
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        const draft = await readLocalTextFile(file);
        showRawFormInDialog(scope, dialog, draft, "本地资料");
      } catch (error) {
        modalError(error);
      }
    });
    dialog.querySelector<HTMLElement>("[data-material-back]")?.addEventListener("click", () => showRawChoiceInDialog(scope, dialog));
  }

  function showFeishuSearch(scope: Obj, dialog: HTMLDialogElement, initialState?: Obj) {
    if (!scope) return;
    const destination = scopeLabel(getData(), scope);
    const state: Obj = initialState || { query: "", items: [], next_cursor: null };
    const page = () => {
      setMaterialPage(dialog, "飞书资料", `<p class="muted">保存到：${esc(destination)}</p><p class="muted">搜索可读文档；这里只显示标题和资料信息。</p><form data-feishu-search-form><label>搜索飞书文档<input name="query" required maxlength="30" value="${esc(state.query)}" placeholder="输入关键词"></label><button class="primary" type="submit">搜索</button></form><div class="feishu-resource-list" data-feishu-results></div><button class="text-btn" type="button" data-material-back>返回</button>`);
      const form = dialog.querySelector<HTMLFormElement>("[data-feishu-search-form]")!;
      const results = dialog.querySelector<HTMLElement>("[data-feishu-results]")!;
      const paint = () => {
        results.innerHTML = feishuResultsHTML(state.items || [], Boolean(state.next_cursor), Boolean(state.searched));
        results.querySelectorAll<HTMLElement>("[data-feishu-select]").forEach((button) => {
          button.onclick = () => { void showFeishuPreview(scope, dialog, button.dataset.feishuSelect!, state); };
        });
        results.querySelector<HTMLElement>("[data-feishu-more]")?.addEventListener("click", () => { void runSearch(state.query, state.next_cursor, true); });
      };
      const runSearch = async (query: string, cursor: string | null = null, append = false) => {
        const button = form.querySelector<HTMLButtonElement>("button[type=submit]")!;
        button.disabled = true;
        button.textContent = "正在搜索…";
        try {
          const response = await api("/feishu/search", cursor ? { cursor } : { query });
          state.query = query;
          state.searched = true;
          state.items = append ? [...(state.items || []), ...(response.items || [])] : (response.items || []);
          state.next_cursor = response.next_cursor || null;
          paint();
          dialog.dataset.dirty = "false";
        } catch (error) {
          modalError(error);
        } finally {
          button.disabled = false;
          button.textContent = "搜索";
        }
      };
      form.onsubmit = (event) => {
        event.preventDefault();
        const query = String(new FormData(form).get("query") || "").trim();
        void runSearch(query);
      };
      form.querySelector<HTMLInputElement>('[name="query"]')?.addEventListener("input", () => { dialog.dataset.dirty = "false"; });
      dialog.querySelector<HTMLElement>("[data-material-back]")?.addEventListener("click", () => showRawChoiceInDialog(scope, dialog));
      paint();
    };
    page();
  }

  async function showFeishuPreview(scope: Obj, dialog: HTMLDialogElement, selectionId: string, searchState: Obj) {
    setMaterialPage(dialog, "飞书资料", '<p class="muted">正在读取你选择的文档…</p>');
    let snapshot: Obj;
    try {
      snapshot = await api(`/feishu/resources/${encodeURIComponent(selectionId)}/preview`, {});
    } catch (error) {
      setMaterialPage(dialog, "飞书资料", `<p class="muted">无法读取这份资料。</p><button class="secondary" type="button" data-feishu-back>返回搜索结果</button>`);
      modalError(error);
      dialog.querySelector<HTMLElement>("[data-feishu-back]")?.addEventListener("click", () => showFeishuSearch(scope, dialog, searchState));
      return;
    }
    setMaterialPage(dialog, "预览飞书资料", feishuPreviewHTML(snapshot));
    let request: Obj | null = null;
    let saved = false;
    const button = dialog.querySelector<HTMLButtonElement>("[data-feishu-import]")!;
    button.onclick = async () => {
      if (button.disabled) return;
      if (!request) request = feishuImportRequest(snapshot.preview_id, scope, crypto.randomUUID());
      button.disabled = true;
      try {
        if (!saved) {
          await api("/feishu/import", request);
          saved = true;
        }
        await load();
        dialog.close();
        render();
        ctx.inform?.(`飞书资料已导入到${scopeLabel(getData(), scope)}。`);
      } catch (error) {
        modalError(saved ? new Error("资料已导入，页面未能更新；重试只重新读取。") : error);
        button.textContent = saved ? "重试刷新" : "重试导入";
      } finally {
        button.disabled = false;
      }
    };
    dialog.querySelector<HTMLElement>("[data-feishu-back]")?.addEventListener("click", () => showFeishuSearch(scope, dialog, searchState));
  }
  on("[data-d1-add-raw]", (el) => {
    const scope = selectedScope(el);
    if (scope) showRawChoice(scope);
  });

  function showKnowledgeForm(item?: Obj, explicitScope?: Obj) {
    const d = getData();
    const scope = explicitScope || (item
      ? { scope_type: item.scope_type, scope_id: item.scope_id }
      : selectedScope(document.querySelector<HTMLElement>("[data-d1-add-wiki]") || document.body));
    if (!scope) return;
    const rawItems = rawsFor(d).filter((raw: Obj) =>
      raw.scope_type === scope.scope_type && raw.scope_id === scope.scope_id,
    );
    const selectedRefs = item?.source_refs || [];
    const type = item?.knowledge_type || "fact";
    const html = `<form class="knowledge-form"><fieldset><label>类型<select name="knowledge_type">${Object.entries(knowledgeTypeLabels).map(([key, label]) => `<option value="${key}" ${type === key ? "selected" : ""}>${esc(label)}</option>`).join("")}</select></label><label>内容<textarea name="content" required maxlength="100000">${esc(item?.content || "")}</textarea></label><label>标签（每行一个）<textarea name="tags" maxlength="10000">${esc((item?.tags || []).join("\n"))}</textarea></label>${sourceChoices(rawItems, selectedRefs)}</fieldset><button class="primary full" type="submit">保存</button></form>`;
    modal(item ? "编辑 Wiki 知识" : "写入 Wiki", html, (dialog: HTMLDialogElement) => {
      const form = dialog.querySelector<HTMLFormElement>("form")!;
      const button = form.querySelector<HTMLButtonElement>("button[type=submit]")!;
      const fields = form.querySelector("fieldset")!;
      let request: Obj | null = null;
      let saved = false;
      form.onsubmit = async (event) => {
        event.preventDefault();
        if (button.disabled) return;
        if (!request) {
          const values = Object.fromEntries(new FormData(form).entries());
          const refs = [...form.querySelectorAll<HTMLInputElement>("[data-d1-source-choice]:checked")]
            .map((input) => JSON.parse(decodeURIComponent(input.value)));
          request = {
            knowledge_type: values.knowledge_type,
            content: values.content,
            tags: String(values.tags || "").split(/\r?\n/).map((x) => x.trim()).filter(Boolean),
            source_refs: refs,
            idempotency_key: crypto.randomUUID(),
          };
          if (item) {
            request.expected_revision = item.revision;
            request.status = item.status;
          } else {
            Object.assign(request, scope);
          }
        }
        button.disabled = true;
        fields.disabled = true;
        try {
          if (!saved) {
            await api(item ? `/wiki/${encodeURIComponent(item.id)}` : "/wiki", request);
            saved = true;
          }
          await load();
          dialog.close();
          render();
        } catch (error) {
          modalError(saved ? new Error("Wiki 已保存，页面未能更新；重试只重新读取。") : error);
          button.textContent = saved ? "重试刷新" : "重试同一保存";
          fields.disabled = saved;
        } finally {
          button.disabled = false;
        }
      };
    });
  }
  on("[data-d1-add-wiki]", (el) => showKnowledgeForm(undefined, selectedScope(el) || undefined));
  on("[data-d1-edit-wiki]", (el) => {
    const item = entriesFor(getData()).find((x: Obj) => x.id === el.dataset.d1EditWiki);
    if (item) showKnowledgeForm(item);
  });

  async function changeStatus(el: HTMLElement, status: "current" | "retired") {
    const item = entriesFor(getData()).find((x: Obj) => x.id === el.dataset.d1RetireWiki || x.id === el.dataset.d1ReviveWiki);
    if (!item) return;
    if (status === "retired" && !window.confirm("标记后，这条知识不再出现在当前理解中；历史和来源仍会保留。")) return;
    try {
      await api(`/wiki/${encodeURIComponent(item.id)}`, {
        knowledge_type: item.knowledge_type,
        content: item.content,
        tags: item.tags || [],
        source_refs: item.source_refs || [],
        status,
        expected_revision: item.revision,
        idempotency_key: crypto.randomUUID(),
      });
      await load();
      render();
    } catch (error) {
      ctx.failure(error);
    }
  }
  on("[data-d1-retire-wiki]", (el) => void changeStatus(el, "retired"));
  on("[data-d1-revive-wiki]", (el) => void changeStatus(el, "current"));

  on("[data-d1-wiki-history]", (el) => readAt({
    historyId: el.dataset.d1WikiHistory || "",
    selected: el.dataset.d1WikiHistory || "",
  }));

  function finishCompilerReview(dialog: HTMLDialogElement, message = "") {
    dialog.close();
    if (message) ctx.inform?.(message);
    render();
  }

  async function cognitionSupportingExperiences(proposal: Obj, patch: Obj) {
    const saved = patch.supporting_experiences;
    if (Array.isArray(saved) && saved.length) {
      return saved.map((item: Obj) => ({
        ...item,
        label: item.type === "project" ? `项目 · ${item.name}` : `任职 · ${item.name}`,
      }));
    }
    const selected = proposal.selected_experiences || [];
    const workspace = getData().wikiSemantic?.cognition?.experiences
      || (await api("/wiki/cognition/experiences")).experiences || [];
    const resolved = new Map<string, Obj>();
    for (const ref of patch.source_refs || []) {
      if (ref.kind !== "wiki_knowledge") continue;
      const history = await api(`/wiki/${encodeURIComponent(ref.id)}/history`);
      const source = (history.revisions || []).find((item: Obj) => item.revision === ref.revision);
      if (!source) continue;
      const selectedExperience = selected.find((item: Obj) =>
        item.type === source.scope_type && item.id === source.scope_id,
      );
      if (!selectedExperience) continue;
      const experience = workspace.find((item: Obj) =>
        item.type === selectedExperience.type && item.id === selectedExperience.id,
      );
      if (!experience) continue;
      const label = experience.type === "project"
        ? `项目 · ${experience.name}` : `任职 · ${experience.name}`;
      resolved.set(`${experience.type}:${experience.id}`, { ...experience, label });
    }
    return [...resolved.values()];
  }

  function isPreparedRequestStale(error: unknown): boolean {
    return error instanceof Error && error.message.includes("prepared_request_stale");
  }

  function renderCompilerStale(dialog: HTMLDialogElement, rawId: string, targetScope?: Obj) {
    const flow = dialog.querySelector<HTMLElement>("[data-d2-flow], [data-d4-flow]");
    if (!flow) return;
    flow.innerHTML = `<section class="notice"><b>资料在预览后发生了变化，请重新确认发送内容。</b><p><button type="button" class="primary" data-d2-repreview>重新预览</button></p></section>`;
    flow.querySelector<HTMLButtonElement>("[data-d2-repreview]")!.onclick = () => {
      dialog.close();
      void startCompiler(rawId, true, targetScope);
    };
  }

  function renderCompilerPreview(dialog: HTMLDialogElement, rawId: string, key: string, preview: Obj, targetScope?: Obj) {
    const flow = dialog.querySelector<HTMLElement>("[data-d2-flow], [data-d4-flow]");
    if (!flow) return;
    dialog.classList.add("d2-preview-dialog");
    flow.innerHTML = wikiCompilerPreviewHTML(preview.readable_context, preview.preview_details);
    const expire = () => renderExpiredPreview(dialog, () => { void startCompiler(rawId, true, targetScope); });
    watchPreviewExpiry(dialog, preview.expires_at, expire);
    flow.querySelector<HTMLButtonElement>("[data-d2-cancel]")!.onclick = () => dialog.close();
    flow.querySelector<HTMLButtonElement>("[data-d2-confirm]")!.onclick = async (event) => {
      const button = event.currentTarget as HTMLButtonElement;
      if (button.disabled) return;
      if (previewExpired(preview.expires_at)) { expire(); return; }
      button.disabled = true;
      try {
        const result = await beginAIProcessing<Obj>(() => { flow.innerHTML = processingHTML(); dialog.dataset.dirty = "false"; window.dispatchEvent(new Event("career-ai-activity-change")); }, () => api("/wiki/compiler/execute", {
          raw_id: rawId, idempotency_key: key,
          ...(targetScope ? { target_scope: targetScope } : {}),
          prepared_id: preview.prepared_id, payload_hash: preview.payload_hash,
          confirm_outbound: true,
        }));
        window.dispatchEvent(new Event("career-ai-activity-change"));
        if (result.status === "no_changes") {
          flow.innerHTML = `<section class="notice"><b>这份资料没有发现值得更新到 Wiki 的长期知识。</b><p>没有写入任何 Wiki。</p><button type="button" class="primary" data-d2-finish>完成</button></section>`;
          flow.querySelector<HTMLButtonElement>("[data-d2-finish]")!.onclick = () =>
            finishCompilerReview(dialog, result.message || "这份资料没有发现值得更新到 Wiki 的长期知识。");
          return;
        }
        if (result.status === "proposal_pending" && result.proposal) {
          try {
            await load();
            render();
            ctx.inform?.("AI 建议已保存，可从右上角 AI 继续处理。");
            await renderCompilerPatch(dialog, result.proposal);
          } catch {
            flow.innerHTML = `<section class="notice"><b>建议已经生成并保存，但当前页面无法显示。</b><p>关闭后重新打开原始资料，可以继续检查这条建议。</p></section>`;
          }
          return;
        }
        flow.innerHTML = `<section class="notice"><b>${esc(result.message || "操作状态需要检查")}</b></section>`;
      } catch (error) {
        if (isPreparationExpired(error)) { expire(); return; }
        if (isPreparedRequestStale(error)) {
          renderCompilerStale(dialog, rawId, targetScope);
          return;
        }
        showOperationError(flow, error);
      }
    };
  }

  async function renderCompilerPatch(dialog: HTMLDialogElement, proposal: Obj, editing = false) {
    const flow = dialog.querySelector<HTMLElement>("[data-d2-flow], [data-d4-flow]");
    if (!flow) return;
    const errorBox = dialog.querySelector<HTMLElement>("#modal-error");
    if (errorBox) { errorBox.hidden = true; errorBox.textContent = ""; }
    const patches = proposal.patches || [];
    const index = patches.findIndex((item: Obj) => item.status === "pending");
    if (index < 0) {
      const accepted = patches.some((item: Obj) => item.status === "accepted");
      flow.innerHTML = `<section class="notice"><b>这组 Wiki 建议已经逐条处理完。</b><p>已处理 ${patches.length} 条；每次操作只处理一条。</p><button type="button" class="primary" data-d2-finish>完成</button></section>`;
      flow.querySelector<HTMLButtonElement>("[data-d2-finish]")!.onclick = () =>
        finishCompilerReview(dialog, accepted ? "当前理解已更新，原文仍保留。" : "建议已处理，Wiki 没有变化。");
      return;
    }
    const patch = patches[index];
    const scope = proposalScopeLabel(proposal, patch, scopeLabel(getData(), { scope_type: patch.scope_type, scope_id: patch.scope_id }));
    let beforeContent: string | undefined;
    let targetKnowledgeType = "";
    if (patch.operation === "rewrite" || patch.operation === "retire") {
      try {
        const history = await api(`/wiki/${encodeURIComponent(patch.target_knowledge_id)}/history`);
        beforeContent = wikiCompilerFrozenBefore(patch, history.revisions || []);
        targetKnowledgeType = (history.revisions || []).find(
          (item: Obj) => item.revision === patch.before_revision,
        )?.knowledge_type || "";
      } catch {
        flow.innerHTML = `<section class="notice"><b>无法安全显示这条建议。</b><p>系统没有找到它对应的 Wiki 原始版本，没有写入任何内容。关闭后再打开仍可继续检查。</p></section>`;
        return;
      }
    }
    const isCognition = proposal.context_kind === "cognition";
    let supportingExperiences: Obj[] = [];
    if (isCognition) {
      try {
        supportingExperiences = await cognitionSupportingExperiences(proposal, patch);
      } catch {
        flow.innerHTML = `<section class="notice"><b>暂时无法安全显示这条建议的支撑经历。</b><p>没有写入任何长期认知，请稍后从待处理建议重新打开。</p></section>`;
        return;
      }
      if (!supportingExperiences.length) {
        flow.innerHTML = `<section class="notice"><b>无法核对这条建议来自哪些经历。</b><p>没有写入任何长期认知，因此暂不显示审批操作。</p></section>`;
        return;
      }
    }
    const displayPatch = isCognition && !patch.knowledge_type && targetKnowledgeType
      ? { ...patch, knowledge_type: targetKnowledgeType }
      : patch;
    const patchHTML = wikiCompilerPatchHTML(
      displayPatch, beforeContent, scope, editing,
      isCognition ? { cognition: true, supportingExperiences } : {},
    );
    flow.innerHTML = isCognition
      ? `<h3>发现 ${patches.length} 条长期认知</h3><p class="muted">第 ${index + 1} / ${patches.length} 条</p>${patchHTML}`
      : `<p class="muted">建议 ${index + 1} / ${patches.length} · 已保存，关闭后可从这份资料继续处理</p>${patchHTML}`;
    flow.querySelectorAll<HTMLElement>("[data-d1-open-raw-kind]").forEach((button) => {
      button.onclick = () => void openRaw(button);
    });
    flow.querySelectorAll<HTMLElement>("[data-d4-open-wiki-source]").forEach((button) => {
      button.onclick = () => void openWikiSource(
        button.dataset.d4OpenWikiSource || "", Number(button.dataset.d4SourceRevision || 0),
      );
    });
    let idempotencyKey = "";
    const decide = async (decision: string, editedValue?: string) => {
      const buttons = [...flow.querySelectorAll<HTMLButtonElement>("button")];
      buttons.forEach((button) => { button.disabled = true; });
      if (!idempotencyKey) idempotencyKey = crypto.randomUUID();
      const body: Obj = { decision, idempotency_key: idempotencyKey };
      if (decision === "edit_accept") body[patch.operation === "retire" ? "reason" : "content"] = editedValue;
      try {
        const result = await api(`/wiki/compiler/proposals/${encodeURIComponent(proposal.id)}/patches/${encodeURIComponent(patch.id)}/resolve`, body);
        await load();
        await renderCompilerPatch(dialog, result.proposal);
        window.dispatchEvent(new Event("career-ai-activity-change"));
        dialog.dataset.dirty = "false";
      } catch (error) {
        modalError(error);
        buttons.forEach((button) => { button.disabled = false; });
      }
    };
    const acceptButton = flow.querySelector<HTMLButtonElement>("[data-d2-accept]");
    if (acceptButton) acceptButton.onclick = () => void decide("accept");
    const editAcceptButton = flow.querySelector<HTMLButtonElement>("[data-d2-edit-accept]");
    if (editAcceptButton) editAcceptButton.onclick = () => void renderCompilerPatch(dialog, proposal, true);
    const confirmEditButton = flow.querySelector<HTMLButtonElement>("[data-d2-confirm-edit]");
    if (confirmEditButton) confirmEditButton.onclick = () => {
      const value = flow.querySelector<HTMLTextAreaElement>("[data-d2-edit-value]")?.value || "";
      void decide("edit_accept", value);
    };
    const cancelEditButton = flow.querySelector<HTMLButtonElement>("[data-d2-cancel-edit]");
    if (cancelEditButton) cancelEditButton.onclick = async () => {
      await renderCompilerPatch(dialog, proposal, false);
      dialog.dataset.dirty = "false";
    };
    flow.querySelector<HTMLButtonElement>("[data-d2-reject]")!.onclick = () => void decide("reject");
  }

  async function startCompiler(rawId: string, freshPreview = false, targetScope?: Obj) {
    if (!rawId) return;
    const key = crypto.randomUUID();
    const dialog = modal("整理到 Wiki", `<section data-d2-flow><p>正在准备可检查的内容…</p></section>`);
    try {
      if (!freshPreview) {
        const existing = await api(`/wiki/compiler/proposals?raw_id=${encodeURIComponent(rawId)}`);
        const pending = (existing.proposals || []).find((proposal: Obj) => {
          if (proposal.status !== "pending") return false;
          if (!targetScope) return !proposal.target_scope;
          const candidate = proposal.target_scope || (proposal.scopes?.length === 1 ? {
            scope_type: proposal.scopes[0].type, scope_id: proposal.scopes[0].stable_id,
          } : null);
          return candidate?.scope_type === targetScope.scope_type
            && candidate?.scope_id === targetScope.scope_id;
        });
        if (pending) {
          await renderCompilerPatch(dialog, pending);
          return;
        }
      }
      const preview = await api("/wiki/compiler/prepare", {
        raw_id: rawId, idempotency_key: key,
        ...(targetScope ? { target_scope: targetScope } : {}),
      });
      renderCompilerPreview(dialog, rawId, key, preview, targetScope);
    } catch (error) {
      modalError(error);
    }
  }
  on("[data-d2-compile]", (el) => {
    const targetScope = el.dataset.d2TargetScopeType && el.dataset.d2TargetScopeId !== undefined
      ? { scope_type: el.dataset.d2TargetScopeType, scope_id: el.dataset.d2TargetScopeId }
      : undefined;
    void startCompiler(el.dataset.d2Compile || "", false, targetScope);
  });

  async function openProposal(id: string) {
    try {
      const proposal = await api(`/wiki/compiler/proposals/${encodeURIComponent(id)}`);
      const dialog = modal(proposal.context_kind === "cognition" ? "长期认知建议" : "Wiki 建议", `<section data-d2-flow></section>`);
      if (proposal.status !== "pending") {
        dialog.querySelector("[data-d2-flow]")!.textContent = "这组建议已结束，没有待处理内容。";
        return;
      }
      await renderCompilerPatch(dialog, proposal);
    } catch (error) { ctx.failure(error); }
  }
  on("[data-d4-resume-proposal]", el => void openProposal(el.dataset.d4ResumeProposal || ""));
  on("[data-ai-resume-proposal]", el => void openProposal(el.dataset.aiResumeProposal || ""));
  return { openProposal };
}

function openRawButton(ref: Obj, label = "查看来源 →") {
  return `<button type="button" class="text-btn" data-d1-open-raw-kind="${esc(ref.kind)}" data-d1-open-raw-id="${esc(ref.id)}" data-d1-open-raw-revision="${esc(ref.revision)}" data-d1-open-raw-hash="${esc(ref.hash)}">${esc(label)}</button>`;
}
