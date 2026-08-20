import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { applyTheme, getTheme, type Theme } from "../lib/theme";
import { TechAmbience } from "./TechAmbience";

export function AppHeader({ username }: { username?: string }) {
  const cycleTheme = () => {
    const order: Theme[] = ["light", "dark", "system"];
    const next = order[(order.indexOf(getTheme()) + 1) % order.length];
    applyTheme(next);
  };
  const logout = async () => {
    await api.logout();
    window.location.href = "/";
  };
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
        <Link to="/" className="flex items-center gap-2">
          <img src="/brand-logo.webp" alt="" className="h-7 w-7 rounded-lg" />
          <span className="text-sm font-semibold text-foreground">Li&Panel</span>
        </Link>
        <div className="ml-auto flex items-center gap-2">
          <button type="button" className="btn btn-ghost h-9 px-3" onClick={cycleTheme} aria-label="切换主题">
            <svg className="h-4 w-4" aria-hidden="true"><use href="#i-moon" /></svg>
          </button>
          {username ? (
            <>
              <Link to="/settings" className="btn btn-ghost h-9 px-3">
                <svg className="h-4 w-4" aria-hidden="true"><use href="#i-gear" /></svg>
                管理
              </Link>
              <button type="button" className="btn btn-ghost h-9 px-3" onClick={logout}>
                <svg className="h-4 w-4" aria-hidden="true"><use href="#i-logout" /></svg>
                {username}
              </button>
            </>
          ) : (
            <Link to="/login" className="btn btn-primary h-9 px-4">登录</Link>
          )}
        </div>
      </div>
      <TechAmbience />
    </header>
  );
}
