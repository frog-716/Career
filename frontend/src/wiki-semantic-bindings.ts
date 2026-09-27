import {
  knowledgeTypeLabel, knowledgeTypeLabels, semanticWikiUI, sourceLabel,
  wikiCompilerFrozenBefore, wikiCompilerPatchHTML, wikiCompilerPreviewHTML,
  wikiHistoryStatusLabel,
} from "./wiki-semantic-ui";

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
  return value.scope_type === "cognition" ? "跨经历认知" : "个人职业资料";
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
    semanticWikiUI.status = "all";
    if (typeof ctx.navigate === "function") void ctx.navigate("wiki").catch(ctx.failure);
  });
  change("#d1-wiki-scope", (value) => {
    semanticWikiUI.scope = value;
    semanticWikiUI.selected = "";
    void load().then(render).catch(ctx.failure);
  });
  change("#d1-wiki-status", (value) => {
    semanticWikiUI.status = value;
    semanticWikiUI.selected = "";
    void load().then(render).catch(ctx.failure);
  });
  on("[data-d1-select-wiki]", (el) => {
    semanticWikiUI.selected = el.dataset.d1SelectWiki || "";
    render();
  });

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
        `<h3>${esc(value.title)}</h3><p class="muted">${esc(scopeLabel(getData(), value))} · ${esc(sourceLabel(value))}</p><div class="prose preserve">${esc(value.content)}</div>`,
      );
    } catch (error) {
      ctx.failure(error);
    }
  }
  on("[data-d1-open-raw-kind]", (el) => void openRaw(el));

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

  function showRawForm(scope: Obj) {
    if (!scope) return;
    const destination = scopeLabel(getData(), scope);
    const html = `<p class="muted">保存到：${esc(destination)}</p><form class="knowledge-form"><fieldset><label>标题<input name="title" required maxlength="500"></label><label>原始资料<textarea name="content" required maxlength="100000" placeholder="粘贴需要保留的虚构或真实原文"></textarea></label><p class="muted">保存后原文不会被 Wiki 修改。</p></fieldset><button class="primary full" type="submit">保存原文</button></form>`;
    modal("添加原始资料", html, (dialog: HTMLDialogElement) => {
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
    });
  }
  on("[data-d1-add-raw]", (el) => {
    const scope = selectedScope(el);
    if (scope) showRawForm(scope);
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
    const html = `<form class="knowledge-form"><fieldset><label>类型<select name="knowledge_type">${Object.entries(knowledgeTypeLabels).map(([key, label]) => `<option value="${key}" ${type === key ? "selected" : ""}>${esc(label)}</option>`).join("")}</select></label><label>内容<textarea name="content" required maxlength="100000">${esc(item?.content || "")}</textarea></label><label>Tags（每行一个，可自由填写）<textarea name="tags" maxlength="10000">${esc((item?.tags || []).join("\n"))}</textarea></label>${sourceChoices(rawItems, selectedRefs)}</fieldset><button class="primary full" type="submit">保存</button></form>`;
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

  on("[data-d1-wiki-history]", (el) => void (async () => {
    try {
      const response = await api(`/wiki/${encodeURIComponent(el.dataset.d1WikiHistory || "")}/history`);
      const revisions = response.revisions || [];
      const html = revisions.map((item: Obj) => {
        const refs = (item.source_refs || []).map((ref: Obj) =>
          `<p>${esc(sourceNames[ref.kind] || "原始来源")} · ${openRawButton(ref)}</p>`,
        ).join("");
        return `<section class="work-domain-card"><small>${esc(knowledgeTypeLabel(item.knowledge_type))} · ${wikiHistoryStatusLabel(item, revisions)}</small><p class="preserve">${esc(item.content)}</p><div class="actions">${(item.tags || []).map((tag: string) => `<span class="pill">${esc(tag)}</span>`).join("")}</div>${refs || '<p class="muted">手工写入 · 未引用原文</p>'}</section>`;
      }).join("") || '<p class="muted">暂无修订记录。</p>';
      modal("Wiki 修订历史", html, (dialog: HTMLDialogElement) => {
        dialog.querySelectorAll<HTMLElement>("[data-d1-open-raw-kind]").forEach((button) => {
          button.onclick = () => void openRaw(button);
        });
      });
    } catch (error) {
      ctx.failure(error);
    }
  })());

  function finishCompilerReview(dialog: HTMLDialogElement, message = "") {
    dialog.close();
    if (message) ctx.inform?.(message);
    render();
  }

  function isPreparedRequestStale(error: unknown): boolean {
    return error instanceof Error && error.message.includes("prepared_request_stale");
  }

  function renderCompilerStale(dialog: HTMLDialogElement, rawId: string, targetScope?: Obj) {
    const flow = dialog.querySelector<HTMLElement>("[data-d2-flow]");
    if (!flow) return;
    flow.innerHTML = `<section class="notice"><b>资料在预览后发生了变化，请重新确认发送内容。</b><p><button type="button" class="primary" data-d2-repreview>重新预览</button></p></section>`;
    flow.querySelector<HTMLButtonElement>("[data-d2-repreview]")!.onclick = () => {
      dialog.close();
      void startCompiler(rawId, true, targetScope);
    };
  }

  function renderCompilerPreview(dialog: HTMLDialogElement, rawId: string, key: string, preview: Obj, targetScope?: Obj) {
    const flow = dialog.querySelector<HTMLElement>("[data-d2-flow]");
    if (!flow) return;
    dialog.classList.add("d2-preview-dialog");
    flow.innerHTML = wikiCompilerPreviewHTML(preview.readable_context, preview.preview_details);
    flow.querySelector<HTMLButtonElement>("[data-d2-cancel]")!.onclick = () => dialog.close();
    flow.querySelector<HTMLButtonElement>("[data-d2-confirm]")!.onclick = async (event) => {
      const button = event.currentTarget as HTMLButtonElement;
      button.disabled = true;
      try {
        const result = await api("/wiki/compiler/execute", {
          raw_id: rawId, idempotency_key: key,
          ...(targetScope ? { target_scope: targetScope } : {}),
          prepared_id: preview.prepared_id, payload_hash: preview.payload_hash,
          confirm_outbound: true,
        });
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
            ctx.inform?.("建议已保存，可以逐条处理；关闭后可从这份资料继续。");
            await renderCompilerPatch(dialog, result.proposal);
          } catch {
            flow.innerHTML = `<section class="notice"><b>建议已经生成并保存，但当前页面无法显示。</b><p>关闭后重新打开原始资料，可以继续检查这条建议。</p></section>`;
          }
          return;
        }
        flow.innerHTML = `<section class="notice"><b>${esc(result.message || "操作状态需要检查")}</b></section>`;
      } catch (error) {
        if (isPreparedRequestStale(error)) {
          renderCompilerStale(dialog, rawId, targetScope);
          return;
        }
        modalError(error);
        button.disabled = false;
      }
    };
  }

  async function renderCompilerPatch(dialog: HTMLDialogElement, proposal: Obj, editing = false) {
    const flow = dialog.querySelector<HTMLElement>("[data-d2-flow]");
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
    const scope = scopeLabel(getData(), { scope_type: patch.scope_type, scope_id: patch.scope_id });
    let beforeContent: string | undefined;
    if (patch.operation === "rewrite" || patch.operation === "retire") {
      try {
        const history = await api(`/wiki/${encodeURIComponent(patch.target_knowledge_id)}/history`);
        beforeContent = wikiCompilerFrozenBefore(patch, history.revisions || []);
      } catch {
        flow.innerHTML = `<section class="notice"><b>无法安全显示这条建议。</b><p>系统没有找到它对应的 Wiki 原始版本，没有写入任何内容。关闭后再打开仍可继续检查。</p></section>`;
        return;
      }
    }
    flow.innerHTML = `<p class="muted">建议 ${index + 1} / ${patches.length} · 已保存，关闭后可从这份资料继续处理</p>${wikiCompilerPatchHTML(patch, beforeContent, scope, editing)}`;
    flow.querySelectorAll<HTMLElement>("[data-d1-open-raw-kind]").forEach((button) => {
      button.onclick = () => void openRaw(button);
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
}

function openRawButton(ref: Obj) {
  return `<button type="button" class="text-btn" data-d1-open-raw-kind="${esc(ref.kind)}" data-d1-open-raw-id="${esc(ref.id)}" data-d1-open-raw-revision="${esc(ref.revision)}" data-d1-open-raw-hash="${esc(ref.hash)}">查看来源 →</button>`;
}
