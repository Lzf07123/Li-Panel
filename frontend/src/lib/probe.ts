/**
 * 客户端存活探测（2026-08-22）：
 * 由浏览器直连目标 URL 发起 HEAD（no-cors），自动使用系统/浏览器代理；
 * 与服务端探测互补——客户端网络可达即视为 up，网络层失败/超时视为 down。
 */

export interface ProbeTarget {
  id: number;
  url: string;
}

export interface ProbeResult {
  status: "up" | "down";
  ms: number | null;
}

/** 单目标超时：与后端 FETCH_TIMEOUT 对齐 */
export const CLIENT_PROBE_TIMEOUT = 5000;
/** 并发上限：避免一次刷新打爆目标站点/浏览器连接池 */
export const CLIENT_PROBE_CONCURRENCY = 6;

export async function probeFromClient(
  targets: ProbeTarget[],
  fetchImpl: typeof fetch = fetch,
  timeout: number = CLIENT_PROBE_TIMEOUT,
): Promise<Record<number, ProbeResult>> {
  const results: Record<number, ProbeResult> = {};
  for (let i = 0; i < targets.length; i += CLIENT_PROBE_CONCURRENCY) {
    const batch = targets.slice(i, i + CLIENT_PROBE_CONCURRENCY);
    await Promise.all(
      batch.map(async ({ id, url }) => {
        const started = performance.now();
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
            results[id] = {
              status: "up",
              ms: Math.round(performance.now() - started),
            };
          } finally {
            clearTimeout(timer);
          }
        } catch {
          results[id] = { status: "down", ms: null };
        }
      }),
    );
  }
  return results;
}
