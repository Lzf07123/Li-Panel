import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { authApi } from "../api/client";
import type { LinkOut } from "../api/types";
import { useTheme } from "../hooks/useTheme";
import { Modal } from "./Modal";

interface PaletteItem {
  key: string;
  label: string;
  hint?: string;
  run: () => void;
}

function openLink(link: LinkOut) {
  const href = link.url ?? `/go/${link.id}`;
  window.open(href, "_blank", "noopener");
}

export function CommandPalette({
  open,
  onClose,
  links,
  loggedIn,
}: {
  open: boolean;
  onClose: () => void;
  links: LinkOut[];
  loggedIn: boolean;
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [theme, setTheme] = useTheme();
  const navigate = useNavigate();

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  const q = query.trim().toLowerCase();
  const matchedLinks = links.filter(
    (link) =>
      !q ||
      link.name.toLowerCase().includes(q) ||
      link.description.toLowerCase().includes(q) ||
      link.tags.some((tag) => tag.toLowerCase().includes(q)) ||
      (link.url ?? "").toLowerCase().includes(q),
  );

  const actions: PaletteItem[] = [
    ...(loggedIn
      ? [
          {
            key: "settings",
            label: "管理",
            hint: "分组与快捷方式",
            run: () => {
              onClose();
              navigate("/settings");
            },
          },
        ]
      : []),
    {
      key: "theme",
      label: theme === "dark" ? "切换为浅色主题" : "切换为深色主题",
      run: () => {
        setTheme(theme === "dark" ? "light" : "dark");
        onClose();
      },
    },
    loggedIn
      ? {
          key: "logout",
          label: "退出登录",
          run: () => {
            onClose();
            void authApi.logout().catch(() => undefined);
            window.location.href = "/";
          },
        }
      : {
          key: "login",
          label: "登录",
          run: () => {
            onClose();
            navigate("/login");
          },
        },
  ];

  const items: PaletteItem[] = [
    ...matchedLinks.slice(0, 12).map(
      (link): PaletteItem => ({
        key: `link-${link.id}`,
        label: link.name,
        hint: link.description || link.url || "快捷方式",
        run: () => {
          onClose();
          openLink(link);
        },
      }),
    ),
    ...actions,
  ];

  function move(delta: number) {
    if (items.length === 0) return;
    setActive((current) => {
      const next = current + delta;
      return next < 0 ? items.length - 1 : next >= items.length ? 0 : next;
    });
  }

  function runActive() {
    const item = items[active];
    if (item) item.run();
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="命令面板"
      maxWidth="max-w-xl"
    >
      <input
        autoFocus
        className="input"
        placeholder="搜索快捷方式或输入命令…"
        aria-label="命令面板搜索"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setActive(0);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            move(1);
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            move(-1);
          } else if (event.key === "Enter") {
            event.preventDefault();
            runActive();
          }
        }}
      />
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-muted">没有匹配结果</p>
      ) : (
        <ul
          role="listbox"
          aria-label="搜索结果"
          className="mt-3 max-h-72 overflow-y-auto space-y-1"
        >
          {items.map((item, index) => (
            <li key={item.key} role="option" aria-selected={index === active}>
              <button
                type="button"
                className={`flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                  index === active
                    ? "bg-primary-soft text-primary"
                    : "text-foreground hover:bg-surface-2"
                }`}
                onMouseEnter={() => setActive(index)}
                onClick={() => item.run()}
              >
                <span className="truncate">{item.label}</span>
                {item.hint ? (
                  <span className="truncate text-xs text-muted">{item.hint}</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
