import { describe, expect, it, vi } from "vitest";

import {
  CLIENT_PROBE_TIMEOUT,
  loadProbeCache,
  probeFromClient,
  saveProbeCache,
} from "./probe";

function mockFetch(handler: (url: string, init?: RequestInit) => Promise<Response> | Response) {
  const fn = vi.fn(handler);
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("probeFromClient", () => {
  it("网络可达判定 up 并返回耗时", async () => {
    mockFetch(() => new Response(null));
    const result = await probeFromClient([{ id: 1, url: "https://a.example" }]);
    expect(result[1].status).toBe("up");
    expect(result[1].ms).toBeGreaterThanOrEqual(0);
  });

  it("网络失败判定 down", async () => {
    mockFetch(() => Promise.reject(new TypeError("Failed to fetch")));
    const result = await probeFromClient([{ id: 2, url: "https://b.example" }]);
    expect(result[2]).toEqual({ status: "down", ms: null });
  });

  it("超时中止判定 down", async () => {
    const fn = mockFetch((_url, init) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError")),
        );
      });
    });
    const result = await probeFromClient([{ id: 3, url: "https://c.example" }], fetch, 50);
    expect(result[3]).toEqual({ status: "down", ms: null });
    expect(fn).toHaveBeenCalledTimes(1);
    const init = fn.mock.calls[0][1] as RequestInit;
    expect(init.signal).toBeDefined();
    expect(CLIENT_PROBE_TIMEOUT).toBeGreaterThan(0);
  });

  it("全部目标并发发起并逐条回调（首个结果不必等全部完成）", async () => {
    const order: number[] = [];
    mockFetch((_url, _init) => {
      const id = Number(new URL(_url).hostname.replace("x", ""));
      return new Promise((resolve) =>
        setTimeout(() => resolve(new Response(null)), id === 0 ? 20 : 120),
      );
    });
    const targets = Array.from({ length: 5 }, (_, i) => ({
      id: i,
      url: `https://x${i}.example`,
    }));
    const seen: number[] = [];
    const result = await probeFromClient(targets, fetch, 5000, (id) => {
      seen.push(id);
    });
    expect(Object.keys(result)).toHaveLength(targets.length);
    // 快链接（id=0, 20ms）先于慢链接（120ms）回调 → 流式更新生效
    expect(seen[0]).toBe(0);
    order.push(seen.length);
    void order;
  });
});

describe("probe cache", () => {
  it("保存后可读回，过期条目被丢弃", async () => {
    localStorage.clear();
    saveProbeCache({ 1: { status: "up", ms: 120 }, 2: { status: "down", ms: null } });
    let cache = loadProbeCache();
    expect(cache[1]).toEqual({ status: "up", ms: 120 });
    expect(cache[2]).toEqual({ status: "down", ms: null });

    // 人为把 ts 改为过期
    const raw = JSON.parse(localStorage.getItem("lipanel-health-cache-v1") ?? "{}");
    raw["1"].ts = Date.now() - 11 * 60_000;
    localStorage.setItem("lipanel-health-cache-v1", JSON.stringify(raw));
    cache = loadProbeCache();
    expect(cache[1]).toBeUndefined();
    expect(cache[2]).toBeDefined();
  });

  it("损坏数据安全返回空对象", () => {
    localStorage.setItem("lipanel-health-cache-v1", "not-json");
    expect(loadProbeCache()).toEqual({});
  });
});
