import { describe, expect, it } from "vitest";

import type { LinkOut } from "../api/types";
import {
  matches,
  passesManageFilters,
  type ManageFilterOptions,
} from "./filters";

function link(overrides: Partial<LinkOut> = {}): LinkOut {
  return {
    id: 1,
    group_id: 1,
    name: "GitHub",
    url_lan: "http://192.168.1.10:3000",
    url_wan: "https://github.com",
    url: "http://192.168.1.10:3000",
    icon_type: "letter",
    icon_value: null,
    description: "代码托管",
    tags: ["dev", "code"],
    is_public: false,
    guest_url_mode: "hidden",
    sort_order: 0,
    open_mode: "new_tab",
    health_enabled: true,
    health_interval: 10,
    health_timeout: 5,
    health_threshold: 1,
    ...overrides,
  };
}

function opts(overrides: Partial<ManageFilterOptions> = {}): ManageFilterOptions {
  return {
    query: "",
    tags: new Set(),
    group: "all",
    visibility: "all",
    healthEnabled: "all",
    ...overrides,
  };
}

describe("matches", () => {
  it("空关键词匹配全部", () => {
    expect(matches(link(), "")).toBe(true);
    expect(matches(link(), "   ")).toBe(true);
  });

  it("匹配名称/描述/标签/生效地址/内网/外网地址，忽略大小写", () => {
    const l = link();
    expect(matches(l, "github")).toBe(true); // 名称
    expect(matches(l, "托管")).toBe(true); // 描述
    expect(matches(l, "DEV")).toBe(true); // 标签（大小写不敏感）
    expect(matches(l, "192.168.1.10")).toBe(true); // 内网地址
    expect(matches(l, "github.com")).toBe(true); // 外网地址
    expect(matches(l, "不存在的词")).toBe(false);
  });
});

describe("passesManageFilters", () => {
  it("默认全部条件通过", () => {
    expect(passesManageFilters(link(), opts())).toBe(true);
  });

  it("多标签为任一命中（OR）", () => {
    expect(passesManageFilters(link({ tags: ["dev", "ops"] }), opts({ tags: new Set(["ops"]) }))).toBe(true);
    expect(passesManageFilters(link({ tags: ["dev"] }), opts({ tags: new Set(["ops"]) }))).toBe(false);
    expect(passesManageFilters(link({ tags: ["dev", "ops"] }), opts({ tags: new Set(["ops", "prod"]) }))).toBe(true);
    expect(passesManageFilters(link(), opts({ tags: new Set() }))).toBe(true);
  });

  it("分组筛选：指定分组与未分组", () => {
    expect(passesManageFilters(link({ group_id: 2 }), opts({ group: 2 }))).toBe(true);
    expect(passesManageFilters(link({ group_id: 1 }), opts({ group: 2 }))).toBe(false);
    expect(passesManageFilters(link({ group_id: null }), opts({ group: "ungrouped" }))).toBe(true);
    expect(passesManageFilters(link({ group_id: 2 }), opts({ group: "ungrouped" }))).toBe(false);
  });

  it("可见性筛选：公开/私密", () => {
    expect(passesManageFilters(link({ is_public: true }), opts({ visibility: "public" }))).toBe(true);
    expect(passesManageFilters(link({ is_public: false }), opts({ visibility: "public" }))).toBe(false);
    expect(passesManageFilters(link({ is_public: false }), opts({ visibility: "private" }))).toBe(true);
  });

  it("健康检测开关筛选", () => {
    expect(passesManageFilters(link({ health_enabled: true }), opts({ healthEnabled: "enabled" }))).toBe(true);
    expect(passesManageFilters(link({ health_enabled: false }), opts({ healthEnabled: "enabled" }))).toBe(false);
    expect(passesManageFilters(link({ health_enabled: false }), opts({ healthEnabled: "disabled" }))).toBe(true);
  });

  it("多条件同时生效", () => {
    const l = link({
      name: "内网 GitLab",
      group_id: 3,
      is_public: true,
      tags: ["dev"],
      health_enabled: false,
    });
    expect(
      passesManageFilters(l, opts({ query: "gitlab", group: 3, visibility: "public", healthEnabled: "disabled", tags: new Set(["dev"]) })),
    ).toBe(true);
    expect(
      passesManageFilters(l, opts({ query: "gitlab", group: 4, visibility: "public", healthEnabled: "disabled", tags: new Set(["dev"]) })),
    ).toBe(false);
  });
});
