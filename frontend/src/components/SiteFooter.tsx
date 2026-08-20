import { useState } from "react";
import { Link } from "react-router-dom";

import type { SiteSettings } from "../api/types";
import {
  APP_VERSION,
  CONTACT_EMAIL,
  COPYRIGHT_HOLDER,
  FOOTER_LINKS,
  GITHUB_ISSUES_URL,
  GITHUB_URL,
  ICP_FILING_ICON,
  ICP_FILING_ICON_ENV,
  ICP_FILING_TEXT,
  ICP_FILING_TEXT_ENV,
  ICP_FILING_URL,
  ICP_FILING_URL_ENV,
  LICENSE_NAME,
  LICENSE_URL,
  POLICE_FILING_ICON,
  POLICE_FILING_ICON_ENV,
  POLICE_FILING_TEXT,
  POLICE_FILING_TEXT_ENV,
  POLICE_FILING_URL,
  POLICE_FILING_URL_ENV,
  envFirst,
} from "../lib/brand";

function FilingLink({
  text,
  href,
  icon,
  placeholder,
}: {
  text: string;
  href: string;
  icon: string;
  placeholder: string;
}) {
  const [broken, setBroken] = useState(false);
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      title={text}
      className="inline-flex items-center gap-1 whitespace-nowrap transition-colors duration-200 hover:text-foreground"
    >
      {broken || !icon ? (
        // 预留图标占位：正式备案图标缺失/加载失败时展示字形方块
        <span className="filing-icon-placeholder" aria-hidden="true">
          {placeholder}
        </span>
      ) : (
        <img
          src={icon}
          alt=""
          loading="lazy"
          className="h-3.5 w-3.5 object-contain"
          onError={() => setBroken(true)}
        />
      )}
      {text}
    </a>
  );
}

function FilingLinks({
  site,
}: {
  site?: SiteSettings | null;
}) {
  // 运行时以后台 site_settings 为事实来源，未配置时回退品牌默认值
  // 备案信息优先构建期环境变量（VITE_*），未配置时才使用后台 site_settings 值
  const entries = [
    {
      key: "icp",
      text: envFirst(ICP_FILING_TEXT_ENV, site?.icp ?? ICP_FILING_TEXT),
      href: envFirst(ICP_FILING_URL_ENV, site?.icp_url ?? ICP_FILING_URL),
      icon: envFirst(ICP_FILING_ICON_ENV, site?.icp_icon ?? ICP_FILING_ICON),
      placeholder: "备",
    },
    {
      key: "police",
      text: envFirst(
        POLICE_FILING_TEXT_ENV,
        site?.police_text ?? POLICE_FILING_TEXT,
      ),
      href: envFirst(POLICE_FILING_URL_ENV, site?.police_url ?? POLICE_FILING_URL),
      icon: envFirst(
        POLICE_FILING_ICON_ENV,
        site?.police_icon ?? POLICE_FILING_ICON,
      ),
      placeholder: "公",
    },
  ].filter((entry) => entry.text !== "");

  if (entries.length === 0) return null;
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      {entries.map((entry, index) => (
        <span key={entry.key} className="inline-flex items-center gap-2">
          {index > 0 ? (
            <span aria-hidden="true" className="text-border">
              ·
            </span>
          ) : null}
          <FilingLink {...entry} />
        </span>
      ))}
    </span>
  );
}

function GitHubIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden="true"
      className="h-3.5 w-3.5"
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}

function FooterLink({ label, href }: { label: string; href: string }) {
  const className =
    "transition-colors duration-200 hover:text-foreground";

  if (href.startsWith("/")) {
    return (
      <Link to={href} className={className}>
        {label}
      </Link>
    );
  }

  return (
    <a href={href} target="_blank" rel="noreferrer" className={className}>
      {label}
    </a>
  );
}

export function SiteFooter({
  site,
}: {
  site?: SiteSettings | null;
}) {
  const year = new Date().getFullYear();

  return (
    <footer className="relative mt-auto border-t border-border/60 bg-surface/60 backdrop-blur">
      <div className="mx-auto flex min-h-14 max-w-7xl flex-wrap items-center justify-center gap-x-2 gap-y-1 px-4 py-5 text-xs text-muted lg:px-8">
        <span>© {year} {COPYRIGHT_HOLDER} · v{APP_VERSION}</span>
        {site?.footer_text ? (
          <span className="whitespace-nowrap">{site.footer_text}</span>
        ) : null}
        <FilingLinks site={site} />
        {FOOTER_LINKS.map((link) => (
          <FooterLink key={link.label} label={link.label} href={link.href} />
        ))}
        {GITHUB_URL && (
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 transition-colors duration-200 hover:text-foreground"
          >
            <GitHubIcon />
            GitHub
          </a>
        )}
        {LICENSE_NAME && LICENSE_URL && (
          <a
            href={LICENSE_URL}
            target="_blank"
            rel="noreferrer"
            className="transition-colors duration-200 hover:text-foreground"
          >
            开源协议（{LICENSE_NAME}）
          </a>
        )}
        {GITHUB_ISSUES_URL && (
          <a
            href={GITHUB_ISSUES_URL}
            target="_blank"
            rel="noreferrer"
            className="transition-colors duration-200 hover:text-foreground"
          >
            反馈问题
          </a>
        )}
        {CONTACT_EMAIL && (
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="transition-colors duration-200 hover:text-foreground"
          >
            联系我们
          </a>
        )}
      </div>
    </footer>
  );
}
