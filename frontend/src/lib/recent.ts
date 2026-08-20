import type { LinkOut } from "../api/types";

const RECENT_KEY = "lipanel-recent";
export const MAX_RECENT = 8;

export interface RecentItem {
  id: number;
  opened_at: number;
}

export function getRecent(): RecentItem[] {
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (item): item is RecentItem =>
          typeof item === "object" &&
          item !== null &&
          typeof (item as RecentItem).id === "number",
      )
      .slice(0, MAX_RECENT);
  } catch {
    return [];
  }
}

export function recordRecent(link: Pick<LinkOut, "id">): RecentItem[] {
  const next: RecentItem[] = [
    { id: link.id, opened_at: Date.now() },
    ...getRecent().filter((item) => item.id !== link.id),
  ].slice(0, MAX_RECENT);
  try {
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* localStorage 不可用时忽略 */
  }
  return next;
}

export function clearRecent(): void {
  try {
    window.localStorage.removeItem(RECENT_KEY);
  } catch {
    /* 忽略 */
  }
}
