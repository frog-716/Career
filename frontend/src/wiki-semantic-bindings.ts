import { semanticWikiUI, sourceLabel } from "./wiki-semantic-ui";

type Obj = Record<string, any>;

const esc = (v: any) =>
  String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
      c
    ]!,
  );
const typeNames: Record<string, string> = {
  fact: "Fact", observation: "Observation", hypothesis: "Hypothesis",
};
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
  ];
}

function rawsFor(d: Obj) {
  return d.page === "projects"
    ? d.projectWiki?.raw || []
    : d.wikiSemantic?.raw || [];
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
    return `人物 · ${item?.name || "人物"}`;
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
    const html = `<form class="knowledge-form"><fieldset><label>标题<input name="title" required maxlength="500"></label><label>原始资料<textarea name="content" required maxlength="100000" placeholder="粘贴需要保留的虚构或真实原文"></textarea></label><p class="muted">保存后原文不会被 Wiki 修改。</p></fieldset><button class="primary full" type="submit">保存原文</button></form>`;
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
    const rawItems = rawsFor(d);
    const selectedRefs = item?.source_refs || [];
    const type = item?.knowledge_type || "fact";
    const html = `<form class="knowledge-form"><fieldset><label>类型<select name="knowledge_type">${Object.entries(typeNames).map(([key, label]) => `<option value="${key}" ${type === key ? "selected" : ""}>${label}</option>`).join("")}</select></label><label>内容<textarea name="content" required maxlength="100000">${esc(item?.content || "")}</textarea></label><label>Tags（每行一个，可自由填写）<textarea name="tags" maxlength="10000">${esc((item?.tags || []).join("\n"))}</textarea></label>${sourceChoices(rawItems, selectedRefs)}</fieldset><button class="primary full" type="submit">保存</button></form>`;
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
    if (status === "retired" && !window.confirm("退役后，这条知识不再出现在当前视图；修订历史会保留。")) return;
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
      const html = response.revisions.map((item: Obj) => {
        const refs = (item.source_refs || []).map((ref: Obj) =>
          `<p>${esc(sourceNames[ref.kind] || "原始来源")} · ${openRawButton(ref)}</p>`,
        ).join("");
        return `<section class="work-domain-card"><small>${esc(typeNames[item.knowledge_type] || item.knowledge_type)} · ${item.status === "retired" ? "已退役" : "当前"}</small><p class="preserve">${esc(item.content)}</p><div class="actions">${(item.tags || []).map((tag: string) => `<span class="pill">${esc(tag)}</span>`).join("")}</div>${refs || '<p class="muted">手工写入 · 未引用原文</p>'}</section>`;
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
}

function openRawButton(ref: Obj) {
  return `<button type="button" class="text-btn" data-d1-open-raw-kind="${esc(ref.kind)}" data-d1-open-raw-id="${esc(ref.id)}" data-d1-open-raw-revision="${esc(ref.revision)}" data-d1-open-raw-hash="${esc(ref.hash)}">查看来源 →</button>`;
}
