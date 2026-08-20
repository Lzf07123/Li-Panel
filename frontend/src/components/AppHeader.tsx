import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { TechAmbience } from "./TechAmbience";
import { ThemeToggle } from "./ThemeToggle";

export function AppHeader({ username }: { username?: string }) {
  const logout = async () => {
    await api.logout();
    window.location.href = "/";
  };
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
        <Link to="/" className="flex items-center gap-2">
          <img src="/brand-logo.webp" alt="" className="h-7 w-7 rounded-lg" />
          <span className="hidden text-sm font-semibold text-foreground sm:inline">
            Li&Panel
          </span>
        </Link>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          {username ? (
            <>
              <Link to="/settings" className="btn btn-ghost h-9 px-3">
                <svg className="h-4 w-4" aria-hidden="true"><use href="/icons.svg#i-gear" /></svg>
                <span className="hidden sm:inline">管理</span>
              </Link>
              <button
                type="button"
                className="btn btn-ghost h-9 px-3"
                onClick={logout}
                aria-label="退出登录"
              >
                <svg className="h-4 w-4" aria-hidden="true"><use href="/icons.svg#i-logout" /></svg>
                <span className="hidden sm:inline">{username}</span>
              </button>
            </>
          ) : (
            <Link to="/login" className="btn btn-primary h-9 px-4">
              登录
            </Link>
          )}
        </div>
      </div>
      <TechAmbience />
    </header>
  );
}
