import { useState } from "react";

import { applyTheme, getTheme, type Theme } from "../lib/theme";

const ORDER: Theme[] = ["light", "dark", "system"];

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getTheme());
  const dark =
    theme === "dark" ||
    (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);

  const cycle = () => {
    const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length];
    applyTheme(next);
    setTheme(next);
  };

  return (
    <button
      type="button"
      className="btn btn-ghost h-9 w-9 px-0"
      onClick={cycle}
      aria-label="切换主题"
      title={`当前：${theme}`}
    >
      <svg className="h-4 w-4" aria-hidden="true">
        <use href={dark ? "/icons.svg#i-sun" : "/icons.svg#i-moon"} />
      </svg>
    </button>
  );
}
