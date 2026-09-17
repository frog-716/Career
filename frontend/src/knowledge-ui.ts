type Obj = Record<string, any>;
const resolutions = new Map<
  string,
  { request: Obj; result?: Obj; busy: boolean }
>();
export const knowledgeUI = {
  tab: "sources",
  selected: "",
  scope: "all",
  category: "all",
};
export const entryNames: Obj = {
  goal: "职业目标",
  constraint: "偏好与约束",
  experience: "经历",
  capability: "能力",
  project: "项目",
  achievement: "成果",
  person: "协作人物",
  growth: "成长",
  strategy: "求职策略",
};
const sourceNames: Obj = {
  text: "手工文本",
  document: "文档摘录",
  local_repository: "本地项目",
  git_repository: "Git 仓库",
  url: "网页来源",
};
const objectNames: Obj = {
  company: "公司",
  org_unit: "组织 / 团队",
  target_role: "目标方向",
  search_cycle: "求职周期",
};
const esc = (v: any) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
const scopeKey = (o: Obj) =>
  o.scope_type === "personal" ? "personal" : o.scope_type + ":" + o.scope_id;
function scopeOptions(d: Obj, selected: string, all = false) {
  return `${all ? '<option value="all">全部范围</option>' : ""}<option value="personal" ${selected === "personal" ? "selected" : ""}>个人职业资料</option>${d.state.jobs.map((j: Obj) => `<option value="job:${esc(j.id)}" ${selected === "job:" + j.id ? "selected" : ""}>机会 · ${esc(j.company)} / ${esc(j.title)}</option>`).join("")}${d.journey.episodes.map((x: Obj) => `<option value="episode:${esc(x.id)}" ${selected === "episode:" + x.id ? "selected" : ""}>任职 · ${esc(x.company)} / ${esc(x.role)}</option>`).join("")}`;
}
function scopeLabel(d: Obj, o: Obj) {
  if (o.scope_type === "personal") return "个人";
  const x = (o.scope_type === "job" ? d.state.jobs : d.journey.episodes).find(
    (x: Obj) => x.id === o.scope_id,
  );
  return `${o.scope_type === "job" ? "机会" : "任职"} · ${x?.company || "未知范围"}`;
}
function typeOptions(value: string) {
  return Object.entries(entryNames)
    .map(
      ([k, v]) =>
        `<option value="${k}" ${k === value ? "selected" : ""}>${v}</option>`,
    )
    .join("");
}
export function knowledgeView(d: Obj, profileHtml: () => string) {
  const k = d.knowledge,
    u = knowledgeUI;
  if (u.tab === "profile")
    return `<section class="materials">${wikiTabs()}${profileHtml()}</section>`;
  const rows = (
    u.tab === "sources"
      ? k.sources
      : u.tab === "candidates"
        ? k.candidates
        : k.entries
  ).filter(
    (x: Obj) =>
      (u.scope === "all" || scopeKey(x) === u.scope) &&
      (u.category === "all" || x.entry_type === u.category),
  );
  const selected = rows.find((x: Obj) => x.id === u.selected) || rows[0];
  const status = (x: Obj) =>
    x.status === "pending"
      ? "待确认"
      : x.status === "confirmed"
        ? "已确认"
        : x.status === "rejected"
          ? "已拒绝"
          : x.status === "withdrawn"
            ? "已撤回"
            : "当前有效";
  return `<section class="materials">${wikiTabs()}<div class="pane-heading"><div class="actions"><select aria-label="资料范围" id="wiki-scope">${scopeOptions(d, u.scope, true)}</select>${u.tab === "sources" ? "" : `<select aria-label="资料类别" id="wiki-category"><option value="all">所有类别</option>${typeOptions(u.category)}</select>`}</div><button class="primary" data-source-add>添加原始资料</button></div><div class="records wiki-records"><div class="record-list scroll">${rows.map((x: Obj) => `<button class="record-row ${selected?.id === x.id ? "selected" : ""}" data-wiki-select="${esc(x.id)}"><span>${esc(x.title)}</span><small>${esc(scopeLabel(d, x))} · ${u.tab === "sources" ? esc(sourceNames[x.source_type]) : esc(status(x))}</small></button>`).join("") || '<div class="empty">暂无内容</div>'}</div><article class="reading scroll">${selected ? `<div class="pane-heading"><h2>${esc(u.tab === "sources" ? "原始资料" : entryNames[selected.entry_type])}</h2><div class="actions">${u.tab === "sources" ? `<button class="primary" data-candidate-new="${esc(selected.id)}">整理为待确认内容</button>` : u.tab === "candidates" && selected.status === "pending" ? `<button class="secondary" data-candidate-edit="${esc(selected.id)}">修正</button><button class="primary" data-candidate-confirm="${esc(selected.id)}">确认入 Wiki</button><button class="quiet" data-candidate-reject="${esc(selected.id)}">拒绝</button>` : u.tab === "entries" ? `<button class="secondary" data-entry-edit="${esc(selected.id)}">编辑</button><button class="quiet" data-entry-history="${esc(selected.id)}">历史</button>` : ""}</div></div><h3>${esc(selected.title)}</h3><small>${esc(scopeLabel(d, selected))}${selected.revision ? " · v" + selected.revision : ""}${selected.status ? " · " + status(selected) : " · 原件保留"}</small>${selected.origin?.kind === "journey_note" ? `<p class="source-locator">选段来源：记录 ${selected.origin.revision ? `更正视图 v${selected.origin.revision}` : "原文"} <button class="text-btn" data-origin-record="${esc(selected.origin.id)}">查看记录与历史 →</button></p>` : selected.origin?.kind === "profile" ? `<p class="muted">来源：整理前的个人资料 v${esc(selected.origin.revision)}</p>` : ""}${selected.locator && !selected.origin ? `<p class="source-locator">${esc(selected.locator)}<small>仅登记来源位置，未读取仓库或网页。</small></p>` : ""}<div class="prose">${esc(selected.content)}</div>${selected.source_ids?.length ? `<div class="source-links"><small>原始依据</small>${selected.source_ids.map((id: string) => `<button class="text-btn" data-source-open="${esc(id)}">${esc(k.sources.find((s: Obj) => s.id === id)?.title || "来源缺失")}</button>`).join("")}</div>` : ""}${selected.entry_id ? `<button class="text-btn" data-entry-open="${esc(selected.entry_id)}">查看已确认条目 →</button>` : ""}` : '<div class="empty">从一份原始资料开始，整理后再确认进 Wiki。</div>'}</article></div></section>`;
}
function wikiTabs() {
  return `<div class="tabs" role="tablist">${[
    ["sources", "原始资料"],
    ["candidates", "待确认"],
    ["entries", "已确认 Wiki"],
    ["profile", "基础资料"],
  ]
    .map(
      ([k, v]) =>
        `<button role="tab" aria-selected="${knowledgeUI.tab === k}" data-wiki-tab="${k}">${v}</button>`,
    )
    .join("")}</div>`;
}
export function directoryView(d: Obj) {
  const os = d.domain.objects as Obj[];
  return `<section class="full-panel"><div class="pane-heading"><h2>业务对象</h2><div class="actions">${Object.entries(
    objectNames,
  )
    .map(
      ([k, v]) =>
        `<button class="secondary" data-object-new="${k}">＋${v}</button>`,
    )
    .join("")}</div></div><div class="scroll panel-body">${Object.entries(
    objectNames,
  )
    .map(
      ([kind, label]) =>
        `<section class="directory-group"><h3>${label}</h3>${
          os
            .filter((x) => x.kind === kind)
            .map(
              (x) =>
                `<button class="directory-row" data-object-edit="${esc(x.id)}"><span><b>${esc(x.name)}</b><small>${kind === "org_unit" ? esc(orgPath(os, x.id)) : esc(x.description || "")} · v${x.revision}</small></span><span>编辑</span></button>`,
            )
            .join("") || '<p class="muted">尚未建立</p>'
        }</section>`,
    )
    .join("")}</div></section>`;
}
export function orgPath(os: Obj[], id: string) {
  const names = [];
  let x = os.find((o) => o.id === id),
    seen = new Set();
  while (x && !seen.has(x.id)) {
    seen.add(x.id);
    names.unshift(x.name);
    const parentId = x.parent_id || x.company_id;
    x = os.find((o) => o.id === parentId);
  }
  return names.join(" / ");
}
export function opportunityObjects(d: Obj, jobId: string) {
  const b = d.domain.opportunities.find((o: Obj) => o.job_id === jobId) || {},
    os = d.domain.objects;
  return `<div class="object-context"><span>${esc(os.find((o: Obj) => o.id === b.search_cycle_id)?.name || "未分求职周期")}</span><span>${esc(os.find((o: Obj) => o.id === b.target_role_id)?.name || "未定目标方向")}</span><span>${esc(orgPath(os, b.org_unit_id || b.company_id) || "公司 / 团队待补充")}</span><button class="text-btn" id="opportunity-objects">编辑关联</button><button class="text-btn" data-page="directory">公司与方向</button></div>`;
}
export function resumeUses(d: Obj, jobId?: string) {
  const opportunityId = jobId
    ? d.state.opportunities?.find((o: Obj) => o.legacy_job_id === jobId)?.id
    : undefined;
  const uses = d.domain.resume_uses.filter(
    (u: Obj) =>
      !jobId ||
      (u.scope_type === "job" && u.scope_id === jobId) ||
      (u.scope_type === "opportunity" && u.scope_id === opportunityId),
  );
  return `<div class="pane-heading"><h2>${jobId ? "这次机会使用的版本" : "简历用途"}</h2><button class="secondary" id="resume-use">关联已保存版本</button></div>${uses.map((u: Obj) => { const useJobId = u.scope_type === "job" ? u.scope_id : d.state.opportunities?.find((o: Obj) => o.id === u.scope_id)?.legacy_job_id; return `<article class="version"><div><b>${esc(u.version_name)}</b><small>${u.scope_type === "role" ? "方向通用版" : "机会定制版"} · ${esc(u.target_name)}</small></div><a class="text-btn" href="/api/artifacts/${esc(u.artifact_id)}?download=true">下载该 PDF</a>${useJobId ? `<button class="secondary" data-application="${esc(u.version_id)}" data-application-job="${esc(useJobId)}">记录投递</button>` : ""}</article>`; }).join("") || '<p class="muted">选择一个正式版本，明确用于哪个方向或机会；关联不代表已经投递。</p>'}`;
}
export function bindKnowledge(ctx: Obj) {
  const { api, modal, modalError, render, load, navigate, getData } = ctx;
  const on = (selector: string, fn: (el: HTMLElement) => void) =>
    document
      .querySelectorAll<HTMLElement>(selector)
      .forEach((el) => (el.onclick = () => fn(el)));
  const change = (selector: string, fn: (value: string) => void) =>
    document
      .querySelectorAll<HTMLSelectElement>(selector)
      .forEach((el) => (el.onchange = () => fn(el.value)));
  on("[data-wiki-tab]", (el) => {
    knowledgeUI.tab = el.dataset.wikiTab!;
    knowledgeUI.selected = "";
    void navigate("wiki");
  });
  on("[data-wiki-select]", (el) => {
    knowledgeUI.selected = el.dataset.wikiSelect!;
    render();
  });
  change("#wiki-scope", (value) => {
    knowledgeUI.scope = value;
    knowledgeUI.selected = "";
    render();
  });
  change("#wiki-category", (value) => {
    knowledgeUI.category = value;
    knowledgeUI.selected = "";
    render();
  });
  on("[data-open-wiki]", (el) => {
    knowledgeUI.scope = el.dataset.openWiki!;
    knowledgeUI.tab = "entries";
    knowledgeUI.category = "all";
    void navigate("wiki");
  });
  on("[data-source-open]", (el) => {
    knowledgeUI.tab = "sources";
    knowledgeUI.scope = "all";
    knowledgeUI.category = "all";
    knowledgeUI.selected = el.dataset.sourceOpen!;
    render();
  });
  on("[data-entry-open]", (el) => {
    knowledgeUI.tab = "entries";
    knowledgeUI.scope = "all";
    knowledgeUI.category = "all";
    knowledgeUI.selected = el.dataset.entryOpen!;
    render();
  });
  function formDialog(
    title: string,
    html: string,
    initial: Obj,
    url: string,
    after: (result: Obj) => void,
    revision?: number,
  ) {
    let request: Obj | null = null,
      saved: Obj | null = null,
      expected = revision;
    modal(
      title,
      `<form class="knowledge-form"><fieldset>${html}</fieldset><div class="wiki-conflict"></div><button class="primary full" type="submit">保存</button></form>`,
      (dialog: HTMLDialogElement) => {
        const form = dialog.querySelector("form")!,
          fields = form.querySelector("fieldset")!,
          button = form.querySelector<HTMLButtonElement>(
            "button[type=submit]",
          )!;
        dialog.dataset.entityId = initial.id || initial.scope_id || "";
        form.onsubmit = async (event) => {
          event.preventDefault();
          if (button.disabled) return;
          if (!request) {
            const values = Object.fromEntries(new FormData(form).entries());
            request = { ...initial, ...values };
            if (form.querySelector("[data-source-choice]"))
              request.source_ids = [
                ...form.querySelectorAll<HTMLInputElement>(
                  "[data-source-choice]:checked",
                ),
              ].map((x) => x.value);
            if (values.scope) {
              const [scope_type, scope_id = ""] = String(values.scope).split(
                ":",
              );
              request.scope_type = scope_type;
              request.scope_id = scope_id;
              delete request.scope;
            }
            if (revision !== undefined) request.expected_revision = expected;
            request.idempotency_key = crypto.randomUUID();
          }
          button.disabled = true;
          fields.disabled = true;
          try {
            saved ||= await api(url, request);
            await load();
            after(saved!);
            dialog.close();
            render();
          } catch (error: any) {
            modalError(
              saved ? new Error("内容已保存，刷新失败；重试只刷新。") : error,
            );
            if (!saved && error.status === 409 && revision !== undefined) {
              try {
                await load();
                const d = getData(),
                  latest = [
                    ...d.knowledge.entries,
                    ...d.knowledge.candidates,
                    ...d.domain.objects,
                    ...d.domain.opportunities,
                  ].find((x: Obj) => x.id === initial.id);
                if (latest) {
                  const box = form.querySelector(".wiki-conflict")!;
                  box.innerHTML = `<p>当前版本已变化，请比较后合并。</p><div class="diff"><pre>${esc(JSON.stringify(request, null, 2))}</pre><pre>${esc(JSON.stringify(latest, null, 2))}</pre></div><button class="secondary" type="button">保留输入，基于最新版本继续</button>`;
                  box.querySelector("button")!.onclick = () => {
                    expected = latest.revision;
                    request = null;
                    box.innerHTML = "";
                  };
                }
              } catch {
                modalError(
                  new Error(
                    "存在版本冲突，但最新内容读取失败。输入已保留，请重试。",
                  ),
                );
              }
              request = null;
              fields.disabled = false;
            } else if (!saved && [404, 422].includes(error.status)) {
              request = null;
              fields.disabled = false;
            }
            button.textContent = saved
              ? "刷新已保存内容"
              : request
                ? "重试同一请求"
                : "保存";
          } finally {
            button.disabled = false;
          }
        };
      },
    );
  }
  on("[data-source-add]", () => {
    const d = getData(),
      scope = knowledgeUI.scope === "all" ? "personal" : knowledgeUI.scope;
    formDialog(
      "添加原始资料",
      `<label>标题<input name="title" required maxlength="500"></label><label>归属范围<select name="scope">${scopeOptions(d, scope)}</select></label><label>来源类型<select name="source_type">${Object.entries(
        sourceNames,
      )
        .map(([k, v]) => `<option value="${k}">${v}</option>`)
        .join(
          "",
        )}</select></label><label>来源位置（可选）<input name="locator" maxlength="2000" placeholder="本地路径、Git 地址或文档位置；本轮只登记"></label><label>原文 / 可保留的说明<textarea name="content" required maxlength="100000" placeholder="保留原话。公司资料仅填写允许保留的内容。"></textarea></label>`,
      {},
      "/knowledge/sources",
      (result) => {
        knowledgeUI.tab = "sources";
        knowledgeUI.scope = scopeKey(result);
        knowledgeUI.category = "all";
        knowledgeUI.selected = result.id;
      },
    );
  });
  function sourceChoices(d: Obj, x: Obj) {
    return `<details><summary>原始依据（可多选）</summary><div class="selection-list">${d.knowledge.sources
      .filter((s: Obj) => scopeKey(s) === scopeKey(x))
      .map(
        (s: Obj) =>
          `<label class="wiki-choice"><input type="checkbox" data-source-choice value="${esc(s.id)}" ${(x.source_ids || []).includes(s.id) ? "checked" : ""}><span>${esc(s.title)}<small>${esc(sourceNames[s.source_type])}</small></span></label>`,
      )
      .join("")}</div></details>`;
  }
  function candidate(sourceId?: string, id?: string) {
    const d = getData(),
      old = id ? d.knowledge.candidates.find((x: Obj) => x.id === id) : null,
      source = sourceId
        ? d.knowledge.sources.find((x: Obj) => x.id === sourceId)
        : null;
    const data = old || {
      title: source.title,
      content: source.content,
      entry_type: "project",
      source_ids: [source.id],
      scope_type: source.scope_type,
      scope_id: source.scope_id,
    };
    formDialog(
      id ? "修正待确认内容" : "整理资料",
      `<p class="muted">${esc(scopeLabel(d, data))} · 这是人工整理，确认前不进入分析。</p><label>类别<select name="entry_type">${typeOptions(data.entry_type)}</select></label><label>标题<input name="title" required maxlength="500" value="${esc(data.title)}"></label><label>当前理解<textarea name="content" required maxlength="100000">${esc(data.content)}</textarea></label>${sourceChoices(d, data)}`,
      data,
      "/knowledge/candidates" + (id ? "/" + id : ""),
      (result) => {
        knowledgeUI.tab = "candidates";
        knowledgeUI.category = "all";
        knowledgeUI.selected = result.id;
      },
      old?.revision,
    );
  }
  on("[data-candidate-new]", (el) => candidate(el.dataset.candidateNew));
  on("[data-candidate-edit]", (el) =>
    candidate(undefined, el.dataset.candidateEdit),
  );
  async function resolve(el: HTMLElement, decision: string) {
    const id = el.dataset.candidateConfirm || el.dataset.candidateReject,
      d = getData(),
      candidate = d.knowledge.candidates.find((x: Obj) => x.id === id);
    if (!id || !candidate) return;
    let operation = resolutions.get(id);
    if (operation?.busy) return;
    if (operation && operation.request.decision !== decision) {
      ctx.failure(new Error("上次操作尚未确认结果，请先重试原操作。"));
      return;
    }
    if (!operation) {
      operation = {
        request: {
          decision,
          expected_revision: candidate.revision,
          idempotency_key: crypto.randomUUID(),
        },
        busy: false,
      };
      resolutions.set(id, operation);
    }
    operation.busy = true;
    el.setAttribute("disabled", "");
    try {
      operation.result ||= await api(
        "/knowledge/candidates/" + id + "/resolve",
        operation.request,
      );
      await load();
      if (operation.result!.entry_id) {
        knowledgeUI.tab = "entries";
        knowledgeUI.selected = operation.result!.entry_id;
      }
      resolutions.delete(id);
      render();
    } catch (error: any) {
      if ([409, 422, 404].includes(error.status) && !operation.result) {
        resolutions.delete(id);
        try {
          await load();
          render();
        } catch {
          /* Keep the original error. */
        }
      }
      ctx.failure(
        operation.result
          ? new Error("操作已保存，刷新失败；重试只刷新。")
          : error,
      );
      el.removeAttribute("disabled");
    } finally {
      operation.busy = false;
    }
  }
  on("[data-candidate-confirm]", (el) => void resolve(el, "confirm"));
  on("[data-candidate-reject]", (el) => void resolve(el, "reject"));
  on("[data-entry-edit]", (el) => {
    const x = getData().knowledge.entries.find(
      (x: Obj) => x.id === el.dataset.entryEdit,
    );
    formDialog(
      "编辑当前条目",
      `<label>类别<select name="entry_type">${typeOptions(x.entry_type)}</select></label><label>标题<input name="title" required maxlength="500" value="${esc(x.title)}"></label><label>内容<textarea name="content" required maxlength="100000">${esc(x.content)}</textarea></label>${sourceChoices(getData(), x)}<label>状态<select name="status"><option value="active" ${x.status === "active" ? "selected" : ""}>当前有效</option><option value="withdrawn" ${x.status === "withdrawn" ? "selected" : ""}>撤回（不参与分析）</option></select></label>`,
      x,
      "/knowledge/entries/" + x.id,
      () => {},
      x.revision,
    );
  });
  on(
    "[data-entry-history]",
    (el) =>
      void (async () => {
        try {
          const r = await api(
            "/knowledge/entries/" + el.dataset.entryHistory + "/history",
          );
          modal(
            "修订历史",
            r.revisions
              .map(
                (x: Obj) =>
                  `<section><h3>v${x.revision} · ${esc(x.title)}</h3><pre>${esc(x.content)}</pre></section>`,
              )
              .join(""),
          );
        } catch (e) {
          ctx.failure(e);
        }
      })(),
  );
  function objectForm(kind: string, id?: string) {
    const d = getData(),
      old = id ? d.domain.objects.find((x: Obj) => x.id === id) : null,
      x = old || {},
      os = d.domain.objects;
    formDialog(
      (id ? "编辑" : "建立") + objectNames[kind],
      `<label>名称<input name="name" required maxlength="500" value="${esc(x.name)}"></label>${
        kind === "org_unit"
          ? `<label>公司<select name="company_id" required>${os
              .filter((o: Obj) => o.kind === "company")
              .map(
                (o: Obj) =>
                  `<option value="${esc(o.id)}" ${x.company_id === o.id ? "selected" : ""}>${esc(o.name)}</option>`,
              )
              .join(
                "",
              )}</select></label><label>上级组织<select name="parent_id"><option value="">直属公司</option>${os
              .filter((o: Obj) => o.kind === "org_unit" && o.id !== id)
              .map(
                (o: Obj) =>
                  `<option value="${esc(o.id)}" ${x.parent_id === o.id ? "selected" : ""}>${esc(orgPath(os, o.id))}</option>`,
              )
              .join("")}</select></label>`
          : ""
      }<label>说明<textarea name="description" maxlength="10000">${esc(x.description)}</textarea></label>`,
      { ...x, kind },
      "/domain/objects" + (id ? "/" + id : ""),
      () => {},
      old?.revision,
    );
  }
  on("[data-object-new]", (el) => objectForm(el.dataset.objectNew!));
  on("[data-object-edit]", (el) => {
    const x = getData().domain.objects.find(
      (x: Obj) => x.id === el.dataset.objectEdit,
    );
    objectForm(x.kind, x.id);
  });
  on("#opportunity-objects", () => {
    const d = getData(),
      jobId = d.jobId,
      old = d.domain.opportunities.find((x: Obj) => x.job_id === jobId) || {
        id: "opportunity-context:" + jobId,
        revision: 0,
      };
    const choose = (label: string, name: string, kind: string) =>
      `<label>${label}<select name="${name}"><option value="">未知 / 未设置</option>${d.domain.objects
        .filter((x: Obj) => x.kind === kind)
        .map(
          (x: Obj) =>
            `<option value="${esc(x.id)}" ${old[name] === x.id ? "selected" : ""}>${esc(kind === "org_unit" ? orgPath(d.domain.objects, x.id) : x.name)}</option>`,
        )
        .join("")}</select></label>`;
    formDialog(
      "机会关联",
      choose("求职周期", "search_cycle_id", "search_cycle") +
        choose("目标方向", "target_role_id", "target_role") +
        choose("公司", "company_id", "company") +
        choose("部门 / 团队", "org_unit_id", "org_unit") +
        '<p class="muted">在“公司与方向”中建立可复用对象；未知层级可以留空。</p>',
      old,
      "/domain/opportunities/" + jobId,
      () => {},
      old.revision,
    );
  });
  on("#resume-use", () => {
    const d = getData();
    formDialog(
      "关联简历版本",
      `<label>已保存版本<select name="version_id" required><option value="">请选择</option>${d.editorVersions.map((v: Obj) => `<option value="${esc(v.id)}">${esc(v.name)}</option>`).join("")}</select></label><label>用途<select name="scope" required><option value="">请选择方向或机会</option>${d.domain.objects
        .filter((o: Obj) => o.kind === "target_role")
        .map(
          (o: Obj) =>
            `<option value="role:${esc(o.id)}">方向通用 · ${esc(o.name)}</option>`,
        )
        .join(
          "",
        )}${d.state.jobs.map((j: Obj) => `<option value="job:${esc(j.id)}" ${d.page === "jobs" && j.id === d.jobId ? "selected" : ""}>机会定制 · ${esc(j.company)} / ${esc(j.title)}</option>`).join("")}</select></label><p class="muted">引用固定的版本与 PDF，后续编辑不会改变此引用。此处不记录实际投递。</p>`,
      {},
      "/domain/resume-uses",
      () => {},
    );
  });
}
