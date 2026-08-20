import type { LinkOut } from "../api/types";
import { ACCENT_CLASSES, accentFor } from "../lib/accent";
import { recordRecent } from "../lib/recent";
import { useI18n } from "../lib/i18n";

export function LinkCard({
  link,
  listIndex,
  onActivate,
  onOpenModal,
  draggable = false,
  isDragOver = false,
  status,
  statusMs,
  onStatusClick,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
}: {
  link: LinkOut;
  listIndex?: number;
  onActivate?: (link: LinkOut) => void;
  onOpenModal?: (link: LinkOut) => void;
  draggable?: boolean;
  isDragOver?: boolean;
  status?: "up" | "down" | "unknown";
  statusMs?: number | null;
  onStatusClick?: (link: LinkOut) => void;
  onDragStart?: (link: LinkOut) => void;
  onDragOver?: (link: LinkOut) => void;
  onDrop?: (link: LinkOut) => void;
  onDragEnd?: () => void;
}) {
  const href = link.url ? link.url : `/go/${link.id}`;
  const isModal = link.open_mode === "modal";
  const target = link.open_mode === "new_tab" ? "_blank" : undefined;
  const { t } = useI18n();
  const accent = ACCENT_CLASSES[accentFor(link.name)];
  const letter = link.name.trim().charAt(0).toUpperCase() || "?";

  return (
    <a
      id={listIndex === undefined ? undefined : `panel-link-${listIndex}`}
      href={href}
      target={target}
      rel={target ? "noreferrer" : undefined}
      draggable={draggable}
      onDragStart={
        draggable
          ? (event) => {
              event.dataTransfer.effectAllowed = "move";
              onDragStart?.(link);
            }
          : undefined
      }
      onDragOver={
        draggable
          ? (event) => {
              event.preventDefault();
              event.dataTransfer.dropEffect = "move";
              onDragOver?.(link);
            }
          : undefined
      }
      onDrop={
        draggable
          ? (event) => {
              event.preventDefault();
              onDrop?.(link);
            }
          : undefined
      }
      onDragEnd={draggable ? onDragEnd : undefined}
      onClick={(event) => {
        recordRecent(link);
        onActivate?.(link);
        if (isModal) {
          event.preventDefault();
          onOpenModal?.(link);
        }
      }}
      className={`card card-interactive flex items-center gap-3 p-4 ${
        draggable ? "cursor-grab select-none active:cursor-grabbing" : ""
      } ${isDragOver ? "ring-2 ring-primary" : ""}`}
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
        <span
          title={link.name}
          className="block text-sm font-medium leading-snug text-foreground line-clamp-2"
        >
          {link.name}
        </span>
        {link.description ? (
          <span title={link.description} className="block truncate text-xs text-muted">
            {link.description}
          </span>
        ) : null}
      </span>
      {status ? (
        <span className="ml-auto flex shrink-0 items-center gap-1.5">
          <span
            role="button"
            tabIndex={-1}
            aria-label={
              status === "up"
                ? t("在线")
                : status === "down"
                  ? t("离线")
                  : t("状态未知")
            }
            title={
              status === "up"
                ? t("在线 · {ms}ms", { ms: statusMs ?? "" }) +
                  t("（点击查看趋势）")
                : status === "down"
                  ? t("离线") + t("（点击查看趋势）")
                  : t("状态未知")
            }
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onStatusClick?.(link);
            }}
            className={`status-dot shrink-0 ${
              status === "up"
                ? "status-dot-up"
                : status === "down"
                  ? "status-dot-down"
                  : ""
            }`}
          />
          <span
            className={`min-w-14 text-right text-xs tabular-nums leading-none ${
              status === "up"
                ? "text-success"
                : status === "down"
                  ? "text-destructive"
                  : "text-muted"
            }`}
            aria-hidden="true"
          >
            {status === "up"
              ? statusMs != null
                ? `${statusMs}ms`
                : t("在线")
              : status === "down"
                ? t("离线")
                : "—"}
          </span>
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className="h-4 w-4 shrink-0 text-muted"
          >
            <path d="M7 17 17 7M8 7h9v9" />
          </svg>
        </span>
      ) : (
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
      )}
    </a>
  );
}
