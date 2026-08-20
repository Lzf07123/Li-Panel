import { useCallback, useState } from "react";

import { enUS } from "../locales/en-US";

export type Lang = "zh-CN" | "en-US";

const STORAGE_KEY = "lipanel-lang";

export function detectLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "zh-CN" || saved === "en-US") return saved;
  } catch {
    /* ignore */
  }
  return (navigator.language || "").toLowerCase().startsWith("en")
    ? "en-US"
    : "zh-CN";
}

export function setLangPreference(lang: Lang): void {
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* ignore */
  }
}

export function translate(lang: Lang, text: string): string {
  if (lang === "zh-CN") return text;
  return enUS[text] ?? text;
}

function interpolate(text: string, params?: Record<string, string | number>): string {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in params ? String(params[key]) : match,
  );
}

/** 轻量 i18n：中文原文即 key，英文查字典；支持 {param} 插值。 */
export function useI18n() {
  const [lang, setLangState] = useState<Lang>(detectLang);
  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    setLangPreference(next);
  }, []);
  const t = useCallback(
    (text: string, params?: Record<string, string | number>) =>
      interpolate(translate(lang, text), params),
    [lang],
  );
  return { lang, setLang, t };
}
