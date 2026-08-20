import { describe, expect, it } from "vitest";

import { ACCENT_KEYS, accentFor } from "./accent";

describe("accentFor", () => {
  it("is stable for the same id", () => {
    expect(accentFor("GitHub")).toBe(accentFor("GitHub"));
  });

  it("returns a valid accent key", () => {
    for (const id of ["a", "bb", "ccc", "中文字符"]) {
      expect(ACCENT_KEYS).toContain(accentFor(id));
    }
  });
});
