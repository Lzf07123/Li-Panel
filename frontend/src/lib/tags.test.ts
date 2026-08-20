import { describe, expect, it } from "vitest";

import { formatTags, parseTags, MAX_TAGS, MAX_TAG_LENGTH } from "./tags";

describe("parseTags", () => {
  it("parses comma-separated tags and trims", () => {
    expect(parseTags(" 开发 , 前端，开发 ")).toEqual(["开发", "前端"]);
  });

  it("dedupes and caps at 8", () => {
    const tags = Array.from({ length: 12 }, (_, i) => `t${i}`);
    expect(parseTags(tags.join(","))).toHaveLength(MAX_TAGS);
  });

  it("caps tag length", () => {
    const tags = parseTags("x".repeat(50));
    expect(tags[0]).toHaveLength(MAX_TAG_LENGTH);
  });
});

describe("formatTags", () => {
  it("joins with comma", () => {
    expect(formatTags(["a", "b"])).toBe("a, b");
  });
});
