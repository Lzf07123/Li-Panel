import type { LinkOut } from "../api/types";
import { ACCENT_CLASSES, accentFor } from "../lib/accent";

export function LinkCard({ link }: { link: LinkOut }) {
  const href = link.url ? link.url : `/go/${link.id}`;
  const target = link.open_mode === "new_tab" ? "_blank" : undefined;
  const accent = ACCENT_CLASSES[accentFor(link.name)];
  const letter = link.name.trim().charAt(0).toUpperCase() || "?";

  return (
    <a
      href={href}
      target={target}
      rel={target ? "noreferrer" : undefined}
      className="card card-interactive flex items-center gap-3 p-4"
    >
      {link.icon_type === "upload" && link.icon_value ? (
        <img
          src={link.icon_value}
          alt=""
          className="h-10 w-10 shrink-0 rounded-xl bg-surface-2 object-cover"
        />
      ) : (
        <span
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-base font-semibold ${accent.tile}`}
        >
          {letter}
        </span>
      )}
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium text-foreground">
          {link.name}
        </span>
        {link.description ? (
          <span className="block truncate text-xs text-muted">
            {link.description}
          </span>
        ) : null}
      </span>
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="ml-auto h-4 w-4 shrink-0 text-muted"
      >
        <path d="M7 17 17 7M8 7h9v9" />
      </svg>
    </a>
  );
}
