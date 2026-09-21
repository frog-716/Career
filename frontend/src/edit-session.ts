export type EditSession = {
  readonly dirty: boolean;
  markSaved: () => void;
};

const formSessions = new WeakMap<HTMLFormElement, EditSession>();
const dialogSessions = new WeakMap<HTMLDialogElement, EditSession[]>();

function snapshot(form: HTMLFormElement): string {
  return JSON.stringify(
    [...new FormData(form).entries()].map(([name, value]) => [
      name,
      typeof value === "string" ? value : `${value.name}:${value.size}:${value.lastModified}`,
    ]),
  );
}

function syncDialog(dialog: HTMLDialogElement) {
  const sessions = dialogSessions.get(dialog) || [];
  const dirty =
    sessions.some((session) => session.dirty) || dialog.dataset.untrackedDirty === "true";
  dialog.dataset.dirty = String(dirty);
}

export function trackForm(dialog: HTMLDialogElement, form: HTMLFormElement): EditSession {
  const existing = formSessions.get(form);
  if (existing) return existing;

  let baseline = snapshot(form);
  const session: EditSession = {
    get dirty() {
      return snapshot(form) !== baseline;
    },
    markSaved() {
      baseline = snapshot(form);
      syncDialog(dialog);
    },
  };
  formSessions.set(form, session);
  const sessions = dialogSessions.get(dialog) || [];
  sessions.push(session);
  dialogSessions.set(dialog, sessions);
  const update = () => syncDialog(dialog);
  form.addEventListener("input", update);
  form.addEventListener("change", update);
  syncDialog(dialog);
  return session;
}

export function trackDialogForms(dialog: HTMLDialogElement): void {
  dialog.querySelectorAll<HTMLFormElement>("form").forEach((form) => trackForm(dialog, form));
}

export function sessionFor(form: HTMLFormElement): EditSession {
  const session = formSessions.get(form);
  if (!session) throw new Error("表单未注册编辑会话");
  return session;
}

export function markUntrackedDialogDirty(dialog: HTMLDialogElement): void {
  dialog.dataset.untrackedDirty = "true";
  syncDialog(dialog);
}

export function markUntrackedDialogClean(dialog: HTMLDialogElement): void {
  delete dialog.dataset.untrackedDirty;
  syncDialog(dialog);
}

export function closeDialogIfAllowed(dialog: HTMLDialogElement): boolean {
  if (dialog.dataset.dirty !== "true") {
    dialog.close();
    return true;
  }
  const discard = window.confirm(
    "当前有未保存输入。点击“确定”放弃未保存内容并关闭，点击“取消”继续编辑。",
  );
  if (!discard) return false;
  dialog.close();
  return true;
}

export function guardOpenDialog(): boolean {
  const dialogs = [...document.querySelectorAll<HTMLDialogElement>("dialog[open]")].reverse();
  for (const dialog of dialogs) {
    if (!closeDialogIfAllowed(dialog)) return false;
  }
  return true;
}
