import { describe, expect, it } from "vitest";

import { envFirst } from "./brand";

describe("envFirst", () => {
  it("环境变量非空时优先", () => {
    expect(envFirst("ICP-2026", "后台值")).toBe("ICP-2026");
  });
  it("环境变量为空时回退后台值", () => {
    expect(envFirst("", "后台值")).toBe("后台值");
  });
});
