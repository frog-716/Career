export const SIDEBAR_MODULE_IDS = ["wiki", "jobs", "projects", "resume", "work"] as const;
export type SidebarModuleId = (typeof SIDEBAR_MODULE_IDS)[number];
export interface SidebarPreferenceStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export function isSidebarModuleId(value: unknown): value is SidebarModuleId {
  return typeof value === "string" && (SIDEBAR_MODULE_IDS as readonly string[]).includes(value);
}

export function normalizeSidebarOrder(value: unknown): SidebarModuleId[] {
  const result: SidebarModuleId[] = [];
  const seen = new Set<SidebarModuleId>();
  if (Array.isArray(value)) {
    for (const candidate of value) {
      if (!isSidebarModuleId(candidate) || seen.has(candidate)) continue;
      seen.add(candidate);
      result.push(candidate);
    }
  }
  for (const id of SIDEBAR_MODULE_IDS) {
    if (seen.has(id)) continue;
    seen.add(id);
    result.push(id);
  }
  return result;
}

export function applySidebarPin(order: unknown, pinned: unknown): SidebarModuleId[] {
  const normalized = normalizeSidebarOrder(order);
  return isSidebarModuleId(pinned)
    ? [pinned, ...normalized.filter((id) => id !== pinned)]
    : normalized;
}

export function resolveSidebarHome(pinned: unknown, order: unknown): SidebarModuleId {
  return isSidebarModuleId(pinned)
    ? pinned
    : normalizeSidebarOrder(order)[0];
}

export function persistSidebarPreferences(
  store: SidebarPreferenceStore,
  homeKey: string,
  orderKey: string,
  home: string | null,
  order: readonly SidebarModuleId[],
): boolean {
  let previousHome: string | null = null;
  let previousOrder: string | null = null;
  try {
    previousHome = store.getItem(homeKey);
    previousOrder = store.getItem(orderKey);
    if (home) store.setItem(homeKey, home);
    else store.removeItem(homeKey);
    store.setItem(orderKey, JSON.stringify(normalizeSidebarOrder(order)));
    return true;
  } catch {
    try {
      if (previousHome !== null) store.setItem(homeKey, previousHome);
      else store.removeItem(homeKey);
      if (previousOrder !== null) store.setItem(orderKey, previousOrder);
      else store.removeItem(orderKey);
    } catch { /* a disabled store may reject rollback as well */ }
    return false;
  }
}
