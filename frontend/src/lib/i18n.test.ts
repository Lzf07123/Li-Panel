import { describe, expect, it } from "vitest";

import { translate } from "./i18n";

describe("i18n translate", () => {
  it("zh-CN returns original text", () => {
    expect(translate("zh-CN", "登录")).toBe("登录");
  });

  it("en-US returns dictionary value", () => {
    expect(translate("en-US", "登录")).toBe("Sign in");
    expect(translate("en-US", "管理")).toBe("Manage");
  });

  it("unknown key falls back to original", () => {
    expect(translate("en-US", "不存在文案")).toBe("不存在文案");
  });
});
