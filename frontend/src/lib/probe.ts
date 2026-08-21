/**
 * 客户端存活探测（2026-08-22）：
 * 由浏览器直连目标 URL 发起 HEAD（no-cors），自动使用系统/浏览器代理；
 * 与服务端探测互补——客户端网络可达即视为 up，网络层失败/超时视为 down。
 *
 * 速度优化（2026-08-22）：
 * - 全部目标并发发起（浏览器连接池自然排队，总耗时 ≈ 最慢单个，而非批次总和）
 * - onResult 逐条回调，首个快链接约 100ms 即可点亮状态点，不必等全部完成
 * - localStorage 缓存上次结果，刷新/重开页面立即渲染（探测完成后后台更新）
 */

export interface ProbeTarget {
  id: number;
  url: string;
}

export interface ProbeResult {
  status: "up" | "down";
  ms: number | null;
}

export interface ProbeCacheValue extends ProbeResult {
  /** 探测完成时间戳（毫秒） */
  ts: number;
}

/** 单目标超时：与后端 FETCH_TIMEOUT 对齐 */
export const CLIENT_PROBE_TIMEOUT = 5000;
/** 缓存有效期：超过后不用于占位渲染 */
export const PROBE_CACHE_TTL = 10 * 60_000;
const PROBE_CACHE_KEY = "lipanel-health-cache-v1";

export async function probeFromClient(
  targets: ProbeTarget[],
  fetchImpl: typeof fetch = fetch,
  timeout: number = CLIENT_PROBE_TIMEOUT,
  onResult?: (id: number, result: ProbeResult) => void,
): Promise<Record<number, ProbeResult>> {
  const results: Record<number, ProbeResult> = {};
  await Promise.all(
    targets.map(async ({ id, url }) => {
      const started = performance.now();
      let result: ProbeResult;
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeout);
        try {
          // no-cors：跨域 HEAD 只能拿到 opaque 响应，但网络层可达即判定存活
          await fetchImpl(url, {
            method: "HEAD",
            mode: "no-cors",
            cache: "no-store",
            signal: controller.signal,
          });
          result = {
            status: "up",
            ms: Math.round(performance.now() - started),
          };
        } finally {
          clearTimeout(timer);
        }
      } catch {
        result = { status: "down", ms: null };
      }
      results[id] = result;
      onResult?.(id, result);
    }),
  );
  return results;
}

/** 读取本地缓存的上次探测结果（过期丢弃），用于刷新/重开页面立即占位渲染 */
export function loadProbeCache(): Record<number, ProbeResult> {
  try {
    const raw = window.localStorage.getItem(PROBE_CACHE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return {};
    const now = Date.now();
    const out: Record<number, ProbeResult> = {};
    for (const [key, value] of Object.entries(parsed)) {
      const id = Number(key);
      const entry = value as Partial<ProbeCacheValue> | undefined;
      if (
        Number.isInteger(id) &&
        entry &&
        (entry.status === "up" || entry.status === "down") &&
        typeof entry.ts === "number" &&
        now - entry.ts <= PROBE_CACHE_TTL
      ) {
        out[id] = { status: entry.status, ms: entry.ms ?? null };
      }
    }
    return out;
  } catch {
    return {};
  }
}

/** 保存本次探测结果（供下次刷新占位渲染） */
export function saveProbeCache(map: Record<number, ProbeResult>): void {
  try {
    const now = Date.now();
    const payload: Record<string, ProbeCacheValue> = {};
    for (const [key, value] of Object.entries(map)) {
      payload[key] = { ...value, ts: now };
    }
    window.localStorage.setItem(PROBE_CACHE_KEY, JSON.stringify(payload));
  } catch {
    /* 隐私模式/存储不可用时静默降级 */
  }
}
