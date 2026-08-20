import type { LinkOut } from "../api/types";
import { Modal } from "./Modal";

export function LinkPreviewModal({
  link,
  onClose,
}: {
  link: LinkOut | null;
  onClose: () => void;
}) {
  if (!link) return null;
  const href = link.url ?? `/go/${link.id}`;

  return (
    <Modal open={true} onClose={onClose} title={link.name} maxWidth="max-w-4xl">
      <div className="flex items-center justify-between gap-3">
        <p className="min-w-0 truncate text-xs text-muted">{href}</p>
        <a
          className="btn btn-ghost h-8 shrink-0 px-3 text-xs"
          href={href}
          target="_blank"
          rel="noreferrer"
        >
          新标签页打开
        </a>
      </div>
      <iframe
        src={href}
        title={link.name}
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        referrerPolicy="no-referrer"
        className="mt-3 h-[65vh] w-full rounded-xl border border-border bg-white"
      />
      <p className="mt-2 text-xs text-muted">
        部分网站会拒绝内嵌显示，可用「新标签页打开」兜底。
      </p>
    </Modal>
  );
}
