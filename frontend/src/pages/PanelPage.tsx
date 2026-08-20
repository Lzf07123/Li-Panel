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
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    authApi.meSilent().then(setMe).catch(() => setMe(null));
    panelApi.get().then(setPanel).catch(() => setPanel(null));
  }, []);

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
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [query]);

  const groups = useMemo(
    () =>
      (panel?.groups ?? []).map((group) => ({
        ...group,
        links: group.links.filter((link) => matches(link, query)),
      })),
    [panel, query],
  );
  const ungrouped = (panel?.ungrouped ?? []).filter((link) => matches(link, query));
  const site = panel?.site;
  const total =
    (panel?.groups.reduce((sum, group) => sum + group.links.length, 0) ?? 0) +
    ungrouped.length;

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

          {groups.map((group) =>
            group.links.length === 0 ? null : (
              <section key={group.id} className="mb-8">
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-muted">
                  <span className="h-px w-4 bg-border" />
                  {group.name}
                </h2>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {group.links.map((link) => (
                    <LinkCard key={link.id} link={link} />
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
                  <LinkCard key={link.id} link={link} />
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
