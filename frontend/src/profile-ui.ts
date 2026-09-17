type Obj = Record<string, any>;

type ProfileContext = {
  state: Obj;
  api: (path: string, body?: Obj) => Promise<any>;
  modal: (
    title: string,
    content: string,
    onReady?: (dialog: HTMLDialogElement) => void,
  ) => HTMLDialogElement;
  modalError: (error: unknown) => void;
  load: () => Promise<void>;
  render: () => void;
  navigate?: (page: string) => Promise<void>;
};

export function hasUnsavedProfile(): boolean {
  return !!document.querySelector(
    'form[data-profile-form][data-dirty="true"], dialog[data-dirty="true"]',
  );
}

const esc = (value: any) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );

const entryTypes: Record<string, string> = {
  goal: "职业目标",
  constraint: "偏好与约束",
  experience: "经历",
  capability: "能力",
  project: "项目",
  achievement: "成果",
};

function basicsOf(profile: Obj): Obj {
  const basics = profile.basics || {};
  return {
    name: basics.name ?? profile.name ?? "",
    email: basics.email ?? profile.email ?? "",
    phone: basics.phone ?? profile.phone ?? "",
    wechat: basics.wechat ?? profile.wechat ?? "",
    github: basics.github ?? profile.github ?? "",
    links: Array.isArray(basics.links)
      ? basics.links
      : Array.isArray(profile.links)
        ? profile.links
        : [],
  };
}

function isLegacy(profile: Obj): boolean {
  return profile.mode !== "structured" && String(profile.content || "").trim() !== "";
}

function canRetrySameRequest(error: any): boolean {
  return !error?.status || error.status >= 500;
}

function linkRows(links: Obj[] = []) {
  return links
    .map(
      (link) =>
        `<div class="profile-link" data-profile-link><label>名称<input name="link_label" maxlength="100" value="${esc(link.label)}" placeholder="例如：个人主页"></label><label>网址<input name="link_url" type="url" maxlength="2000" value="${esc(link.url)}" placeholder="https://..."></label><button type="button" class="text-btn" data-remove-profile-link>移除</button></div>`,
    )
    .join("");
}

function basicsFields(basics: Obj) {
  return `<div class="form-grid"><label>姓名<input name="name" aria-label="姓名" maxlength="200" value="${esc(basics.name)}"></label><label>邮箱<input name="email" type="email" aria-label="邮箱" maxlength="320" value="${esc(basics.email)}"></label><label>电话<input name="phone" aria-label="电话" maxlength="100" value="${esc(basics.phone)}"></label><label>微信<input name="wechat" aria-label="微信" maxlength="500" value="${esc(basics.wechat)}"></label><label>GitHub<input name="github" type="url" aria-label="GitHub 地址" maxlength="500" value="${esc(basics.github)}" placeholder="https://github.com/用户名"></label></div><fieldset class="profile-links" data-profile-links><legend>个人网页链接</legend><p class="muted">可添加个人主页、作品集、博客等公开链接，网址请填写完整的 https:// 地址。</p><div data-profile-link-list>${linkRows(basics.links)}</div><button type="button" class="secondary" data-add-profile-link>添加网页链接</button></fieldset>`;
}

function entryTypeOptions(value = "experience") {
  return Object.entries(entryTypes)
    .map(([key, label]) => `<option value="${key}" ${key === value ? "selected" : ""}>${label}</option>`)
    .join("");
}

function entryRow(entry: Obj = {}, index = 0) {
  return `<div class="profile-entry" data-profile-entry><div class="form-grid"><label>条目类型<select name="entry_type">${entryTypeOptions(entry.entry_type)}</select></label><label>标题<input name="title" maxlength="500" value="${esc(entry.title)}" placeholder="例如：负责过的项目"></label></div><label>整理内容<textarea name="content" maxlength="100000" placeholder="只写你愿意整理为待确认候选的内容">${esc(entry.content)}</textarea></label><button type="button" class="text-btn" data-remove-profile-entry>移除此条目</button><span class="muted">候选条目 ${index + 1} · 后续仍需确认后才会进入可信资料</span></div>`;
}

function basicsForm(profile: Obj) {
  const basics = basicsOf(profile);
  return `<section class="profile-editor"><div class="pane-heading"><div><h2>基础资料</h2><p class="muted">维护姓名、联系方式和公开网页链接。经历、能力与目标请整理到职业 Wiki。</p></div></div><form id="profile-basics-form" data-profile-form>${basicsFields(basics)}<button class="primary" type="submit">保存基础资料</button></form></section>`;
}

export function profilePanel(profile: Obj): string {
  const original = String(profile.content || "");
  if (isLegacy(profile)) {
    return `<section class="profile-editor"><div class="pane-heading"><div><h2>基础资料</h2><p class="muted">这份资料仍是旧版自由文本，需要你明确整理后才能保存新的结构化资料。</p></div></div><div class="source-card"><h3>原始资料（只读保留）</h3><pre>${esc(original)}</pre><p class="muted">在完成整理前，旧原文仍会被分析读取，可能与 Wiki 条目重复；整理后原文继续保留，但不再作为当前基础资料重复使用。</p></div><button class="primary" type="button" data-profile-organize>整理并保存</button></section>`;
  }
  return basicsForm(profile);
}

function profileFromState(state: Obj): Obj {
  return state?.profile || state || {};
}

function formValues(form: HTMLFormElement) {
  const data = new FormData(form);
  const links = [...form.querySelectorAll<HTMLElement>("[data-profile-link]")]
    .map((row) => ({
      label: String(row.querySelector<HTMLInputElement>('[name="link_label"]')?.value || "").trim(),
      url: String(row.querySelector<HTMLInputElement>('[name="link_url"]')?.value || "").trim(),
    }))
    .filter((link) => link.label || link.url);
  return {
    name: String(data.get("name") || "").trim(),
    email: String(data.get("email") || "").trim(),
    phone: String(data.get("phone") || "").trim(),
    wechat: String(data.get("wechat") || "").trim(),
    github: String(data.get("github") || "").trim(),
    links,
  };
}

function bindLinkControls(root: ParentNode) {
  const list = root.querySelector<HTMLElement>("[data-profile-link-list]");
  const add = root.querySelector<HTMLButtonElement>("[data-add-profile-link]");
  if (!list || !add) return;
  const changed = () => {
    add.disabled = list.children.length >= 10;
    const form = list.closest("form"); if (form) form.dataset.dirty = "true";
  };
  add.disabled = list.children.length >= 10;
  add.addEventListener("click", () => {
    if (list.children.length >= 10) return;
    list.insertAdjacentHTML(
      "beforeend",
      `<div class="profile-link" data-profile-link><label>名称<input name="link_label" maxlength="100" placeholder="例如：个人主页"></label><label>网址<input name="link_url" type="url" maxlength="2000" placeholder="https://..."></label><button type="button" class="text-btn" data-remove-profile-link>移除</button></div>`,
    );
    const row = list.lastElementChild!;
    row.querySelector("[data-remove-profile-link]")?.addEventListener("click", () => { row.remove(); changed(); });
    row.querySelector<HTMLInputElement>("input")?.focus();
    changed();
  });
  root.querySelectorAll("[data-remove-profile-link]").forEach((button) =>
    button.addEventListener("click", () => { button.closest("[data-profile-link]")?.remove(); changed(); }),
  );
}

function conflictText(latest: Obj) {
  const p = profileFromState(latest);
  const b = basicsOf(p);
  return `<div class="diff"><section><h3>服务器当前基础资料</h3><pre>${esc(`姓名：${b.name}\n邮箱：${b.email}\n电话：${b.phone}\n微信：${b.wechat}\nGitHub：${b.github}\n网页链接：${b.links.map((link: Obj) => `${link.label || "未命名"} ${link.url}`).join("\n") || "（无）"}`)}</pre></section><section><h3>服务器当前原文</h3><pre>${esc(p.content || "（无旧自由文本）")}</pre></section></div>`;
}

function showConflict(
  ctx: ProfileContext,
  dialog: HTMLDialogElement,
  request: Obj,
  latest: Obj,
  retry: () => void,
) {
  const host = dialog.querySelector<HTMLElement>("[data-profile-conflict]");
  if (!host) return;
  host.innerHTML = `<p class="notice">资料已被其他窗口修改。你的表单输入已保留，请比较服务器版本后再继续。</p>${conflictText(latest)}<button type="button" class="secondary" data-profile-use-latest>采用服务器当前资料作为保存基准</button>`;
  host.querySelector("[data-profile-use-latest]")?.addEventListener("click", () => {
    request.expected_revision = profileFromState(latest).revision;
    host.innerHTML = `<p class="notice">已采用服务器当前资料作为保存基准；你的输入仍保留，请检查后再次保存。</p>`;
    retry();
  });
  ctx.modalError(new Error("版本冲突：请比较服务器版本后再保存。"));
}

async function reloadOnly(ctx: ProfileContext, dialog: HTMLDialogElement | null) {
  if (dialog?.isConnected) dialog.close();
  try {
    await ctx.load();
    ctx.render();
  } catch (error) {
    ctx.modal(
      "保存成功，刷新失败",
      `<p class="notice">保存已经成功，但刷新页面数据失败。请重试刷新，不会重复提交。</p><div data-profile-reload-error></div><button type="button" class="secondary" data-profile-reload>重试刷新</button>`,
      (retryDialog) => {
        retryDialog.querySelector("[data-profile-reload]")?.addEventListener("click", () => void reloadOnly(ctx, retryDialog));
        ctx.modalError(error);
      },
    );
  }
}

function organizeDialog(ctx: ProfileContext, profile: Obj) {
  const initial = basicsOf(profile);
  ctx.modal(
    "整理旧版个人资料",
    `<form id="profile-organize-form" data-profile-form><fieldset><p>原文会完整保留。请填写基础字段，并把需要后续确认的内容拆成条目。</p><div class="source-card"><h3>原始资料（完整只读）</h3><pre>${esc(profile.content || "")}</pre></div>${basicsFields(initial)}<label class="check-row"><input type="checkbox" name="confirmed" required>我已核对原文，确认整理后完整保留原文；当前基础资料只采用上面的基础字段</label><div id="profile-entries"><h3>待确认条目（可选）</h3><p class="muted">这些内容提交后仍是待确认候选，不会自动成为可信资料。</p><div data-profile-entry-list></div><button type="button" class="secondary" data-add-profile-entry>添加待确认条目</button></div></fieldset><div data-profile-conflict></div><div data-profile-reload-error></div><button class="primary full" type="submit">确认整理并保存</button></form>`,
    (dialog) => {
      const form = dialog.querySelector<HTMLFormElement>("#profile-organize-form")!;
      const fieldset = form.querySelector<HTMLFieldSetElement>("fieldset")!;
      const list = dialog.querySelector<HTMLElement>("[data-profile-entry-list]")!;
      bindLinkControls(dialog);
      let expected = profile.revision ?? 0;
      const add = (entry?: Obj) => {
        list.insertAdjacentHTML("beforeend", entryRow(entry, list.children.length));
        const row = list.lastElementChild as HTMLElement | null;
        row?.querySelector("[data-remove-profile-entry]")?.addEventListener("click", () => row.remove());
      };
      dialog.querySelector("[data-add-profile-entry]")?.addEventListener("click", () => add());
      let busy = false;
      let pendingRequest: Obj | null = null;
      form.onsubmit = async (event) => {
        event.preventDefault();
        if (busy) return;
        const submit = form.querySelector<HTMLButtonElement>('button[type="submit"]')!;
        if (!form.checkValidity()) { form.reportValidity(); return; }
        const values = formValues(form);
        const entries = [...list.querySelectorAll<HTMLElement>("[data-profile-entry]")]
          .map((row) => ({
            title: String(row.querySelector<HTMLInputElement>('[name="title"]')?.value || "").trim(),
            content: String(row.querySelector<HTMLTextAreaElement>('[name="content"]')?.value || "").trim(),
            entry_type: String(row.querySelector<HTMLSelectElement>('[name="entry_type"]')?.value || "experience"),
          }))
          .filter((entry) => entry.title || entry.content);
        const confirmed = form.querySelector<HTMLInputElement>('[name="confirmed"]')?.checked === true;
        const request = pendingRequest || { basics: values, expected_revision: expected, idempotency_key: crypto.randomUUID(), confirmed, entries };
        busy = true;
        fieldset.disabled = true;
        submit.disabled = true;
        try {
          await ctx.api("/profile/organize", request);
          pendingRequest = null;
          await reloadOnly(ctx, dialog);
        } catch (error: any) {
          if (error?.status === 409) {
            pendingRequest = null;
            try {
              const latest = await ctx.api("/state");
              showConflict(ctx, dialog, request, latest, () => { expected = request.expected_revision; });
            } catch (loadError) { ctx.modalError(loadError); }
          } else if (canRetrySameRequest(error)) {
            pendingRequest = request;
            ctx.modalError(error);
          } else {
            pendingRequest = null;
            ctx.modalError(error);
          }
        } finally {
          busy = false;
          if (fieldset.isConnected) fieldset.disabled = false;
          if (submit.isConnected) submit.disabled = false;
        }
      };
    },
  );
}

export function bindProfile(ctx: ProfileContext): void {
  const profile = profileFromState(ctx.state);
  document.querySelector<HTMLElement>("[data-profile-organize]")?.addEventListener("click", () => organizeDialog(ctx, profile));
  const form = document.querySelector<HTMLFormElement>("#profile-basics-form");
  if (!form) return;
  bindLinkControls(form);
  let expected = profile.revision ?? 0;
  let basicsRequest: Obj | null = null;
  let busy = false;
  form.addEventListener("input", () => {
    form.dataset.dirty = "true";
  });
  form.onsubmit = async (event) => {
    event.preventDefault();
    if (busy) return;
    const request = basicsRequest || { basics: formValues(form), expected_revision: expected };
    busy = true;
    const submit = form.querySelector<HTMLButtonElement>('button[type="submit"]');
    if (submit) submit.disabled = true;
    try {
      await ctx.api("/profile/basics", request);
      basicsRequest = null;
      delete form.dataset.dirty;
      await reloadOnly(ctx, null);
    } catch (error: any) {
      if (error?.status === 409) {
        basicsRequest = null;
        try {
          const latest = await ctx.api("/state");
          const dialog = ctx.modal("资料版本冲突", `<div data-profile-conflict></div><button type="button" class="primary" data-profile-close>返回表单</button>`, (d) => d.querySelector("[data-profile-close]")?.addEventListener("click", () => d.close()));
          showConflict(ctx, dialog, request, latest, () => { expected = request.expected_revision; });
        } catch (loadError) { ctx.modalError(loadError); }
      } else if (canRetrySameRequest(error)) {
        basicsRequest = request;
        ctx.modalError(error);
      } else {
        basicsRequest = null;
        ctx.modalError(error);
      }
    } finally {
      busy = false;
      if (submit?.isConnected) submit.disabled = false;
    }
  };
}
