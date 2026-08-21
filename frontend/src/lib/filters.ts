/**
 * 快捷方式筛选条件（2026-08-22）：
 * 关键词 + 多标签（OR）+ 分组 + 可见性 + 健康检测开关 的纯函数实现，
 * 与 UI 解耦，供后台管理与面板页共用，便于单元测试。
 */

import type { LinkOut } from "../api/types";

export type ManageVisibility = "all" | "public" | "private";
export type ManageHealthEnabled = "all" | "enabled" | "disabled";
export type ManageGroup = "all" | "ungrouped" | number;

export interface ManageFilterOptions {
  query: string;
  tags: ReadonlySet<string>;
  group: ManageGroup;
  visibility: ManageVisibility;
  healthEnabled: ManageHealthEnabled;
}

/** 关键词匹配：名称 / 描述 / 标签 / 生效地址 / 内网地址 / 外网地址（忽略大小写） */
export function matches(link: LinkOut, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    link.name.toLowerCase().includes(q) ||
    link.description.toLowerCase().includes(q) ||
    link.tags.some((tag) => tag.toLowerCase().includes(q)) ||
    (link.url ?? "").toLowerCase().includes(q) ||
    link.url_lan.toLowerCase().includes(q) ||
    (link.url_wan ?? "").toLowerCase().includes(q)
  );
}

/** 后台管理综合筛选：所有启用条件同时生效；标签多选为「任一命中」语义 */
export function passesManageFilters(
  link: LinkOut,
  opts: ManageFilterOptions,
): boolean {
  if (!matches(link, opts.query)) return false;
  if (opts.tags.size > 0 && !link.tags.some((tag) => opts.tags.has(tag))) {
    return false;
  }
  if (opts.group !== "all") {
    const target = opts.group === "ungrouped" ? null : opts.group;
    if (link.group_id !== target) return false;
  }
  if (
    opts.visibility !== "all" &&
    (opts.visibility === "public") !== link.is_public
  ) {
    return false;
  }
  if (
    opts.healthEnabled !== "all" &&
    (opts.healthEnabled === "enabled") !== link.health_enabled
  ) {
    return false;
  }
  return true;
}
