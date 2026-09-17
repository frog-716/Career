"use strict";

if (location.protocol === "file:") {
  location.replace("http://127.0.0.1:8765/");
}

const paper = document.getElementById("paper");
const pageStatus = document.getElementById("pageStatus");
const undoButton = document.getElementById("undo");
const redoButton = document.getElementById("redo");
const versionDialog = document.getElementById("versionDialog");
const versionList = document.getElementById("versionList");
const restoreDialog = document.getElementById("restoreDialog");
const restoreDialogMessage = document.getElementById("restoreDialogMessage");
const toastElement = document.getElementById("toast");
const materialsDialog = document.getElementById("materialsDialog");
const materialsList = document.getElementById("materialsList");
const sourcesDialog = document.getElementById("sourcesDialog");
const sourcesList = document.getElementById("sourcesList");
const editorJobId = new URLSearchParams(location.search).get("job_id") || "";

const SECTION_TYPES = ["skills", "experience", "projects", "education"];
const SECTION_NAMES = {
  skills: "专业技能",
  experience: "实习经历",
  projects: "项目经历",
  education: "教育背景",
};



let resume = null;
let undoStack = [];
let redoStack = [];
let saveTimer = null;
let toastTimer = null;
let savedRange = null;
let activeEditable = null;
let focusAfterRender = null;
let contentRoot = null;
let lastOverflowPixels = 0;
let lastCloudSavedAt = null;
let saveInFlight = false;


let localChangePending = false;
let lastLocalEditAt = 0;
let revision = 0;
let savedSnapshot = "";
let autosaveChain = Promise.resolve();
let editorLocked = false;
let conflictState = null;
let pendingVersion = null;
let conflictDialog = null;
let materialsRequest = null;
let materialsBusy = false;

function newId(prefix = "item") {
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${random}`;
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function sanitizeHTML(value) {
  const source = new DOMParser().parseFromString(String(value ?? ""), "text/html");
  const output = document.createElement("div");
  const allowed = new Set(["B", "STRONG", "I", "EM", "U", "BR", "FONT", "SPAN"]);

  function copyNode(node) {
    if (node.nodeType === Node.TEXT_NODE) return document.createTextNode(node.nodeValue || "");
    if (node.nodeType !== Node.ELEMENT_NODE) return document.createDocumentFragment();
    const tag = node.tagName.toUpperCase();
    const target = allowed.has(tag) ? document.createElement(tag.toLowerCase()) : document.createDocumentFragment();
    if (tag === "FONT" && /^[1-7]$/.test(node.getAttribute("size") || "")) {
      target.setAttribute("size", node.getAttribute("size"));
    }
    if (tag === "SPAN" && /^\d+(?:\.5)?pt$/.test(node.style.fontSize || "")) {
      target.style.fontSize = node.style.fontSize;
    }
    node.childNodes.forEach((child) => target.append(copyNode(child)));
    return target;
  }

  source.body.childNodes.forEach((node) => output.append(copyNode(node)));
  return output.innerHTML;
}

function cleanContent(value) {
  return sanitizeHTML(typeof value === "object" && value ? value.content : value);
}

function normalizeBullets(values = []) {
  return values.map((value) => ({
    id: value?.id || newId("bullet"),
    content: cleanContent(value),
  }));
}

function normalizeDocument(value) {
  const source = value && typeof value === "object" ? value : {};
  const profile = source.profile && typeof source.profile === "object" ? source.profile : {};
  const sourceSections = Array.isArray(source.sections) ? source.sections : [];
  const sections = SECTION_TYPES.map((type) => {
    const section = sourceSections.find((candidate) => candidate?.type === type) || {};
    const items = Array.isArray(section.items) ? section.items : [];
    const base = {
      id: section.id || `section-${type}`,
      type,
      title: cleanContent(section.title || SECTION_NAMES[type]),
      items: [],
    };
    if (type === "skills") {
      base.items = items.map((item) => ({id: item?.id || newId("skill"), content: cleanContent(item)}));
    } else if (type === "experience") {
      base.items = items.map((item) => ({
        id: item?.id || newId("experience"),
        organization: cleanContent(item?.organization || item?.company || ""),
        role: cleanContent(item?.role || ""),
        date: cleanContent(item?.date || ""),
        bullets: normalizeBullets(item?.bullets),
      }));
    } else if (type === "projects") {
      base.items = items.map((item) => ({
        id: item?.id || newId("project"),
        title: cleanContent(item?.title || ""),
        responsibility: cleanContent(item?.responsibility || ""),
        date: cleanContent(item?.date || ""),
        bullets: normalizeBullets(item?.bullets),
      }));
    } else {
      base.items = items.map((item) => ({
        id: item?.id || newId("education"),
        school: cleanContent(item?.school || ""),
        major: cleanContent(item?.major || ""),
        date: cleanContent(item?.date || ""),
        bullets: normalizeBullets(item?.bullets || item?.lines),
      }));
    }
    return base;
  });

  return {
    schemaVersion: 1,
    profile: {
      id: profile.id || "profile-main",
      name: cleanContent(profile.name || "姓名"),
      contacts: (Array.isArray(profile.contacts) ? profile.contacts : [
        {id: "contact-phone", content: "电话：", kind: "identity"},
        {id: "contact-email", content: "邮箱：", kind: "identity"},
        {id: "contact-wechat", content: "微信：", kind: "identity"},
      ]).map((contact, index) => ({
        id: contact?.id || newId("contact"),
        content: cleanContent(contact),
        kind: contact?.kind === "identity" ? "identity" : contact?.kind === "link" || index >= 3 ? "link" : "identity",
        href: String(contact?.href || "").trim(),
      })),
    },
    sections,
    formatting: source.formatting && typeof source.formatting === "object" ? source.formatting : {},
    meta: source.meta && typeof source.meta === "object" ? source.meta : {},
  };
}

function section(type) {
  return resume.sections.find((candidate) => candidate.type === type);
}

function setStatus(message, state = "saved") {
  const status = document.getElementById("saveStatus");
  status.textContent = message;
  status.classList.toggle("error", state === "error");
  if (state === "error") showToast(message);
}

function lockEditor(locked) {
  editorLocked = locked;
  paper.inert = locked;
  document.querySelector(".app-bar").inert = locked;
  document.getElementById("saveVersion").disabled = Boolean(pendingVersion);
  document.getElementById("exportPdf").disabled = Boolean(pendingVersion);
}

function askInPage(message, withName = false) {
  const dialog = document.createElement('dialog');
  dialog.innerHTML = '<form><h2></h2><label hidden>版本名称<input maxlength="200" autocomplete="off"></label><div class="restore-actions"><button type="button">取消</button><button type="submit">确认</button></div></form>';
  dialog.querySelector('h2').textContent = message;
  const input = dialog.querySelector('input');
  dialog.querySelector('label').hidden = !withName; input.required = withName;
  document.body.append(dialog); dialog.showModal();
  if (withName) input.focus();
  return new Promise(resolve => {
    let result = null;
    dialog.querySelector('[type="button"]').onclick = () => dialog.close();
    dialog.querySelector('form').onsubmit = event => { event.preventDefault(); result = withName ? input.value.trim() : true; dialog.close(); };
    dialog.addEventListener('close', () => { dialog.remove(); resolve(result); }, {once: true});
  });
}

function showToast(message) {
  clearTimeout(toastTimer);
  toastElement.textContent = message;
  toastElement.classList.add("show");
  toastTimer = setTimeout(() => toastElement.classList.remove("show"), 2600);
}

function snapshot() {
  return JSON.stringify(resume);
}

async function flushSave() {
  clearTimeout(saveTimer); saveTimer = null;
  await autosaveChain.catch(() => {});
  if (conflictState) { showConflict(); throw new Error("请先处理保存冲突"); }
  if (revision === 0 || snapshot() !== savedSnapshot) {
    localChangePending = true;
    autosaveChain = saveDocument();
    await autosaveChain;
  }
  if (localChangePending) throw new Error("当前内容尚未保存");
}

function showConflict() {
  if (!conflictState || conflictDialog?.open) return;
  const compared = conflictState;
  const dialog = document.createElement("dialog");
  conflictDialog = dialog;
  dialog.className = "conflict-dialog";
  dialog.innerHTML = '<div class="dialog-head"><h2>保存冲突</h2><button type="button" data-close>关闭</button></div><p>当前输入已保留，请比较两边后选择。</p><div class="diff"><section><h3>当前输入</h3><pre data-mine></pre></section><section><h3>服务器版本</h3><pre data-server></pre></section></div><div class="restore-actions"><button data-reload type="button">重新载入服务器版本</button><button data-keep type="button">保存当前输入</button></div>';
  dialog.querySelector('[data-mine]').textContent = documentText(resume);
  dialog.querySelector('[data-server]').textContent = documentText(compared.server);
  document.body.append(dialog); dialog.showModal();
  dialog.querySelector('[data-close]').onclick = () => dialog.close();
  dialog.addEventListener('close', () => { dialog.remove(); conflictDialog = null; });
  dialog.querySelector('[data-reload]').onclick = () => {
    clearTimeout(saveTimer); saveTimer = null;
    resume = normalizeDocument(compared.server); revision = compared.revision;
    savedSnapshot = snapshot(); localChangePending = false; conflictState = null;
    undoStack = []; redoStack = []; activeEditable = null;
    dialog.close(); render(); updateHistoryButtons(); setStatus("已载入服务器版本");
  };
  dialog.querySelector('[data-keep]').onclick = async () => {
    resume.meta.source_refs = clone(compared.server.meta?.source_refs || []);
    revision = compared.revision; conflictState = null;
    dialog.close();
    try { await flushSave(); } catch (error) { setStatus(error.message, 'error'); }
  };
}

async function requestBackend(url, {method = "GET", data, cache} = {}) {
  if (typeof window.__backendRequest__ === "function") {
    return window.__backendRequest__(url, {method, data});
  }

  const response = await fetch(url, {
    method,
    headers: {"Content-Type": "application/json", "X-Career-Request": "1"},
    body: data === undefined ? undefined : JSON.stringify(data),
    cache,
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // 保留 null；下方仍会按 HTTP 状态抛出明确错误。
  }
  if (!response.ok) {
    const error = new Error(payload?.detail || `HTTP ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return {status: response.status, data: payload};
}

function updateHistoryButtons() {
  undoButton.disabled = undoStack.length === 0;
  redoButton.disabled = redoStack.length === 0;
}

function checkpoint() {
  const value = snapshot();
  if (undoStack.at(-1) !== value) undoStack.push(value);
  if (undoStack.length > 100) undoStack.shift();
  redoStack = [];
  updateHistoryButtons();
}

function applySnapshot(serialized) {
  const next = JSON.parse(serialized);
  // source_refs are server-owned. Old undo snapshots must not erase refs added
  // by a later Wiki import or a concurrent server response.
  const currentRefs = Array.isArray(resume?.meta?.source_refs) ? resume.meta.source_refs : [];
  const nextMeta = next.meta && typeof next.meta === "object" ? next.meta : {};
  if (Array.isArray(resume?.meta?.source_refs)) nextMeta.source_refs = clone(currentRefs);
  next.meta = nextMeta;
  resume = normalizeDocument(next);
  render();
  queueSave();
}

function undo() {
  if (editorLocked) return;
  if (!undoStack.length) return;
  redoStack.push(snapshot());
  applySnapshot(undoStack.pop());
  updateHistoryButtons();
}

function redo() {
  if (editorLocked) return;
  if (!redoStack.length) return;
  undoStack.push(snapshot());
  applySnapshot(redoStack.pop());
  updateHistoryButtons();
}

function queueSave() {
  if (editorLocked) return;
  localChangePending = snapshot() !== savedSnapshot;
  if (!localChangePending) { setStatus("已保存"); return; }
  setStatus(conflictState ? "保存冲突 · 当前输入已保留" : "未保存", conflictState ? "error" : "saving");
  clearTimeout(saveTimer);
  if (conflictState) return;
  saveTimer = setTimeout(() => {
    saveTimer = null;
    autosaveChain = autosaveChain.catch(() => {}).then(saveDocument);
    autosaveChain.catch(() => {});
  }, 350);
}

async function saveDocument() {
  if (!resume || conflictState) return;
  if (snapshot() === savedSnapshot && revision !== 0) { localChangePending = false; return; }
  saveInFlight = true;
  try {
    resume.meta.updatedAt = new Date().toISOString();
    const sent = snapshot();
    const {data: payload} = await requestBackend("/api/editor", {
      method: "PUT", data: {document: JSON.parse(sent), expected_revision: revision},
    });
    revision = payload.revision; savedSnapshot = sent;
    localChangePending = snapshot() !== sent;
    setStatus(localChangePending ? "未保存" : "已保存");
  } catch (error) {
    localChangePending = true;
    if (error.status === 409) {
      try {
        const latest = await requestBackend("/api/editor", {cache: "no-store"});
        conflictState = {server: latest.data.document, revision: latest.data.revision};
        showConflict();
      } catch (readError) { showToast(`保存冲突，无法读取最新版本：${readError.message}`); }
    }
    setStatus(`保存失败：${error.message}`, "error");
    throw error;
  } finally { saveInFlight = false; }
}

function mutate(change, message, focusId = null) {
  if (editorLocked) return;
  checkpoint();
  change();
  focusAfterRender = focusId;
  render();
  queueSave();
  if (message) showToast(message);
}

function moveItem(items, index, offset) {
  const target = index + offset;
  if (target < 0 || target >= items.length) return false;
  [items[index], items[target]] = [items[target], items[index]];
  return true;
}

function button(label, title, onClick, className = "") {
  const element = document.createElement("button");
  element.type = "button";
  element.textContent = label;
  element.title = title;
  element.className = className;
  element.addEventListener("mousedown", (event) => event.preventDefault());
  element.addEventListener("click", onClick);
  return element;
}

function tools(actions) {
  const container = document.createElement("div");
  container.className = "item-tools";
  const toggle = button("⋯", "打开操作菜单", () => container.classList.toggle("is-open"), "tools-toggle");
  const actionGroup = document.createElement("span");
  actionGroup.className = "tools-actions";
  actions.forEach((action) => {
    if (action.hidden) return;
    const control = button(action.label, action.title, action.run, action.className || "");
    control.disabled = Boolean(action.disabled);
    actionGroup.append(control);
  });
  container.append(toggle, actionGroup);
  return container;
}

function bindEditable(element, value, setter, options = {}) {
  const {placeholder = "点击编辑", editId = newId("edit")} = options;
  element.classList.add("editable");
  element.contentEditable = "true";
  element.dataset.placeholder = placeholder;
  element.dataset.editId = editId;
  element.innerHTML = sanitizeHTML(value);
  element.dataset.empty = element.textContent.trim() ? "false" : "true";
  element.style.textAlign = resume.formatting?.[editId]?.textAlign || "";
  element.addEventListener("focus", () => {
    activeEditable = element;
    checkpoint();
  });
  element.addEventListener("input", () => {
    if (editorLocked) return;
    const hasText = Boolean(element.textContent.trim());
    if (!hasText) element.replaceChildren();
    setter(hasText ? sanitizeHTML(element.innerHTML) : "");
    element.dataset.empty = hasText ? "false" : "true";
    activeEditable = element;
    queueSave();
    requestAnimationFrame(updatePageStatus);
  });
  element.addEventListener("blur", () => {
    if (editorLocked) return;
    const next = Boolean(element.textContent.trim()) ? sanitizeHTML(element.innerHTML) : "";
    const before = snapshot(); setter(next); element.dataset.empty = next ? "false" : "true";
    if (snapshot() !== before) queueSave();
  });
  return element;
}

function editable(tag, className, value, setter, options) {
  const element = document.createElement(tag);
  element.className = className;
  return bindEditable(element, value, setter, options);
}

function renderHeader() {
  const header = document.createElement("div");
  header.className = "resume-header";
  header.append(editable("h1", "name", resume.profile.name, (value) => { resume.profile.name = value; }, {
    placeholder: "姓名",
    editId: "profile-name",
  }));

  const contactType = (contact) => {
    const text = textOf(contact.content).trim();
    if (contact.kind === "link") return /^github\s*[：:]/i.test(text) || /(?:^|\/)github\.com(?:\/|$)/i.test(contact.href || text) ? "github" : "link";
    const stable = {"contact-phone": "phone", "contact-email": "email", "contact-wechat": "wechat"}[contact.id];
    if (stable) return stable;
    if (/^(微信|wechat)\s*[：:]/i.test(text)) return "wechat";
    if (/^(邮箱|email)\s*[：:]/i.test(text) || /[^\s@]+@[^\s@]+\.[^\s@]+/.test(text)) return "email";
    if (/^(电话|手机|phone)\s*[：:]/i.test(text) || /^[+\d ()-]{7,}$/.test(text.replace(/^联系方式\s*[：:]?\s*/, ""))) return "phone";
    return "identity";
  };
  const contactLabel = (contact) => ({phone: "电话", email: "邮箱", wechat: "微信", github: "GitHub"})[contactType(contact)] || "联系方式";
  const contactValue = (contact) => {
    if (contact.kind === "link") return contactType(contact) === "github" ? contact.content.replace(/^GitHub\s*[：:]\s*/i, "") : contact.content;
    return textOf(contact.content).replace(/^(电话|手机|邮箱|微信|联系方式|phone|email|wechat)\s*[：:]?\s*/i, "");
  };
  const contactIcon = (contact) => {
    if (contactType(contact) === "github") {
      const icon = document.createElement("span");
      icon.className = "contact-icon contact-icon-github";
      icon.setAttribute("aria-label", "GitHub");
      icon.setAttribute("role", "img");
      return icon;
    }
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("class", "contact-icon");
    icon.classList.add(`contact-icon-${contact.id}`);
    icon.classList.add(`contact-icon-${contactType(contact)}`);
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.setAttribute("aria-label", contactLabel(contact));
    icon.setAttribute("role", "img");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const paths = {
      "contact-phone": "M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.12 4.2 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.9.33 1.78.62 2.63a2 2 0 0 1-.45 2.11L8 9.73a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.85.29 1.73.5 2.63.62A2 2 0 0 1 22 16.92Z",
      "contact-email": "M3 5.5h18v13H3z M3.5 6.2 12 12.5l8.5-6.3",
      "contact-wechat": "M8.5 6.2c-3.1 0-5.7 2-5.7 4.6 0 1.5.8 2.8 2.2 3.7l-.6 2 2.3-1.2c.6.2 1.2.3 1.8.3h.5c-.1-.4-.2-.8-.2-1.2 0-2.7 2.7-4.9 6-4.9h.5c-.2-1.9-2.3-3.3-4.8-3.3H8.5Zm6.6 4.7c-2.5 0-4.6 1.5-4.6 3.4s2.1 3.4 4.6 3.4c.5 0 1-.1 1.5-.2l1.8.9-.5-1.5c1.1-.6 1.8-1.5 1.8-2.6 0-1.9-2.1-3.4-4.6-3.4Z",
    };
    path.setAttribute("d", paths[`contact-${contactType(contact)}`] || "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "1.8");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    if (contactType(contact) === "wechat") {
      path.setAttribute("transform", "translate(-2.4 -2.4) scale(1.2)");
    }
    icon.append(path);
    return icon;
  };
  const renderContacts = (items, className, isLinkRow = false) => {
    const contacts = document.createElement("div");
    contacts.className = `contact-row ${className}`;
    items.forEach((contact) => {
      const wrapper = document.createElement("span");
      wrapper.className = "contact-item";
      const githubContact = contactType(contact) === "github";
      if (githubContact) {
        wrapper.classList.add("contact-item-github");
        if (contact.href) {
          const link = document.createElement("a");
          link.className = "contact-github-link";
          link.href = contact.href;
          link.target = "_blank";
          link.rel = "noreferrer noopener";
          link.title = "打开 GitHub";
          link.append(contactIcon(contact));
          wrapper.append(link);
        } else {
          const icon = contactIcon(contact);
          icon.title = "请在基础资料中填写 GitHub 链接";
          wrapper.append(icon);
        }
        contacts.append(wrapper);
        return;
      }
      if (!isLinkRow) wrapper.append(contactIcon(contact));
      const text = document.createElement("span");
      text.className = "contact-text";
      text.textContent = contactValue(contact);
      wrapper.append(text);
      if (isLinkRow) {
        const link = document.createElement("a");
        link.className = `contact-link-open${contact.href ? "" : " disabled"}`;
        link.href = contact.href || "#";
        link.target = "_blank";
        link.rel = "noreferrer noopener";
        link.textContent = "↗";
        link.title = contact.href ? "打开网页链接" : "编辑后填入可访问的网页链接";
        link.addEventListener("click", (event) => { if (!contact.href) event.preventDefault(); });
        wrapper.append(link);
      }
      contacts.append(wrapper);
    });
    return contacts;
  };
  const identityContacts = resume.profile.contacts.filter((contact) => contact.kind !== "link");
  const linkContacts = resume.profile.contacts.filter((contact) => contact.kind === "link");
  header.classList.toggle("has-contact-links", linkContacts.length > 0);
  const identityRow = renderContacts(identityContacts, "contact-identity-row");
  if (!identityContacts.some(contact => contactType(contact) === "wechat")) {
    const addWechat = button("填写微信", "前往基础资料填写微信", async () => {
      await flushSave();
      location.href = "/#profile";
    }, "add-wechat");
    addWechat.prepend(contactIcon({id: "contact-wechat",kind: "identity",content: ""}));
    identityRow.append(addWechat);
  }
  header.append(identityRow);
  if (linkContacts.length) header.append(renderContacts(linkContacts, "contact-link-row", true));

  const editProfile = button("编辑基础资料", "编辑联系方式和个人网页", async () => {
    await flushSave();
    location.href = "/#profile";
  }, "add-contact");
  header.append(editProfile);
  contentRoot.append(header);
}

function renderSectionHeading(currentSection, addLabel, onAdd) {
  const heading = document.createElement("div");
  heading.className = "section-heading";
  heading.append(editable("span", "heading-text", currentSection.title, (value) => { currentSection.title = value; }, {
    placeholder: SECTION_NAMES[currentSection.type],
    editId: `${currentSection.id}-title`,
  }));
  const line = document.createElement("i");
  line.className = "heading-line";
  heading.append(line);
  heading.append(tools([{label: "+", title: addLabel, run: onAdd}]));
  contentRoot.append(heading);
}

function renderSkills(currentSection) {
  renderSectionHeading(currentSection, "增加技能行", () => {
    const item = {id: newId("skill"), content: "技能类别：请填写"};
    mutate(() => currentSection.items.push(item), "已增加技能行", item.id);
  });
  currentSection.items.forEach((item, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "skill-item";
    wrapper.append(editable("div", "skill-text", item.content, (value) => { item.content = value; }, {
      placeholder: "填写技能",
      editId: item.id,
    }));
    wrapper.append(tools([
      {label: "↑", title: "上移", disabled: index === 0, run: () => mutate(() => moveItem(currentSection.items, index, -1), "已上移")},
      {label: "↓", title: "下移", disabled: index === currentSection.items.length - 1, run: () => mutate(() => moveItem(currentSection.items, index, 1), "已下移")},
      {label: "×", title: "删除", className: "danger", run: () => mutate(() => currentSection.items.splice(index, 1), "已删除技能行")},
    ]));
    contentRoot.append(wrapper);
  });
}

function renderBullets(entry, prefix) {
  entry.bullets.forEach((bullet, index) => {
    const row = document.createElement("div");
    row.className = "resume-bullet";
    row.append(editable("div", "bullet-text", bullet.content, (value) => { bullet.content = value; }, {
      placeholder: "填写经历要点",
      editId: bullet.id,
    }));
    row.append(tools([
      {label: "↑", title: "上移要点", disabled: index === 0, run: () => mutate(() => moveItem(entry.bullets, index, -1), "已上移要点")},
      {label: "↓", title: "下移要点", disabled: index === entry.bullets.length - 1, run: () => mutate(() => moveItem(entry.bullets, index, 1), "已下移要点")},
      {label: "×", title: "删除要点", className: "danger", run: () => mutate(() => entry.bullets.splice(index, 1), "已删除要点")},
    ]));
    row.dataset.parent = prefix;
    contentRoot.append(row);
  });
}

function entryTools(items, entry, index, label) {
  return tools([
    {
      label: "+",
      title: "增加要点",
      run: () => {
        const bullet = {id: newId("bullet"), content: "请填写新的经历要点"};
        mutate(() => entry.bullets.push(bullet), "已增加要点", bullet.id);
      },
    },
    {label: "↑", title: `上移${label}`, disabled: index === 0, run: () => mutate(() => moveItem(items, index, -1), `已上移${label}`)},
    {label: "↓", title: `下移${label}`, disabled: index === items.length - 1, run: () => mutate(() => moveItem(items, index, 1), `已下移${label}`)},
    {
      label: "×",
      title: `删除${label}`,
      className: "danger",
      run: async () => {
        if (await askInPage(`删除这段${label}？可使用“上一步”恢复。`)) mutate(() => items.splice(index, 1), `已删除${label}`);
      },
    },
  ]);
}

function renderExperience(currentSection) {
  renderSectionHeading(currentSection, "增加工作或实习经历", () => {
    const entry = {id: newId("experience"), organization: "", role: "", date: "", bullets: []};
    mutate(() => currentSection.items.push(entry), "已增加经历", `${entry.id}-organization`);
  });
  currentSection.items.forEach((entry, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "entry";
    const header = document.createElement("div");
    header.className = "entry-header experience-header";
    header.append(
      editable("div", "", entry.organization, (value) => { entry.organization = value; }, {placeholder: "公司名称", editId: `${entry.id}-organization`}),
      editable("div", "", entry.role, (value) => { entry.role = value; }, {placeholder: "职位名称", editId: `${entry.id}-role`}),
      editable("div", "entry-date", entry.date, (value) => { entry.date = value; }, {placeholder: "起止时间", editId: `${entry.id}-date`}),
    );
    header.append(entryTools(currentSection.items, entry, index, "经历"));
    wrapper.append(header);
    contentRoot.append(wrapper);
    renderBullets(entry, entry.id);
  });
}

function renderProjects(currentSection) {
  renderSectionHeading(currentSection, "增加项目经历", () => {
    const entry = {id: newId("project"), title: "", responsibility: "", date: "", bullets: []};
    mutate(() => currentSection.items.push(entry), "已增加项目", `${entry.id}-title`);
  });
  currentSection.items.forEach((entry, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "entry";
    const header = document.createElement("div");
    header.className = "entry-header project-header";
    header.append(
      editable("div", "", entry.title, (value) => { entry.title = value; }, {placeholder: "项目名称", editId: `${entry.id}-title`}),
      editable("div", "entry-responsibility", entry.responsibility, (value) => { entry.responsibility = value; }, {placeholder: "项目职责", editId: `${entry.id}-responsibility`}),
      editable("div", "entry-date optional-date", entry.date, (value) => { entry.date = value; }, {placeholder: "起止时间", editId: `${entry.id}-date`}),
    );
    header.append(entryTools(currentSection.items, entry, index, "项目"));
    wrapper.append(header);
    contentRoot.append(wrapper);
    renderBullets(entry, entry.id);
  });
}

function renderEducation(currentSection) {
  renderSectionHeading(currentSection, "增加教育经历", () => {
    const entry = {id: newId("education"), school: "学校名称", major: "专业名称", date: "起止时间", bullets: []};
    mutate(() => currentSection.items.push(entry), "已增加教育经历", `${entry.id}-school`);
  });
  currentSection.items.forEach((entry, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "entry";
    const header = document.createElement("div");
    header.className = "entry-header education-header";
    header.append(
      editable("div", "", entry.school, (value) => { entry.school = value; }, {placeholder: "学校名称", editId: `${entry.id}-school`}),
      editable("div", "", entry.major, (value) => { entry.major = value; }, {placeholder: "专业名称", editId: `${entry.id}-major`}),
      editable("div", "entry-date", entry.date, (value) => { entry.date = value; }, {placeholder: "起止时间", editId: `${entry.id}-date`}),
    );
    header.append(entryTools(currentSection.items, entry, index, "教育"));
    wrapper.append(header);
    contentRoot.append(wrapper);
    renderBullets(entry, entry.id);
  });
}

function render() {
  paper.replaceChildren();
  paper.style.setProperty("--fit-scale", "1");
  contentRoot = document.createElement("div");
  contentRoot.className = "resume-content";
  paper.append(contentRoot);
  renderHeader();
  renderSkills(section("skills"));
  renderExperience(section("experience"));
  renderProjects(section("projects"));
  renderEducation(section("education"));
  requestAnimationFrame(() => {
    updatePageStatus();
    if (focusAfterRender) {
      const target = paper.querySelector(`[data-edit-id="${CSS.escape(focusAfterRender)}"]`);
      focusAfterRender = null;
      target?.focus();
    }
  });
}

function updatePageStatus() {
  if (!contentRoot) return;
  const paperStyle = getComputedStyle(paper);
  const availableHeight = paper.clientHeight - parseFloat(paperStyle.paddingTop) - parseFloat(paperStyle.paddingBottom);
  let low = 0.05;
  let high = 2;
  let best = low;
  for (let iteration = 0; iteration < 11; iteration += 1) {
    const candidate = (low + high) / 2;
    paper.style.setProperty("--fit-factor", candidate.toFixed(4));
    paper.style.setProperty("--resume-body-size", `${12.25 * candidate}px`);
    paper.style.setProperty("--resume-entry-size", `${12.75 * candidate}px`);
    paper.style.setProperty("--resume-date-size", `${12.75 * candidate}px`);
    paper.style.setProperty("--fit-scale", candidate.toFixed(4));
    const height = contentRoot.scrollHeight;
    if (height <= availableHeight) {
      best = candidate;
      low = candidate;
    } else {
      high = candidate;
    }
  }
  const scale = Math.floor(best * 200) / 200;
  paper.style.setProperty("--fit-factor", String(scale));
  paper.style.setProperty("--resume-body-size", `${12.25 * scale}px`);
  paper.style.setProperty("--resume-entry-size", `${12.75 * scale}px`);
  paper.style.setProperty("--resume-date-size", `${12.75 * scale}px`);
  paper.style.setProperty("--fit-scale", String(scale));
  const overflowPixels = Math.max(0, paper.scrollHeight - paper.clientHeight);
  lastOverflowPixels = overflowPixels;
  if (overflowPixels > 2) {
    const millimeters = Math.ceil(overflowPixels * 25.4 / 96);
    pageStatus.textContent = `缩放${Math.round(scale * 100)}% · 超出 A4 约 ${millimeters} mm`;
    pageStatus.classList.add("overflow");
  } else {
    pageStatus.textContent = `缩放${Math.round(scale * 100)}%`;
    pageStatus.classList.remove("overflow");
  }
}

function rememberSelection() {
  const selection = window.getSelection();
  if (selection?.rangeCount) {
    const range = selection.getRangeAt(0);
    if (paper.contains(range.commonAncestorContainer)) {
      savedRange = range.cloneRange();
      activeEditable = (range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
        ? range.commonAncestorContainer
        : range.commonAncestorContainer.parentElement)?.closest(".editable") || activeEditable;
    }
  }
}

function restoreSelection() {
  if (!savedRange) return;
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(savedRange);
}

function syncActiveEditable() {
  if (!activeEditable?.isConnected) return;
  activeEditable.dispatchEvent(new Event("input", {bubbles: true}));
}

function applyCommand(command, value = null) {
  if (editorLocked) return;
  restoreSelection();
  document.execCommand(command, false, value);
  syncActiveEditable();
}

function applyAlignment(alignment) {
  if (editorLocked) return;
  restoreSelection();
  const target = activeEditable?.isConnected ? activeEditable : null;
  if (!target) return;
  checkpoint();
  target.style.textAlign = alignment;
  resume.formatting[target.dataset.editId] = {textAlign: alignment};
  queueSave();
}

function download(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function createPdfArtifact() {
  if (!window.html2canvas || !window.jspdf?.jsPDF) throw new Error("PDF 组件未加载");
  document.body.classList.add("pdf-rendering");
  try {
    const canvas = await window.html2canvas(paper, {scale: 2, useCORS: true, backgroundColor: "#ffffff"});
    const pdf = new window.jspdf.jsPDF({orientation: "portrait", unit: "mm", format: "a4", compress: true});
    pdf.addImage(canvas.toDataURL("image/jpeg", 0.92), "JPEG", 0, 0, 210, 297, undefined, "FAST");
    const fileName = `简历-${new Date().toISOString().slice(0, 10)}.pdf`;
    return {blob: pdf.output("blob"), fileName};
  } finally {
    document.body.classList.remove("pdf-rendering");
  }
}

function downloadBlob(fileName, blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function commitPendingVersion() {
  if (!pendingVersion || editorLocked) return;
  const pending = pendingVersion;
  lockEditor(true);
  try {
    const {data: result} = await requestBackend("/api/editor/versions", {method: "POST", data: pending.body});
    if (pending.downloadLocal) downloadBlob(pending.artifact.fileName, pending.artifact.blob);
    pendingVersion = null;
    document.getElementById('versionRetry').hidden = true;
    setStatus("已保存"); showToast(`已保存版本：${result.name}`);
    return result;
  } catch (error) {
    document.getElementById('versionRetry').hidden = false;
    document.getElementById('versionRetryMessage').textContent = `版本“${pending.body.name}”尚未确认保存成功：${error.message}`;
    setStatus("版本保存未完成，可重试同一次请求", "error");
    throw error;
  } finally { lockEditor(false); }
}

async function saveVersionToCloud(name, options = {}) {
  if (editorLocked) throw new Error("正在处理，请稍候");
  if (pendingVersion) throw new Error("请先处理上一次版本保存");
  const cleanName = String(name || "").trim();
  if (!cleanName) throw new Error("请填写版本名称");
  lockEditor(true);
  try {
    await flushSave();
    await document.fonts.ready;
    updatePageStatus();
    if (lastOverflowPixels > 2) throw new Error("内容超出 A4，请缩减内容或调整格式后再保存 PDF");
    const frozen = clone(resume), frozenRevision = revision;
    const artifact = await createPdfArtifact();
    const pdfBase64 = await new Promise((resolve, reject) => {
      const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1]);
      reader.onerror = () => reject(new Error('PDF 读取失败')); reader.readAsDataURL(artifact.blob);
    });
    pendingVersion = {body: {name: cleanName, document: frozen, expected_revision: frozenRevision,
      pdf_base64: pdfBase64, idempotency_key: crypto.randomUUID()}, artifact, downloadLocal: options.downloadLocal};
  } finally { lockEditor(false); }
  return commitPendingVersion();
}

async function exportPdfAndArchive(name) {
  return saveVersionToCloud(name, {downloadLocal: true});
}

function documentText(doc) {
  const lines = [textOf(doc.profile.name), ...doc.profile.contacts.map(item => textOf(item.content))];
  for (const section of doc.sections) {
    lines.push('', textOf(section.title));
    for (const item of section.items) {
      const fields = ['organization', 'role', 'title', 'responsibility', 'school', 'major', 'date', 'content'];
      lines.push(fields.filter(key => item[key]).map(key => textOf(item[key])).join(' · '));
      for (const bullet of item.bullets || []) lines.push('• ' + textOf(bullet.content));
    }
  }
  return lines.join('\n');
}

function textOf(html) {
  const holder = document.createElement("div");
  holder.innerHTML = sanitizeHTML(html);
  return holder.textContent.trim();
}

function markdownExport() {
  const identity = resume.profile.contacts.filter((item) => item.kind !== "link").map((item) => textOf(item.content));
  const links = resume.profile.contacts.filter((item) => item.kind === "link").map((item) => textOf(item.content));
  const lines = [`# ${textOf(resume.profile.name)}`, identity.join(" ｜ "), ...(links.length ? [links.join(" ｜ ")] : []), ""];
  for (const currentSection of resume.sections) {
    lines.push(`## ${textOf(currentSection.title)}`, "");
    if (currentSection.type === "skills") {
      currentSection.items.forEach((item) => lines.push(`- ${textOf(item.content)}`));
    } else {
      currentSection.items.forEach((item) => {
        if (currentSection.type === "experience") lines.push(`### ${textOf(item.organization)} | ${textOf(item.role)} | ${textOf(item.date)}`);
        if (currentSection.type === "projects") {
          const title = textOf(item.title);
          const responsibility = textOf(item.responsibility);
          const date = textOf(item.date);
          const fields = [title, responsibility, date];
          while (fields.length && !fields.at(-1)) fields.pop();
          lines.push(`### ${fields.join(" | ")}`);
        }
        if (currentSection.type === "education") lines.push(`### ${textOf(item.school)} | ${textOf(item.major)} | ${textOf(item.date)}`);
        item.bullets.forEach((bullet) => lines.push(`- ${textOf(bullet.content)}`));
        lines.push("");
      });
    }
    lines.push("");
  }
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

async function refreshVersions() {
  versionList.innerHTML = '<div class="empty-state">正在读取…</div>';
  try {
    const {data: payload} = await requestBackend("/api/editor/versions", {cache: "no-store"});
    const versions = Array.isArray(payload?.versions) ? payload.versions : [];
    versionList.replaceChildren();
    if (!versions.length) {
      versionList.innerHTML = '<div class="empty-state">还没有手动保存的版本</div>';
      return;
    }
    versions.forEach((version) => {
      const row = document.createElement("div");
      row.className = "version-row";
      const info = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = version.name;
      const time = document.createElement("time");
      time.textContent = new Date(version.createdAt).toLocaleString("zh-CN", {
        year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
      });
      info.append(name, time);
      const actions = document.createElement("div");
      actions.className = "version-actions";
      actions.append(
        button("下载 PDF", "下载这个历史版本的 PDF", () => downloadHistoricalPdf(version.id)),
        button("恢复", "恢复这个版本", () => restoreHistoricalVersion(version)),
        button("删除", "删除这个历史版本", () => deleteHistoricalVersion(version), "danger"),
      );
      row.append(info, actions);
      versionList.append(row);
    });
  } catch (error) {
    versionList.innerHTML = `<div class="empty-state">读取失败：${error.message}</div>`;
  }
}

async function getHistoricalVersion(id) {
  const {data: version} = await requestBackend(`/api/editor/versions/${id}`, {cache: "no-store"});
  if (!version?.document) throw new Error("历史版本数据不完整");
  return version;
}

async function downloadHistoricalPdf(id) {
  try {
    const version = await getHistoricalVersion(id);
    const response = await fetch(`/api/artifacts/${version.artifact_id}?download=true`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    downloadBlob(`简历-${version.name}.pdf`, await response.blob());
    showToast(`已下载：${version.name}`);
  } catch (error) {
    showToast(`PDF 下载失败：${error.message}`);
  }
}

async function deleteHistoricalVersion(version) {
  const confirmed = await askInPage(`确认删除版本“${version.name}”？删除后不能恢复。`, false);
  if (!confirmed) return;
  try {
    await requestBackend(`/api/editor/versions/${encodeURIComponent(version.id)}`, {method: "DELETE"});
    await refreshVersions();
    showToast(`已删除版本：${version.name}`);
  } catch (error) {
    showToast(`删除失败：${error.message}`);
  }
}

function chooseRestoreAction(versionName) {
  restoreDialogMessage.textContent = `恢复“${versionName}”前，当前内容如何处理？`;
  restoreDialog.showModal();
  return new Promise((resolve) => {
    const finish = (choice) => {
      restoreDialog.close();
      resolve(choice);
    };
    document.getElementById("discardCurrent").onclick = () => finish("discard");
    document.getElementById("saveCurrent").onclick = () => finish("save");
    document.getElementById("cancelRestore").onclick = () => finish("cancel");
    restoreDialog.oncancel = (event) => {
      event.preventDefault();
      finish("cancel");
    };
  });
}

async function applyHistoricalVersion(version) {
  if (editorLocked || pendingVersion) throw new Error("请先完成当前版本保存");
  lockEditor(true);
  try {
    // Persist the pre-restore draft so its recovery point includes the latest edit.
    await flushSave();
    const {data: payload} = await requestBackend("/api/editor/restore", {
      method: "POST", data: {version_id: version.id, expected_revision: revision},
    });
    checkpoint(); resume = normalizeDocument(payload.document);
    activeEditable = null; localChangePending = false;
    revision = payload.revision; savedSnapshot = snapshot();
    render(); updateHistoryButtons(); setStatus("已恢复并保存");
  } finally { lockEditor(false); }
}

async function restoreHistoricalVersion(versionSummary) {
  versionDialog.close();
  const choice = await chooseRestoreAction(versionSummary.name);
  if (choice === "cancel") {
    versionDialog.showModal();
    await refreshVersions();
    return;
  }
  try {
    if (choice === "save") {
      const currentName = await askInPage("给当前版本起一个名称", true);
      if (!currentName) {
        versionDialog.showModal();
        await refreshVersions();
        return;
      }
      await saveVersionToCloud(currentName, {silent: true});
    }
    const version = await getHistoricalVersion(versionSummary.id);
    await applyHistoricalVersion(version);
    showToast(`已恢复：${version.name}`);
  } catch (error) {
    versionDialog.showModal();
    await refreshVersions();
    showToast(`恢复失败：${error.message}`);
  }
}

function sourceScopeLabel(source) {
  if (source.scope_type === "job") return "当前机会";
  if (source.scope_type === "personal") return "个人资料";
  return ({episode: "任职记录", org: "组织"})[source.scope_type] || "其他范围";
}

function sourceWikiHref(source) {
  if (source.source_kind === "profile" || source.source_id === "profile") return "/#profile";
  const id = source.source_id || source.id;
  return `/#wiki/${encodeURIComponent(id || "")}`;
}

function sourceStatusLabel(status) {
  return ({current: "当前", updated: "有新版本", withdrawn: "已撤回", removed: "已移除"})[status] || status || "未知";
}

async function refreshSources() {
  sourcesList.innerHTML = '<div class="empty-state">正在读取…</div>';
  try {
    const {data} = await requestBackend("/api/editor/sources", {cache: "no-store"});
    const sources = Array.isArray(data?.sources) ? data.sources : [];
    sourcesList.replaceChildren();
    if (!sources.length) {
      sourcesList.innerHTML = '<div class="empty-state">当前工作稿还没有材料来源</div>';
      return;
    }
    sources.forEach((source) => {
      const row = document.createElement("article");
      row.className = "source-row";
      const title = document.createElement("strong");
      title.textContent = source.title || source.source_id || "未命名来源";
      const meta = document.createElement("span");
      meta.textContent = `v${source.revision ?? "?"} · ${sourceStatusLabel(source.status)}${sourceScopeLabel(source) ? ` · ${sourceScopeLabel(source)}` : ""}`;
      const link = document.createElement("a");
      link.href = sourceWikiHref(source);
      link.textContent = source.source_kind === "profile" ? "查看基础资料 →" : "查看 Wiki 来源 →";
      link.target = "_blank";
      link.rel = "noopener";
      row.append(title, meta, link);
      sourcesList.append(row);
    });
  } catch (error) {
    sourcesList.replaceChildren();
    const message = document.createElement("div");
    message.className = "empty-state";
    message.textContent = `读取失败：${error.message}`;
    sourcesList.append(message);
  }
}

const materialTypeNames = {skill: "技能", skills: "技能", capability: "能力", experience: "经历", project: "项目", projects: "项目", education: "教育", goal: "目标", constraint: "限制", achievement: "成果", strategy: "策略", person: "人物", growth: "成长"};
const selectedMaterials = () => [...materialsList.querySelectorAll(".material-choice")].flatMap((row) => {
  const input = row.querySelector("input[data-material-id]");
  if (input?.checked) return [{id: input.dataset.materialId, revision: input.dataset.materialRevision, section: row.querySelector("select")?.value || ""}];
  const profile = row.querySelector("input[data-profile]");
  return profile?.checked ? [{profile: true, revision: profile.dataset.profileRevision}] : [];
});

function setMaterialsBusy(value) {
  materialsBusy = value;
  ["reloadMaterials", "cancelMaterials", "importMaterials"].forEach((id) => { const button = document.getElementById(id); if (button) button.disabled = value; });
  const close = materialsDialog.querySelector(".dialog-head button");
  if (close) close.disabled = value;
  materialsList.inert = value;
  materialsDialog.setAttribute("aria-busy", String(value));
}

function materialTitle(entry) {
  return entry.title || entry.name || entry.content?.slice?.(0, 80) || entry.id || "未命名条目";
}

function renderMaterials(payload) {
  const entries = Array.isArray(payload?.entries) ? payload.entries : [];
  const profile = payload?.profile;
  document.getElementById("materialsScope").textContent = "当前机会与个人资料";
  materialsList.replaceChildren();
  if (!entries.length && !(profile && (profile.mode === "structured" || profile.structured === true || profile.basics))) {
    materialsList.innerHTML = '<div class="empty-state">没有可选的当前 Wiki 条目</div>';
    return;
  }
  entries.forEach((entry) => {
    const row = document.createElement("label");
    row.className = "material-choice";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.dataset.materialId = entry.id || "";
    checkbox.dataset.materialRevision = String(entry.revision ?? "");
    const text = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = materialTitle(entry);
    const detail = document.createElement("small");
    detail.textContent = `${materialTypeNames[entry.entry_type || entry.type] || "Wiki条目"} · v${entry.revision ?? "?"}${entry.scope_type ? ` · ${sourceScopeLabel(entry)}` : ""}`;
    const section = document.createElement("select");
    section.setAttribute("aria-label", `选择“${materialTitle(entry)}”导入分区`);
    SECTION_TYPES.forEach((type) => { const option = document.createElement("option"); option.value = type; option.textContent = SECTION_NAMES[type]; section.append(option); });
    section.value = ["skill", "skills", "capability"].includes(entry.entry_type) ? "skills" : entry.entry_type === "project" ? "projects" : entry.entry_type === "education" ? "education" : "experience";
    const content = document.createElement("p");
    content.className = "material-content";
    content.textContent = entry.content || entry.summary || entry.description || "暂无正文";
    text.append(title, detail, content);
    row.append(checkbox, text, section);
    materialsList.append(row);
  });
  if (profile && (profile.mode === "structured" || profile.structured === true || profile.basics)) {
    const row = document.createElement("label");
    row.className = "material-choice profile-choice";
    const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.dataset.profile = "true";
    const text = document.createElement("span");
    const title = document.createElement("strong"); title.textContent = "基础资料";
    const detail = document.createElement("small"); detail.textContent = `结构化资料 · v${profile.revision ?? "?"}`;
    checkbox.dataset.profileRevision = String(profile.revision ?? "");
    text.append(title, detail); row.append(checkbox, text); materialsList.prepend(row);
  }
}

async function openMaterials() {
  if (materialsBusy) return;
  const previous = selectedMaterials();
  materialsList.innerHTML = '<div class="empty-state">正在读取…</div>';
  if (!materialsDialog.open) materialsDialog.showModal();
  try {
    const query = editorJobId ? `?job_id=${encodeURIComponent(editorJobId)}` : "";
    const {data} = await requestBackend(`/api/editor/materials${query}`, {cache: "no-store"});
    renderMaterials(data);
    const previousById = new Map(previous.map((item) => [item.profile ? "profile" : item.id, item]));
    materialsList.querySelectorAll(".material-choice").forEach((row) => {
      const input = row.querySelector("input");
      const old = previousById.get(input.dataset.profile ? "profile" : input.dataset.materialId);
      if (!old) return;
      input.checked = true;
      if (old.section && row.querySelector("select")) row.querySelector("select").value = old.section;
    });
  } catch (error) {
    materialsList.replaceChildren();
    const message = document.createElement("div");
    message.className = "empty-state";
    message.textContent = `读取失败：${error.message}`;
    materialsList.append(message);
  }
}

async function importMaterials() {
  if (editorLocked || materialsBusy) return;
  const selections = [...materialsList.querySelectorAll("input[data-material-id]:checked")].map((input) => ({
    id: input.dataset.materialId,
    revision: Number(input.dataset.materialRevision),
    section_type: input.closest(".material-choice").querySelector("select").value,
  }));
  const profileInput = materialsList.querySelector("input[data-profile]:checked");
  if (!selections.length && !profileInput) { showToast("请至少选择一条 Wiki 条目或基础资料"); return; }
  const selectionFingerprint = JSON.stringify({job_id: editorJobId, selections, include_profile: Boolean(profileInput), profile_revision: profileInput?.dataset.profileRevision || null});
  setMaterialsBusy(true);
  try {
    const canRetry = materialsRequest?.selectionFingerprint === selectionFingerprint
      && materialsRequest.body?.expected_revision === revision
      && !localChangePending && snapshot() === savedSnapshot;
    let body;
    if (canRetry) {
      // A lost response must replay the exact request. Do not flush again:
      // that would advance the CAS revision and invalidate the idempotent key.
      body = materialsRequest.body;
    } else {
      await flushSave();
      body = {expected_revision: revision, selections, include_profile: Boolean(profileInput)};
      if (editorJobId) body.job_id = editorJobId;
      if (profileInput) body.profile_revision = Number(profileInput.dataset.profileRevision || 0);
      materialsRequest = {
        selectionFingerprint,
        body: {...body, idempotency_key: globalThis.crypto?.randomUUID?.() || `editor-select-${Date.now()}`},
      };
      body = materialsRequest.body;
    }
    lockEditor(true);
    checkpoint();
    const {data} = await requestBackend("/api/editor/select-facts", {method: "POST", data: body});
    resume = normalizeDocument(data.document);
    revision = Number(data.revision);
    lastCloudSavedAt = data.savedAt || null;
    savedSnapshot = snapshot();
    localChangePending = false; conflictState = null; activeEditable = null;
    render(); updateHistoryButtons(); setStatus("已从 Wiki 导入并保存");
    materialsDialog.close();
    materialsRequest = null;
    await refreshSources();
  } catch (error) {
    if (error.status === 409 && conflictState) showToast("草稿保存冲突，请先处理冲突对话框；当前材料勾选已保留");
    else if (error.status === 409) {
      try {
        const latest = await requestBackend("/api/editor", {cache: "no-store"});
        if (latest.data.revision > revision) {
          conflictState = {server: latest.data.document, revision: latest.data.revision};
          materialsRequest = null;
          showConflict();
          showToast("草稿已被其它窗口更新，请先处理冲突；当前材料勾选已保留");
        } else showToast("材料已更新。当前勾选已保留，请点击“重新读取”确认后再导入");
      } catch (readError) { showToast(`无法读取最新草稿：${readError.message}`); }
    }
    else setStatus(`导入失败：${error.message}`, "error");
  } finally { lockEditor(false); setMaterialsBusy(false); }
}

function wireToolbar() {
  undoButton.addEventListener("click", undo);
  redoButton.addEventListener("click", redo);
  document.getElementById("exportMarkdown").addEventListener("click", () => download("resume.md", markdownExport(), "text/markdown; charset=utf-8"));
  document.getElementById("exportJson").addEventListener("click", () => download("resume.json", JSON.stringify(resume, null, 2), "application/json"));
  document.getElementById("saveDraft").onclick = () => { flushSave().catch(error => setStatus(error.message, "error")); };
  document.getElementById("openMaterials").onclick = () => { openMaterials().catch((error) => showToast(error.message)); };
  document.getElementById("reloadMaterials").onclick = () => { if (!materialsBusy) { materialsRequest = null; openMaterials().catch((error) => showToast(error.message)); } };
  document.getElementById("cancelMaterials").onclick = () => { if (!materialsBusy) materialsDialog.close(); };
  document.getElementById("importMaterials").onclick = () => { importMaterials().catch((error) => showToast(error.message)); };
  materialsDialog.addEventListener("cancel", (event) => { if (materialsBusy) event.preventDefault(); });
  document.getElementById("openSources").onclick = async () => { sourcesDialog.showModal(); await refreshSources(); };
  document.getElementById("retryVersion").onclick = () => { commitPendingVersion().catch(() => {}); };
  document.getElementById("cancelVersion").onclick = () => { pendingVersion = null; document.getElementById("versionRetry").hidden = true; lockEditor(false); };
  document.getElementById("captureFeedback").addEventListener("click", () => {
    const dialog = document.createElement("dialog"); dialog.className = "feedback-dialog";
    dialog.innerHTML = '<form><h2>记录反馈</h2><label>你的反馈<textarea required></textarea></label><p role="status"></p><button type="button">取消</button><button type="submit">保存反馈</button></form>';
    document.body.append(dialog); dialog.showModal();
    dialog.querySelector('[type="button"]').onclick = () => dialog.close();
    dialog.addEventListener('close', () => dialog.remove());
    dialog.querySelector('form').onsubmit = async event => {
      event.preventDefault(); const text = dialog.querySelector('textarea').value;
      if (!text.trim()) return;
      const submit = dialog.querySelector('[type="submit"]'); submit.disabled = true;
      try { await requestBackend('/api/feedback', {method: 'POST', data: {text, current_page: 'editor', entity_id: 'editor-main'}}); dialog.close(); showToast('反馈已保存'); }
      catch (error) { dialog.querySelector('[role="status"]').textContent = error.message; submit.disabled = false; }
    };
  });
  document.getElementById("saveVersion").addEventListener("click", async () => {
    const name = await askInPage("给当前版本起一个名称", true);
    if (!name) return;
    try { await saveVersionToCloud(name); } catch (error) { showToast(`保存版本失败：${error.message}`); }
  });
  document.getElementById("openVersions").addEventListener("click", async () => {
    versionDialog.showModal();
    await refreshVersions();
  });
  document.getElementById("exportPdf").addEventListener("click", async () => {
    updatePageStatus();
    if (lastOverflowPixels > 2) { showToast("内容超出 A4，请调整后再导出"); return; }
    const name = await askInPage("给这个 PDF 版本起一个名称", true);
    if (!name) return;
    exportPdfAndArchive(name).catch((error) => showToast(error.message));
  });
  document.addEventListener("selectionchange", () => {
    const selection = window.getSelection();
    if (selection?.rangeCount && paper.contains(selection.anchorNode)) rememberSelection();
  });
  paper.addEventListener("click", (event) => {
    if (event.target.closest(".item-tools")) return;
    paper.querySelectorAll(".item-tools.is-open").forEach((element) => element.classList.remove("is-open"));
    paper.querySelectorAll(".is-selected").forEach((element) => element.classList.remove("is-selected"));
    event.target.closest(".section-heading, .skill-item, .entry, .resume-bullet, .contact-item")?.classList.add("is-selected");
  });
  document.addEventListener("click", (event) => {
    if (paper.contains(event.target)) return;
    paper.querySelectorAll(".is-selected").forEach((element) => element.classList.remove("is-selected"));
  });
  document.addEventListener("keydown", (event) => {
    if (editorLocked) { event.preventDefault(); return; }
    if (event.metaKey && !event.altKey && !event.shiftKey) {
      const alignments = {ArrowLeft: "left", ArrowRight: "right", ArrowDown: "center"};
      if (event.key === "b") {
        event.preventDefault();
        applyCommand("bold");
        return;
      }
      if (alignments[event.key]) {
        event.preventDefault();
        applyAlignment(alignments[event.key]);
        return;
      }
    }
    if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "z") return;
    event.preventDefault();
    if (event.shiftKey) redo(); else undo();
  });
  window.addEventListener("resize", updatePageStatus);

}

function registerWebMCP() {
  const context = document.modelContext;
  if (!context?.registerTool) return;
  const lifecycle = new AbortController();
  const register = (tool) => Promise.resolve(context.registerTool(tool, {signal: lifecycle.signal})).catch(() => {});
  register({
    name: "read_resume_document",
    title: "读取当前简历",
    description: "读取编辑器中的当前结构化简历内容（可能有尚未保存的修改），用于检查或提出建议。",
    inputSchema: {type: "object", properties: {}, additionalProperties: false},
    annotations: {readOnlyHint: true, untrustedContentHint: true},
    execute() { return clone(resume); },
  });

}

async function start() {
  wireToolbar();
  const backLink = document.querySelector(".back-link");
  if (backLink) backLink.href = editorJobId ? `/#jobs/${encodeURIComponent(editorJobId)}?tab=resume` : "/#resume";
  try {
    const {data: payload} = await requestBackend("/api/editor", {cache: "no-store"});
    const initial = payload?.document;
    if (payload?.revision === 0 && !initial.profile.contacts.length) delete initial.profile.contacts;
    resume = normalizeDocument(initial);
    revision = Number(payload?.revision || 0);
    savedSnapshot = snapshot();
    lastCloudSavedAt = payload?.savedAt || null;
    render();
    setStatus(revision === 0 ? "空白工作稿 · 尚未保存" : "已保存");
    updateHistoryButtons();
    refreshSources().catch(() => {});
    registerWebMCP();
  } catch (error) {
    setStatus(`载入失败：${error.message}`, "error");
    paper.innerHTML = '<div class="empty-state">简历数据载入失败，请确认本地服务正常后刷新。</div>';
  }
}

if (location.protocol !== "file:") start();

window.addEventListener("beforeunload", (event) => {
  if (localChangePending || conflictState || editorLocked || pendingVersion) { event.preventDefault(); event.returnValue = "当前内容尚未保存"; }
});
