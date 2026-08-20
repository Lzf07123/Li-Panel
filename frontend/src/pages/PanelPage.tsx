import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { authApi, panelApi } from "../api/client";
import type { LinkOut, MeOut, PanelOut } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { Brand } from "../components/Brand";
import { LinkCard } from "../components/LinkCard";
import { PageSkeleton } from "../components/PageSkeleton";
import { SiteFooter } from "../components/SiteFooter";
import { AuroraBackground } from "../components/bits/AuroraBackground";
import { BlurText } from "../components/bits/BlurText";
import { FloatingBackground } from "../components/FloatingBackground";
import { TechAmbience } from "../components/bits/TechAmbience";

function matches(link: LinkOut, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    link.name.toLowerCase().includes(q) ||
    link.description.toLowerCase().includes(q) ||
    link.tags.some((tag) => tag.toLowerCase().includes(q)) ||
    (link.url ?? "").toLowerCase().includes(q)
  );
}

export function PanelPage() {
  const [panel, setPanel] = useState<PanelOut | null>(null);
  const [me, setMe] = useState<MeOut | null>(null);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    authApi.meSilent().then(setMe).catch(() => setMe(null));
    panelApi.get().then(setPanel).catch(() => setPanel(null));
  }, []);

  const groups = useMemo(
    () =>
      (panel?.groups ?? []).map((group) => ({
        ...group,
        links: group.links.filter((link) => matches(link, query)),
      })),
    [panel, query],
  );
  const ungrouped = (panel?.ungrouped ?? []).filter((link) => matches(link, query));
  const flatLinks = useMemo(() => {
    const items: { link: LinkOut; id: string }[] = [];
    for (const group of groups) {
      for (const link of group.links) {
        items.push({ link, id: `panel-link-${items.length}` });
      }
    }
    for (const link of ungrouped) {
      items.push({ link, id: `panel-link-${items.length}` });
    }
    return items;
  }, [groups, ungrouped]);

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
  }, [query, panel]);

  const site = panel?.site;
  const total = flatLinks.length;

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
          title={me ? `欢迎，${me.user.username}` : "快捷方式"}
          actions={
            me ? (
              <>
                <Link to="/settings" className="btn btn-ghost h-9 px-3">
                  管理
                </Link>
                <button
                  type="button"
                  className="btn btn-ghost h-9 px-3"
                  onClick={logout}
                >
                  退出
                </button>
              </>
            ) : (
              <Link to="/login" className="btn btn-primary h-9 px-4">
                登录
              </Link>
            )
          }
        />
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
          {site ? (
            <section className="mb-10 flex flex-col items-center gap-3 text-center">
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
                  ? `找到 ${total} 个结果`
                  : `共 ${total} 个快捷方式`}
              </span>
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
              placeholder="搜索名称、描述、标签…"
              aria-label="搜索快捷方式"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <kbd className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[10px] leading-none text-muted">
              /
            </kbd>
          </div>

          {query.trim() && total === 0 ? (
            <div className="card mx-auto mb-10 max-w-md p-8 text-center">
              <p className="text-sm font-medium text-foreground">
                没有找到匹配的快捷方式
              </p>
              <p className="mt-1 text-xs text-muted">用外部搜索引擎继续：</p>
              <div className="mt-4 flex justify-center gap-2">
                <a
                  className="btn btn-ghost h-9 px-4"
                  href={`https://www.bing.com/search?q=${encodeURIComponent(query.trim())}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Bing 搜索
                </a>
                <a
                  className="btn btn-ghost h-9 px-4"
                  href={`https://www.google.com/search?q=${encodeURIComponent(query.trim())}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Google 搜索
                </a>
              </div>
            </div>
          ) : null}

          {groups.map((group) =>
            group.links.length === 0 ? null : (
              <section key={group.id} className="mb-8">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-muted">
                  <span className="h-px w-4 bg-border" />
                  {group.name}
                </h2>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {group.links.map((link) => (
                    <LinkCard
                      key={link.id}
                      link={link}
                      listIndex={flatLinks.findIndex(
                        (item) => item.link.id === link.id,
                      )}
                    />
                  ))}
                </div>
              </section>
            ),
          )}

          {ungrouped.length > 0 ? (
            <section className="mb-8">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-muted">
                <span className="h-px w-4 bg-border" />
                未分组
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {ungrouped.map((link) => (
                  <LinkCard
                    key={link.id}
                    link={link}
                    listIndex={flatLinks.findIndex(
                      (item) => item.link.id === link.id,
                    )}
                  />
                ))}
              </div>
            </section>
          ) : null}
        </main>
        <SiteFooter />
      </div>
    </div>
  );
}
