/**
 * 品牌与站点信息集中配置：优先从构建期环境变量（VITE_*）读取，
 * 未设置时回退到本文件默认值。视觉实现与 Li&Pass 参考实现 1:1。
 */

const env = import.meta.env;

function envString(name: string, fallback: string): string {
  const value = env[name];
  return typeof value === "string" && value.trim() !== ""
    ? value.trim()
    : fallback;
}

export const APP_NAME = envString("VITE_APP_NAME", "Li&Panel");
export const APP_TAGLINE = envString(
  "VITE_APP_TAGLINE",
  "一次收藏，触达所有常用入口",
);
export const COPYRIGHT_HOLDER = APP_NAME;
export const DOCUMENT_TITLE = `${APP_NAME} · 快捷方式面板`;
/** 应用版本（V46）：与 backend/app/version.py、docs/CHANGELOG.md 同步 */
export const APP_VERSION = envString("VITE_APP_VERSION", "0.1.0");

/** 网站图标：统一使用 WebP 单格式（透明背景，512×512） */
export const FAVICON_WEBP = "/favicon.webp";
export const FAVICON_PATH = FAVICON_WEBP;

/** 页面品牌主图（登录页/页头 Logo）：透明背景，512×512 */
export const APP_LOGO = "/brand-logo.webp";

// 备案信息：留空时页脚不显示对应链接
export const ICP_FILING_TEXT = envString("VITE_ICP_FILING_TEXT", "");
export const ICP_FILING_URL = envString(
  "VITE_ICP_FILING_URL",
  "https://beian.miit.gov.cn/",
);
export const ICP_FILING_ICON = envString("VITE_ICP_FILING_ICON", "/badges/icp.webp");
export const POLICE_FILING_TEXT = envString("VITE_POLICE_FILING_TEXT", "");
export const POLICE_FILING_URL = envString(
  "VITE_POLICE_FILING_URL",
  "https://beian.mps.gov.cn/",
);
export const POLICE_FILING_ICON = envString(
  "VITE_POLICE_FILING_ICON",
  "/badges/police.webp",
);

// 开源仓库与反馈入口：置空即隐藏对应页脚链接
export const GITHUB_URL = envString("VITE_GITHUB_URL", "");
export const GITHUB_ISSUES_URL = envString("VITE_GITHUB_ISSUES_URL", "");
export const LICENSE_NAME = envString("VITE_LICENSE_NAME", "");
export const LICENSE_URL = envString("VITE_LICENSE_URL", "");
export const CONTACT_EMAIL = envString("VITE_CONTACT_EMAIL", "");

/** 页脚附加链接：默认不展示（Li&Panel 无法律页面），可用 VITE_FOOTER_LINKS 覆盖 */
const DEFAULT_FOOTER_LINKS: { label: string; href: string }[] = [];

function footerLinksFromEnv(): { label: string; href: string }[] {
  const raw = envString("VITE_FOOTER_LINKS", "");
  if (!raw) return DEFAULT_FOOTER_LINKS;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return DEFAULT_FOOTER_LINKS;
    return parsed.filter(
      (item): item is { label: string; href: string } =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as { label?: unknown }).label === "string" &&
        typeof (item as { href?: unknown }).href === "string",
    );
  } catch {
    return DEFAULT_FOOTER_LINKS;
  }
}

export const FOOTER_LINKS: { label: string; href: string }[] =
  footerLinksFromEnv();
