import { useEffect, useMemo, useState } from "react";

import { AppHeader } from "../components/AppHeader";
import { AuroraBackground } from "../components/AuroraBackground";
import { BlurText } from "../components/BlurText";
import { CountUp } from "../components/CountUp";
import { FloatingBackground } from "../components/FloatingBackground";
import { GroupSection } from "../components/GroupSection";
import { LinkCard } from "../components/LinkCard";
import { PageSkeleton } from "../components/PageSkeleton";
import { api, ApiError, type LinkItem, type Me, type PanelData } from "../lib/api";
import { TechAmbience } from "../components/TechAmbience";

function matches(link: LinkItem, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) {
    return true;
  }
  return (
    link.name.toLowerCase().includes(q) ||
    link.description.toLowerCase().includes(q) ||
    link.tags.some((tag) => tag.toLowerCase().includes(q)) ||
    (link.url ?? "").toLowerCase().includes(q)
  );
}

export function PanelPage() {
  const [panel, setPanel] = useState<PanelData | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe(null));
    api
      .getPanel()
      .then(setPanel)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          window.location.href = "/login";
        } else {
          setError("加载面板失败");
        }
      });
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
  const site = panel?.site;
  const total = (panel?.groups.reduce((sum, group) => sum + group.links.length, 0) ?? 0) + ungrouped.length;

  if (!panel && !error) {
    return (
      <div className="relative min-h-screen bg-background">
        <AuroraBackground soft />
        <div className="relative z-10">
          <AppHeader username={me?.user.username} />
          <PageSkeleton />
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-background">
      <AuroraBackground soft />
      <FloatingBackground shapeCount={10} calm />
      <TechAmbience />
      <div className="relative z-10">
        <AppHeader username={me?.user.username} />
        <main className="mx-auto max-w-7xl px-4 py-8">
          {error ? <div className="badge badge-danger mb-6 w-full justify-center py-2">{error}</div> : null}
          {site ? (
            <section className="mb-8 flex flex-col items-center gap-2 text-center">
              <img src={site.logo || "/brand-logo.webp"} alt="" className="h-14 w-14 rounded-2xl" />
              <h1 className="text-2xl font-semibold text-foreground">
                <BlurText text={site.site_name} />
              </h1>
              <p className="text-sm text-muted">{site.slogan}</p>
              {site.description ? <p className="max-w-xl text-sm text-muted">{site.description}</p> : null}
              <span className="badge badge-muted mt-2">
                共 <CountUp value={total} /> 个快捷方式
              </span>
            </section>
          ) : null}
          <div className="relative mx-auto mb-8 max-w-md">
            <svg className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true">
              <use href="/icons.svg#i-search" />
            </svg>
            <input
              className="input pl-9"
              placeholder="搜索名称、描述、标签…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {groups.map((group) => (
            <GroupSection key={group.id} group={group} />
          ))}
          {ungrouped.length > 0 ? (
            <section className="mb-8">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-muted">
                <svg className="h-4 w-4" aria-hidden="true"><use href="/icons.svg#i-grid" /></svg>
                未分组
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {ungrouped.map((link) => (
                  <LinkCard key={link.id} link={link} />
                ))}
              </div>
            </section>
          ) : null}
          {site ? (
            <footer className="mt-12 border-t border-border pt-6 pb-4 text-center text-xs text-muted">
              {site.footer_text}
              {site.icp ? ` · ${site.icp}` : ""}
            </footer>
          ) : null}
        </main>
      </div>
    </div>
  );
}
