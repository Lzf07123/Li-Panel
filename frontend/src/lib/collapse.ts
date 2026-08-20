const KEY = "lipanel-collapsed-groups";

export function loadCollapsedGroups(): Set<number> {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((item) => typeof item === "number"));
  } catch {
    return new Set();
  }
}

export function saveCollapsedGroups(groups: Set<number>): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(Array.from(groups)));
  } catch {
    /* localStorage 不可用时忽略 */
  }
}

export function toggleCollapsedGroup(
  current: Set<number>,
  groupId: number,
): Set<number> {
  const next = new Set(current);
  if (next.has(groupId)) {
    next.delete(groupId);
  } else {
    next.add(groupId);
  }
  saveCollapsedGroups(next);
  return next;
}
