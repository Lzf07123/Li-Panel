import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { authApi, healthApi, linksApi, panelApi, rssApi } from "../api/client";
import type { LinkOut, MeOut, PanelOut } from "../api/types";
import { clearRecent, getRecent, recordRecent, type RecentItem } from "../lib/recent";
import { loadCollapsedGroups, toggleCollapsedGroup } from "../lib/collapse";
import { matches } from "../lib/filters";
import { AppHeader } from "../components/AppHeader";
import {
  CLIENT_PROBE_INTERVAL_MS,
  SERVER_STATUS_INTERVAL_MS,
  loadProbeCache,
  probeFromClient,
  pruneProbeCache,
  saveProbeCache,
} from "../lib/probe";
import { Brand } from "../components/Brand";
import { CommandPalette } from "../components/CommandPalette";
import { DateTimeWidget } from "../components/DateTimeWidget";
import { GroupIcon, isGroupIconName } from "../components/GroupIcon";
import { LinkCard } from "../components/LinkCard";
import { ACCENT_CLASSES, accentFor } from "../lib/accent";
import { LinkPreviewModal } from "../components/LinkPreviewModal";
import { HealthTrendModal } from "../components/HealthTrendModal";
import { PageSkeleton } from "../components/PageSkeleton";
import { SiteFooter } from "../components/SiteFooter";
import { AuroraBackground } from "../components/bits/AuroraBackground";
import { BlurText } from "../components/bits/BlurText";
import { FloatingBackground } from "../components/FloatingBackground";
import { TechAmbience } from "../components/bits/TechAmbience";
import { useToast } from "../hooks/useToast";
import { useI18n } from "../lib/i18n";

export function PanelPage() {
  const [panel, setPanel] = useState<PanelOut | null>(null);
  const [me, setMe] = useState<MeOut | null>(null);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [recents, setRecents] = useState<RecentItem[]>(getRecent);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [previewLink, setPreviewLink] = useState<LinkOut | null>(null);
  const [trendLink, setTrendLink] = useState<LinkOut | null>(null);
  const [rssData, setRssData] = useState<{
    feeds: {
      feed_url: string;
      items: {
        title: string;
        link: string;
        pub_date?: string;
        description?: string;
      }[];
    }[];
  } | null>(null);
  const [rssOpen, setRssOpen] = useState(true);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<number>>(
    loadCollapsedGroups,
  );
  const [linkHealth, setLinkHealth] = useState<
    Record<number, { status: "up" | "down" | "unknown"; ms: number | null }>
  >(() => {
    // 首次渲染直接使用本地缓存的上次探测结果（0ms 占位），避免等探测完成才显示
    const cached = loadProbeCache();
    const initial: Record<
      number,
      { status: "up" | "down" | "unknown"; ms: number | null }
    > = {};
    for (const [id, value] of Object.entries(cached)) {
      initial[Number(id)] = { status: value.status, ms: value.ms };
    }
    return initial;
  });
  const [dragId, setDragId] = useState<number | null>(null);
  const [dragOverId, setDragOverId] = useState<number | null>(null);
  const toast = useToast();
  const { t } = useI18n();
  const searchRef = useRef<HTMLInputElement>(null);
  const meRef = useRef<MeOut | null>(null);
  const panelRef = useRef<PanelOut | null>(null);
  useEffect(() => {
    meRef.current = me;
  }, [me]);
  useEffect(() => {
    panelRef.current = panel;
  }, [panel]);

  /**
   * 客户端存活探测（2026-08-22）：刷新页面/回到面板时由浏览器直连目标 URL
   * （HEAD no-cors），自动使用系统/浏览器代理；结果优先于服务端探测展示。
   * 仅登录用户执行（访客视图不暴露私密 URL）；仅探测已启用健康检查的链接；
   * 30s 节流避免频繁切窗口打爆目标；面板打开期间按 120s 周期常驻探测。
   */
  const lastClientProbe = useRef(0);
  const runClientProbe = useCallback(() => {
    if (!meRef.current) return;
    const now = Date.now();
    if (now - lastClientProbe.current < 30_000) return;
    lastClientProbe.current = now;
    const panelData = panelRef.current;
    if (!panelData) return;
    const targets: { id: number; url: string }[] = [];
    const collect = (link: LinkOut) => {
      if (!link.health_enabled) return;
      const url = link.url || link.url_lan || link.url_wan;
      if (url && /^https?:\/\//.test(url)) targets.push({ id: link.id, url });
    };
    for (const group of panelData.groups) group.links.forEach(collect);
    panelData.ungrouped.forEach(collect);
    if (targets.length === 0) return;
    void probeFromClient(targets, fetch, 5000, (id, value) => {
      // 流式更新：每个目标完成立即点亮状态点，首个快链接约 100ms 出现
      setLinkHealth((prev) => ({ ...prev, [id]: value }));
    })
      .then((map) => saveProbeCache(map))
      .catch(() => undefined);
  }, []);

  /** 站点连接检测由用户侧发起：refresh=true 强制重新检测（忽略服务端缓存）。

      强制检测节流 60s（与服务端缓存 TTL 一致）：窗口聚焦/标签页恢复可见会频繁触发，
      若每次都强制出站检测，慢链接多时会拖垮面板（状态点转圈/失败）。
      60s 内重复触发降级为普通请求，直接命中服务端缓存。 */
  const lastForcedHealth = useRef(0);
  const loadHealth = useCallback((refresh: boolean) => {
    const now = Date.now();
    if (refresh) {
      if (now - lastForcedHealth.current < 60_000) {
        refresh = false;
      } else {
        lastForcedHealth.current = now;
      }
    }
    const target = meRef.current
      ? healthApi.links(refresh)
      : healthApi.status(refresh);
    void target
      .then((data) => {
        setLinkHealth((prev) => {
          const next = { ...prev };
          for (const item of data.results) {
            // 客户端探测结果优先；服务端仅补齐未探测的链接（访客/无 URL 链接）
            if (!(item.link_id in next)) {
              next[item.link_id] = { status: item.status, ms: item.ms };
            }
          }
          return next;
        });
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    authApi
      .meSilent()
      .then((current) => {
        meRef.current = current;
        setMe(current);
        void rssApi
          .feeds()
          .then(setRssData)
          .catch(() => setRssData(null));
        // 首次进入面板：立即检测
        loadHealth(true);
      })
      .catch(() => {
        meRef.current = null;
        setMe(null);
        // 访客公开状态页：首次进入立即检测
        loadHealth(true);
      });
    panelApi
      .get()
      .then((data) => {
        setPanel(data);
        // 清理已删除/停用健康检查链接的本地缓存残留
        const active = new Set<number>();
        const collectId = (link: LinkOut) => {
          const url = link.url || link.url_lan || link.url_wan;
          if (link.health_enabled && url && /^https?:\/\//.test(url)) {
            active.add(link.id);
          }
        };
        data.groups.forEach((group) => group.links.forEach(collectId));
        data.ungrouped.forEach(collectId);
        pruneProbeCache(active);
      })
      .catch(() => setPanel(null));
  }, [loadHealth]);

  // 刷新/首次进入：panel 与登录态均就绪后立即客户端探测存活率
  // （panel 与 me 异步加载，刷新时可能 panel 先到；两者齐备才探测）
  useEffect(() => {
    if (panel && me) runClientProbe();
  }, [panel, me, runClientProbe]);

  // 回到面板（标签页恢复可见 / 窗口重新聚焦）：重新检测
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        loadHealth(true);
        runClientProbe();
      }
    };
    const onFocus = () => {
      loadHealth(true);
      runClientProbe();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onFocus);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onFocus);
    };
  }, [loadHealth, runClientProbe]);

  // 面板打开期间常驻探测：客户端 120s 周期直连更新（受 30s 节流约束），
  // 服务端每 5min 走缓存兜底刷新（不强制出站），不依赖切窗口也能持续更新状态
  useEffect(() => {
    const probeTimer = window.setInterval(runClientProbe, CLIENT_PROBE_INTERVAL_MS);
    const statusTimer = window.setInterval(
      () => loadHealth(false),
      SERVER_STATUS_INTERVAL_MS,
    );
    return () => {
      window.clearInterval(probeTimer);
      window.clearInterval(statusTimer);
    };
  }, [runClientProbe, loadHealth]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((current) => !current);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const groups = useMemo(
    () =>
      (panel?.groups ?? []).map((group) => ({
        ...group,
        links: group.links.filter(
          (link) =>
            matches(link, query) &&
            (tagFilter === null || link.tags.includes(tagFilter)),
        ),
      })),
    [panel, query, tagFilter],
  );
  const ungrouped = (panel?.ungrouped ?? []).filter(
    (link) =>
      matches(link, query) && (tagFilter === null || link.tags.includes(tagFilter)),
  );
  const searching = Boolean(query.trim()) || tagFilter !== null;
  const isGroupCollapsed = (groupId: number) =>
    !searching && collapsedGroups.has(groupId);
  const allTags = useMemo(() => {
    const links = [
      ...(panel?.groups ?? []).flatMap((group) => group.links),
      ...(panel?.ungrouped ?? []),
    ];
    return Array.from(new Set(links.flatMap((link) => link.tags))).sort((a, b) =>
      a.localeCompare(b, "zh-CN"),
    );
  }, [panel]);
  const allLinks = useMemo(
    () => [
      ...(panel?.groups ?? []).flatMap((group) => group.links),
      ...(panel?.ungrouped ?? []),
    ],
    [panel],
  );
  const recentLinks = useMemo(() => {
    const byId = new Map(allLinks.map((link) => [link.id, link]));
    return recents
      .map((item) => byId.get(item.id))
      .filter((link): link is LinkOut => Boolean(link));
  }, [recents, allLinks]);
  // V25：今天打开过的快捷方式（无则回退最近使用）
  const todayLinks = useMemo(() => {
    const now = new Date();
    const isToday = (ts: number) => {
      const d = new Date(ts);
      return (
        d.getFullYear() === now.getFullYear() &&
        d.getMonth() === now.getMonth() &&
        d.getDate() === now.getDate()
      );
    };
    const todayItems = recents.filter((item) => isToday(item.opened_at));
    const items = todayItems.length > 0 ? todayItems : recents;
    const byId = new Map(allLinks.map((link) => [link.id, link]));
    return items
      .map((item) => byId.get(item.id))
      .filter((link): link is LinkOut => Boolean(link))
      .slice(0, 6);
  }, [recents, allLinks]);
  const flatLinks = useMemo(() => {
    const items: { link: LinkOut; id: string }[] = [];
    for (const group of groups) {
      if (!searching && collapsedGroups.has(group.id)) continue;
      for (const link of group.links) {
        items.push({ link, id: `panel-link-${items.length}` });
      }
    }
    for (const link of ungrouped) {
      items.push({ link, id: `panel-link-${items.length}` });
    }
    return items;
  }, [groups, ungrouped, collapsedGroups, searching]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing =
        target !== null &&
        ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
      if (
        event.key === "/" &&
        !typing &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey
      ) {
        event.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
        return;
      }
      if (
        event.key === "Escape" &&
        document.activeElement === searchRef.current
      ) {
        if (query) {
          setQuery("");
        } else {
          searchRef.current?.blur();
        }
        return;
      }
      if (document.activeElement !== searchRef.current || flatLinks.length === 0) {
        return;
      }
      const moveTo = (next: number) => {
        event.preventDefault();
        const clamped =
          next < 0 ? flatLinks.length - 1 : next >= flatLinks.length ? 0 : next;
        setActiveIndex(clamped);
        const el = document.getElementById(flatLinks[clamped].id);
        el?.focus();
        el?.scrollIntoView({ block: "nearest" });
      };
      if (event.key === "ArrowDown") {
        moveTo(activeIndex + 1);
      } else if (event.key === "ArrowUp") {
        moveTo(activeIndex - 1);
      } else if (event.key === "Home") {
        moveTo(0);
      } else if (event.key === "End") {
        moveTo(flatLinks.length - 1);
      } else if (event.key === "Enter" && activeIndex >= 0) {
        event.preventDefault();
        document.getElementById(flatLinks[activeIndex].id)?.click();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [query, flatLinks, activeIndex]);

  useEffect(() => {
    setActiveIndex(-1);
  }, [query, tagFilter, panel]);

  const site = panel?.site;
  const total = flatLinks.length;
  const canDrag = Boolean(me) && !searching;

  function handleDragEnd() {
    setDragId(null);
    setDragOverId(null);
  }

  function handleDrop(target: LinkOut) {
    const sourceId = dragId;
    setDragId(null);
    setDragOverId(null);
    if (sourceId === null || sourceId === target.id) return;
    const section = groups.find((group) =>
      group.links.some((link) => link.id === sourceId),
    );
    const sectionLinks = section ? section.links : ungrouped;
    const ids = sectionLinks.map((link) => link.id);
    const from = ids.indexOf(sourceId);
    const to = ids.indexOf(target.id);
    if (from === -1 || to === -1) {
      toast.info(t("拖拽排序仅在同一个分组内生效"));
      return;
    }
    const next = [...ids];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    setPanel((current) => {
      if (!current) return current;
      const sourceLinks = section ? section.links : current.ungrouped;
      const byId = new Map(sourceLinks.map((link) => [link.id, link]));
      const ordered = next
        .map((id) => byId.get(id))
        .filter((link): link is LinkOut => Boolean(link));
      const rest = sourceLinks.filter((link) => !next.includes(link.id));
      const links = [...ordered, ...rest];
      if (section) {
        return {
          ...current,
          groups: current.groups.map((group) =>
            group.id === section.id ? { ...group, links } : group,
          ),
        };
      }
      return { ...current, ungrouped: links };
    });
    linksApi.updateOrder(next).catch(() => {
      toast.error(t("排序保存失败，已恢复原顺序"));
      void panelApi.get().then(setPanel).catch(() => undefined);
    });
  }

  const logout = async () => {
    await authApi.logout().catch(() => undefined);
    window.location.href = "/";
  };

  if (!panel) {
    return <PageSkeleton title="快捷方式" />;
  }

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background">
      <FloatingBackground theme="auto" transparent shapeCount={10} />
      <AuroraBackground />
      <TechAmbience />
      <div className="relative z-10 flex flex-1 flex-col">
        <AppHeader
          title={me ? t("欢迎，{name}", { name: me.user.username }) : t("快捷方式")}
          actions={
            me ? (
              <>
                <Link to="/settings" className="btn btn-ghost h-9 px-3">
                  {t("管理")}
                </Link>
                <button
                  type="button"
                  className="btn btn-ghost h-9 px-3"
                  onClick={logout}
                >
                  {t("退出")}
                </button>
              </>
            ) : (
              <Link to="/login" className="btn btn-primary h-9 px-4">
                {t("登录")}
              </Link>
            )
          }
        />
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 outline-none sm:px-6 lg:px-8"
        >
          {site ? (
            <section className="mb-10 flex flex-col items-center gap-3 text-center">
              <DateTimeWidget username={me?.user.username} />
              <Brand className="brand-halo h-14 w-14" />
              <h1 className="text-3xl font-bold tracking-tight text-foreground">
                <BlurText
                  as="span"
                  text={site.site_name}
                  animateBy="words"
                  direction="top"
                  delay={120}
                  stepDuration={0.35}
                />
              </h1>
              <p className="text-sm text-muted">{site.slogan}</p>
              {site.description ? (
                <p className="max-w-xl text-sm text-muted">{site.description}</p>
              ) : null}
              <span className="badge badge-muted mt-1" aria-live="polite">
                {query.trim()
                  ? t("找到 {n} 个结果", { n: total })
                  : t("共 {n} 个快捷方式", { n: total })}
              </span>
              {me && !query.trim() && todayLinks.length > 0 ? (
                <div
                  className="mt-2 flex max-w-2xl flex-wrap items-center justify-center gap-2"
                  aria-label={t("今天常用")}
                >
                  {todayLinks.map((link) => {
                    const href = link.url ? link.url : `/go/${link.id}`;
                    return (
                      <a
                        key={link.id}
                        href={href}
                        target={link.open_mode === "new_tab" ? "_blank" : undefined}
                        rel={
                          link.open_mode === "new_tab" ? "noreferrer" : undefined
                        }
                        title={link.description || link.name}
                        className="badge badge-muted cursor-pointer border transition-colors hover:border-primary hover:text-primary"
                        onClick={(event) => {
                          const next = recordRecent(link);
                          setRecents(next);
                          if (link.open_mode === "modal") {
                            event.preventDefault();
                            setPreviewLink(link);
                          }
                        }}
                      >
                        {link.name}
                      </a>
                    );
                  })}
                </div>
              ) : null}
            </section>
          ) : null}

          <div className="relative mx-auto mb-8 max-w-md">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <input
              ref={searchRef}
              type="search"
              className="input pl-9"
              placeholder={t("搜索名称、描述、标签…")}
              aria-label="搜索快捷方式"
              title="按 / 聚焦；Ctrl/⌘ + K 打开命令面板"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <kbd className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[10px] leading-none text-muted">
              /
            </kbd>
          </div>

          {allTags.length > 0 ? (
            <div
              role="group"
              aria-label="按标签筛选"
              className="mx-auto mb-8 flex max-w-2xl flex-wrap items-center justify-center gap-2"
            >
              <button
                type="button"
                aria-pressed={tagFilter === null}
                className={`badge cursor-pointer border ${
                  tagFilter === null ? "badge-primary" : "badge-muted"
                }`}
                onClick={() => setTagFilter(null)}
              >
                {t("全部")}
              </button>
              {allTags.map((tag) => {
                const active = tagFilter === tag;
                return (
                  <button
                    key={tag}
                    type="button"
                    aria-pressed={active}
                    className={`badge cursor-pointer border ${
                      active ? "badge-primary" : "badge-muted"
                    }`}
                    onClick={() => setTagFilter(active ? null : tag)}
                  >
                    {tag}
                  </button>
                );
              })}
            </div>
          ) : null}

          {query.trim() && total === 0 ? (
            <div className="card mx-auto mb-10 max-w-md p-8 text-center">
              <p className="text-sm font-medium text-foreground">
                {t("没有找到匹配的快捷方式")}
              </p>
              <p className="mt-1 text-xs text-muted">
                {t("用外部搜索引擎继续：")}
              </p>
              <div className="mt-4 flex justify-center gap-2">
                <a
                  className="btn btn-ghost h-9 px-4"
                  href={`https://www.bing.com/search?q=${encodeURIComponent(query.trim())}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("Bing 搜索")}
                </a>
                <a
                  className="btn btn-ghost h-9 px-4"
                  href={`https://www.google.com/search?q=${encodeURIComponent(query.trim())}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("Google 搜索")}
                </a>
              </div>
            </div>
          ) : null}

          {!query.trim() && tagFilter === null && total === 0 ? (
            <div className="card mx-auto mb-10 max-w-md p-10 text-center">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
                className="mx-auto h-10 w-10 text-muted"
              >
                <rect x="3" y="3" width="7" height="7" rx="1.5" />
                <rect x="14" y="3" width="7" height="7" rx="1.5" />
                <rect x="3" y="14" width="7" height="7" rx="1.5" />
                <rect x="14" y="14" width="7" height="7" rx="1.5" />
              </svg>
              <p className="mt-4 text-sm font-medium text-foreground">
                {me ? t("还没有快捷方式") : t("这里还没有公开内容")}
              </p>
              <p className="mt-1 text-xs text-muted">
                {me
                  ? t("去管理页添加你的第一个快捷方式。")
                  : t("登录后即可收藏常用入口。")}
              </p>
              <div className="mt-5">
                <Link
                  to={me ? "/settings" : "/login"}
                  className="btn btn-primary h-9 px-4"
                >
                  {me ? t("去添加") : t("登录")}
                </Link>
              </div>
            </div>
          ) : null}

          {!query.trim() && tagFilter === null && recentLinks.length > 0 ? (
            <section className="mb-8">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-muted">
                  <span className="h-px w-4 bg-border" />
                  {t("最近使用")}
                  <span className="text-xs font-normal text-muted/80">
                    · {recentLinks.length}
                  </span>
                </h2>
                <button
                  type="button"
                  className="btn btn-ghost h-7 px-2 text-xs"
                  onClick={() => {
                    clearRecent();
                    setRecents([]);
                  }}
                >
                  {t("清空")}
                </button>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {recentLinks.map((link) => (
                  <LinkCard
                    key={link.id}
                    link={link}
                    onActivate={(activated) => setRecents(recordRecent(activated))}
                    onOpenModal={setPreviewLink}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {groups.map((group) =>
            group.links.length === 0 ? null : (
              <section key={group.id} className="mb-8">
                <button
                  type="button"
                  aria-expanded={!isGroupCollapsed(group.id)}
                  className="mb-3 flex items-center gap-2 text-sm font-semibold text-muted transition-colors hover:text-foreground"
                  onClick={() =>
                    setCollapsedGroups((current) =>
                      toggleCollapsedGroup(current, group.id),
                    )
                  }
                >
                  <span
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-sm font-semibold ${
                      ACCENT_CLASSES[accentFor(group.name)].tile
                    }`}
                  >
                    {isGroupIconName(group.icon) ? (
                      <GroupIcon name={group.icon} className="h-4 w-4" />
                    ) : (
                      group.name.trim().charAt(0).toUpperCase() || "?"
                    )}
                  </span>
                  {group.name}
                  <span className="text-xs font-normal text-muted/80">
                    · {group.links.length}
                  </span>
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                    className={`h-3.5 w-3.5 transition-transform ${
                      isGroupCollapsed(group.id) ? "-rotate-90" : ""
                    }`}
                  >
                    <path d="m6 9 6 6 6-6" />
                  </svg>
                </button>
                {!isGroupCollapsed(group.id) ? (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {group.links.map((link) => (
                      <LinkCard
                        key={link.id}
                        link={link}
                        onActivate={(activated) =>
                          setRecents(recordRecent(activated))
                        }
                        onOpenModal={setPreviewLink}
                        listIndex={flatLinks.findIndex(
                          (item) => item.link.id === link.id,
                        )}
                        draggable={canDrag}
                        isDragOver={dragOverId === link.id}
                        status={linkHealth[link.id]?.status}
                        statusMs={linkHealth[link.id]?.ms}
                        onStatusClick={setTrendLink}
                        onDragStart={(link) => setDragId(link.id)}
                        onDragOver={(link) => setDragOverId(link.id)}
                        onDrop={handleDrop}
                        onDragEnd={handleDragEnd}
                      />
                    ))}
                  </div>
                ) : null}
              </section>
            ),
          )}

          {ungrouped.length > 0 ? (
            <section className="mb-8">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-muted">
                <span className="h-px w-4 bg-border" />
                {t("未分组")}
                <span className="text-xs font-normal text-muted/80">
                  · {ungrouped.length}
                </span>
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {ungrouped.map((link) => (
                  <LinkCard
                    key={link.id}
                    link={link}
                    onActivate={(activated) => setRecents(recordRecent(activated))}
                    onOpenModal={setPreviewLink}
                    listIndex={flatLinks.findIndex(
                      (item) => item.link.id === link.id,
                    )}
                    draggable={canDrag}
                    isDragOver={dragOverId === link.id}
                    status={linkHealth[link.id]?.status}
                    statusMs={linkHealth[link.id]?.ms}
                    onStatusClick={setTrendLink}
                    onDragStart={(link) => setDragId(link.id)}
                    onDragOver={(link) => setDragOverId(link.id)}
                    onDrop={handleDrop}
                    onDragEnd={handleDragEnd}
                  />
                ))}
              </div>
            </section>
          ) : null}
          {me && rssData && rssData.feeds.length > 0 ? (
            <section className="mb-8">
              <button
                type="button"
                aria-expanded={rssOpen}
                className="mb-3 flex items-center gap-2 text-sm font-semibold text-muted transition-colors hover:text-foreground"
                onClick={() => setRssOpen((current) => !current)}
              >
                <span className="h-px w-4 bg-border" />
                {t("订阅")}
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                  className={`h-3.5 w-3.5 transition-transform ${
                    rssOpen ? "" : "-rotate-90"
                  }`}
                >
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </button>
              {rssOpen ? (
                <div className="card space-y-3 p-4">
                  {rssData.feeds.map((feed) =>
                    feed.items.map((item) => (
                      <a
                        key={`${feed.feed_url}-${item.link}`}
                        href={item.link}
                        target="_blank"
                        rel="noreferrer"
                        className="block min-w-0 rounded-lg px-2 py-1.5 transition-colors hover:bg-surface-2"
                      >
                        <span className="block truncate text-sm font-medium text-foreground">
                          {item.title}
                        </span>
                        {item.description ? (
                          <span className="block truncate text-xs text-muted">
                            {item.description}
                          </span>
                        ) : null}
                      </a>
                    )),
                  )}
                </div>
              ) : null}
            </section>
          ) : null}
        </main>
        <SiteFooter site={site} />
      </div>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        links={allLinks}
        loggedIn={Boolean(me)}
      />
      <LinkPreviewModal link={previewLink} onClose={() => setPreviewLink(null)} />
      <HealthTrendModal
        link={trendLink}
        onClose={() => setTrendLink(null)}
      />
    </div>
  );
}
