import { useEffect, useState } from "react";

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

function greetingFor(hour: number): string {
  if (hour >= 5 && hour < 12) return "早上好";
  if (hour >= 12 && hour < 14) return "中午好";
  if (hour >= 14 && hour < 18) return "下午好";
  if (hour >= 18) return "晚上好";
  return "夜深了";
}

function formatDate(date: Date): string {
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日 星期${
    WEEKDAYS[date.getDay()]
  }`;
}

function formatTime(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(
    date.getSeconds(),
  )}`;
}

/**
 * 面板顶部问候 + 日期/时间小组件（路线图 V24 时钟、V25 问候的前端部分）。
 * 本地时区、秒级更新；纯文本更新不做动画，天然满足 prefers-reduced-motion。
 */
export function DateTimeWidget({
  username,
}: {
  username?: string | null;
}) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <p className="flex flex-wrap items-center justify-center gap-x-2 gap-y-0.5 text-xs text-muted">
      <span>
        {username
          ? `${greetingFor(now.getHours())}，${username}`
          : greetingFor(now.getHours())}
      </span>
      <span aria-hidden="true" className="text-border">
        ·
      </span>
      <time dateTime={now.toISOString()}>{formatDate(now)}</time>
      <span aria-hidden="true" className="text-border">
        ·
      </span>
      <time dateTime={now.toISOString()}>{formatTime(now)}</time>
    </p>
  );
}
