import { useEffect, useState } from "react";

import { healthApi } from "../api/client";
import type { LinkOut } from "../api/types";
import { Modal } from "./Modal";
import { useI18n } from "../lib/i18n";

interface HistoryPoint {
  status: "up" | "down";
  ms: number;
  checked_at: string;
}

export function HealthTrendModal({
  link,
  onClose,
}: {
  link: LinkOut | null;
  onClose: () => void;
}) {
  const [points, setPoints] = useState<HistoryPoint[]>([]);
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (link === null) return;
    setLoading(true);
    healthApi
      .history(link.id)
      .then(setPoints)
      .catch(() => setPoints([]))
      .finally(() => setLoading(false));
  }, [link]);

  const bars = points.slice(0, 24).reverse();
  const upCount = points.filter((p) => p.status === "up").length;

  return (
    <Modal open={link !== null} onClose={onClose} title={t("状态趋势")}>
      {link ? (
        <div>
          <p className="text-sm font-medium text-foreground">{link.name}</p>
          <p className="mt-1 text-xs text-muted">
            {t("最近 24 小时采样（每 10 分钟一轮）· 当前共 {n} 条", { n: points.length })}
          </p>
          {loading ? (
            <p className="mt-4 text-sm text-muted">{t("加载中…")}</p>
          ) : bars.length === 0 ? (
            <p className="mt-4 text-sm text-muted">
              {t("还没有历史数据，状态检查后会自动采样。")}
            </p>
          ) : (
            <div className="mt-4 flex items-end gap-1">
              {bars.map((point, index) => (
                <span
                  key={`${point.checked_at}-${index}`}
                  title={`${point.checked_at} · ${
                    point.status === "up" ? "在线" : "离线"
                  }${point.ms ? ` · ${point.ms}ms` : ""}`}
                  className={`h-6 w-2 rounded-sm ${
                    point.status === "up"
                      ? "bg-success"
                      : "bg-destructive"
                  }`}
                />
              ))}
            </div>
          )}
          {points.length > 0 ? (
            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted">
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-sm bg-success" />
                {t("在线")} {upCount}
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-sm bg-destructive" />
                {t("离线")} {points.length - upCount}
              </span>
            </div>
          ) : null}
        </div>
      ) : null}
    </Modal>
  );
}
