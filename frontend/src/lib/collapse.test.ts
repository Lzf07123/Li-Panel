import { beforeEach, describe, expect, it } from "vitest";

import { loadCollapsedGroups, toggleCollapsedGroup } from "./collapse";

describe("collapse groups", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("loads empty by default", () => {
    expect(loadCollapsedGroups().size).toBe(0);
  });

  it("toggles and persists", () => {
    const next = toggleCollapsedGroup(new Set(), 3);
    expect(next.has(3)).toBe(true);
    expect(loadCollapsedGroups().has(3)).toBe(true);
    const after = toggleCollapsedGroup(next, 3);
    expect(after.has(3)).toBe(false);
  });
});
