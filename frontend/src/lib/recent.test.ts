import { beforeEach, describe, expect, it } from "vitest";

import { MAX_RECENT, clearRecent, getRecent, recordRecent } from "./recent";

describe("recent", () => {
  beforeEach(() => {
    clearRecent();
  });

  it("records most recent first and dedupes", () => {
    recordRecent({ id: 1 });
    recordRecent({ id: 2 });
    recordRecent({ id: 1 });
    const items = getRecent();
    expect(items.map((i) => i.id)).toEqual([1, 2]);
  });

  it("caps at MAX_RECENT", () => {
    for (let i = 0; i < MAX_RECENT + 5; i += 1) {
      recordRecent({ id: i });
    }
    expect(getRecent()).toHaveLength(MAX_RECENT);
  });
});
