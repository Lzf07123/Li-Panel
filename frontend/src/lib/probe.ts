/**
 * 客户端存活探测（2026-08-22）：
 * 由浏览器直连目标 URL 发起 HEAD（no-cors），自动使用系统/浏览器代理；
 * 与服务端探测互补——客户端网络可达即视为 up，网络层失败/超时视为 down。
 *
 * 速度优化（2026-08-22）：
 * - 全部目标并发发起（浏览器连接池自然排队，总耗时 ≈ 最慢单个，而非批次总和）
 * - onResult 逐条回调，首个快链接约 100ms 即可点亮状态点，不必等全部完成
 * - localStorage 缓存上次结果，刷新/重开页面立即渲染（探测完成后后台更新）
 *
 * 流程优化（2026-08-22）：
 * - pruneProbeCache 清理已删除/停用链接的残留结果，缓存不再无限膨胀
 * - 面板打开期间按 CLIENT_PROBE_INTERVAL_MS 常驻周期探测，不依赖切窗口
 */

import type { LinkOut } from "../api/types";

export interface ProbeTarget {
  id: number;
  url: string;
}

/** 收集需要客户端探测的链接：仅启用健康检查且带 http(s) 地址（访客不暴露私密 URL）。 */
export function collectProbeTargets(links: LinkOut[]): ProbeTarget[] {
  const targets: ProbeTarget[] = [];
  for (const link of links) {
    if (!link.health_enabled) continue;
    const url = link.url || link.url_lan || link.url_wan;
    if (url && /^https?:\/\//.test(url)) {
      targets.push({ id: link.id, url });
    }
  }
  return targets;
}

export interface ProbeResult {
  status: "up" | "down";
  ms: number | null;
}

/** 批探测进度：done 为已完成批数，total 为总批数（供前端「分批显示」进度指示） */
export interface ProbeBatchProgress {
  done: number;
  total: number;
}

export interface ProbeCacheValue extends ProbeResult {
  /** 探测完成时间戳（毫秒） */
  ts: number;
}

/** 单目标超时：与后端 FETCH_TIMEOUT 对齐 */
export const CLIENT_PROBE_TIMEOUT = 5000;
/** 探测批大小：每批并发发起、批间串行（避免一次打爆目标站点/浏览器连接池），每批完成后回调一次 */
export const CLIENT_PROBE_BATCH_SIZE = 6;
/** 缓存有效期：超过后不用于占位渲染 */
export const PROBE_CACHE_TTL = 10 * 60_000;
/** 面板打开期间的客户端常驻探测周期（受 30s 节流约束，实际间隔 ≥ 120s） */
export const CLIENT_PROBE_INTERVAL_MS = 120_000;
/** 面板打开期间服务端状态兜底刷新周期（非强制，命中服务端 60s 缓存） */
export const SERVER_STATUS_INTERVAL_MS = 5 * 60_000;
const PROBE_CACHE_KEY = "lipanel-health-cache-v1";

export async function probeFromClient(
  targets: ProbeTarget[],
  fetchImpl: typeof fetch = fetch,
  timeout: number = CLIENT_PROBE_TIMEOUT,
  onResult?: (id: number, result: ProbeResult) => void,
  onBatch?: (batchResults: Record<number, ProbeResult>, progress: ProbeBatchProgress) => void,
): Promise<Record<number, ProbeResult>> {
  const results: Record<number, ProbeResult> = {};
  const total = Math.ceil(targets.length / CLIENT_PROBE_BATCH_SIZE);
  // 分批检测：每批 CLIENT_PROBE_BATCH_SIZE 个并发发起，批间串行；
  // 每批完成后回调 onBatch（分批显示/进度），批内 onResult 仍逐条流式点亮。
  for (let i = 0; i < targets.length; i += CLIENT_PROBE_BATCH_SIZE) {
    const batch = targets.slice(i, i + CLIENT_PROBE_BATCH_SIZE);
    await Promise.all(
      batch.map(async ({ id, url }) => {
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
    const batchResults: Record<number, ProbeResult> = {};
    for (const target of batch) {
      batchResults[target.id] = results[target.id];
    }
    onBatch?.(batchResults, { done: i / CLIENT_PROBE_BATCH_SIZE + 1, total });
  }
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

/** 清理本地缓存中已删除/停用链接的残留结果（保留有效且活跃的结果） */
export function pruneProbeCache(activeIds: ReadonlySet<number>): void {
  try {
    const raw = window.localStorage.getItem(PROBE_CACHE_KEY);
    if (!raw) return;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return;
    const now = Date.now();
    const next: Record<string, ProbeCacheValue> = {};
    for (const [key, value] of Object.entries(parsed)) {
      const id = Number(key);
      const entry = value as Partial<ProbeCacheValue> | undefined;
      if (
        activeIds.has(id) &&
        entry &&
        (entry.status === "up" || entry.status === "down") &&
        typeof entry.ts === "number" &&
        now - entry.ts <= PROBE_CACHE_TTL
      ) {
        next[key] = { status: entry.status, ms: entry.ms ?? null, ts: entry.ts };
      }
    }
    window.localStorage.setItem(PROBE_CACHE_KEY, JSON.stringify(next));
  } catch {
    /* 隐私模式/存储不可用时静默降级 */
  }
}
