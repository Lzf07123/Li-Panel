import type { LinkItem } from "../lib/api";

export function LinkCard({ link }: { link: LinkItem }) {
  const href = link.url ? link.url : `/go/${link.id}`;
  const target = link.open_mode === "new_tab" ? "_blank" : undefined;
  const letter = link.name.trim().charAt(0).toUpperCase() || "?";
  return (
    <a
      href={href}
      target={target}
      rel={target ? "noreferrer" : undefined}
      className="card card-signature flex cursor-pointer items-center gap-3 p-4"
    >
      {link.icon_type === "upload" && link.icon_value ? (
        <img src={link.icon_value} alt="" className="h-10 w-10 shrink-0 rounded-xl object-cover" />
      ) : (
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-base font-semibold text-primary">
          {letter}
        </span>
      )}
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium text-foreground">{link.name}</span>
        {link.description ? (
          <span className="block truncate text-xs text-muted">{link.description}</span>
        ) : null}
      </span>
      <svg className="ml-auto h-4 w-4 shrink-0 text-muted" aria-hidden="true">
        <use href="/icons.svg#i-external" />
      </svg>
    </a>
  );
}
