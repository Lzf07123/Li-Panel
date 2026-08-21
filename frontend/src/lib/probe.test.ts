import { describe, expect, it, vi } from "vitest";

import type { LinkOut } from "../api/types";

import {
  CLIENT_PROBE_BATCH_SIZE,
  CLIENT_PROBE_TIMEOUT,
  collectProbeTargets,
  loadProbeCache,
  probeFromClient,
  pruneProbeCache,
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

describe("pruneProbeCache", () => {
  it("删除已停用/删除链接的残留结果，保留活跃结果", () => {
    localStorage.clear();
    saveProbeCache({
      1: { status: "up", ms: 120 },
      2: { status: "down", ms: null },
      3: { status: "up", ms: 80 },
    });
    pruneProbeCache(new Set([1, 3]));
    const cache = loadProbeCache();
    expect(Object.keys(cache).sort()).toEqual(["1", "3"]);
    expect(cache[1]).toEqual({ status: "up", ms: 120 });
    expect(cache[3]).toEqual({ status: "up", ms: 80 });
  });

  it("清理时同时丢弃过期条目", () => {
    localStorage.clear();
    saveProbeCache({ 1: { status: "up", ms: 100 }, 2: { status: "down", ms: null } });
    const raw = JSON.parse(localStorage.getItem("lipanel-health-cache-v1") ?? "{}");
    raw["1"].ts = Date.now() - 11 * 60_000;
    localStorage.setItem("lipanel-health-cache-v1", JSON.stringify(raw));
    pruneProbeCache(new Set([1, 2]));
    const cache = loadProbeCache();
    expect(cache[1]).toBeUndefined();
    expect(cache[2]).toBeDefined();
  });

  it("空活跃集合清空缓存，损坏数据安全跳过", () => {
    localStorage.clear();
    saveProbeCache({ 1: { status: "up", ms: 10 } });
    pruneProbeCache(new Set());
    expect(loadProbeCache()).toEqual({});

    localStorage.setItem("lipanel-health-cache-v1", "not-json");
    pruneProbeCache(new Set([1]));
    expect(loadProbeCache()).toEqual({});
  });
});

describe("collectProbeTargets", () => {
  const base: Omit<LinkOut, "id" | "health_enabled"> = {
    group_id: null,
    name: "",
    url_lan: "",
    url_wan: null,
    icon_type: "letter",
    icon_value: null,
    description: "",
    tags: [],
    is_public: false,
    guest_url_mode: "hidden",
    sort_order: 0,
    open_mode: "new_tab",
    health_interval: 10,
    health_timeout: 5,
    health_threshold: 1,
  };

  it("仅收集启用健康检查且带 http(s) 地址的链接", () => {
    const links: LinkOut[] = [
      { ...base, id: 1, health_enabled: true, url: "https://a.example" },
      { ...base, id: 2, health_enabled: false, url: "https://b.example" },
      { ...base, id: 3, health_enabled: true, url_lan: "http://192.168.1.2" },
      { ...base, id: 4, health_enabled: true, url_lan: "ftp://x.example" },
    ];
    expect(collectProbeTargets(links)).toEqual([
      { id: 1, url: "https://a.example" },
      { id: 3, url: "http://192.168.1.2" },
    ]);
  });

  it("url 为空时回退 url_lan / url_wan", () => {
    const links: LinkOut[] = [
      {
        ...base,
        id: 1,
        health_enabled: true,
        url: undefined,
        url_wan: "https://w.example",
      },
      {
        ...base,
        id: 2,
        health_enabled: true,
        url: undefined,
        url_lan: "http://l.example",
        url_wan: "https://w2.example",
      },
    ];
    expect(collectProbeTargets(links)).toEqual([
      { id: 1, url: "https://w.example" },
      { id: 2, url: "http://l.example" },
    ]);
  });

  it("空地址或非 http(s) 协议跳过", () => {
    const links: LinkOut[] = [
      { ...base, id: 1, health_enabled: true, url: "" },
      { ...base, id: 2, health_enabled: true, url_lan: "mailto:a@example.com" },
      { ...base, id: 3, health_enabled: false, url: "https://x.example" },
    ];
    expect(collectProbeTargets(links)).toEqual([]);
  });
});

describe("probeFromClient 分批显示", () => {
  it("探测全并发发起（活跃数 = 目标数），不再串行分批", async () => {
    let active = 0;
    let maxActive = 0;
    mockFetch(() => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      return new Promise((resolve) =>
        setTimeout(() => {
          active -= 1;
          resolve(new Response(null));
        }, 20),
      );
    });
    const targets = Array.from({ length: 7 }, (_, i) => ({
      id: i,
      url: `https://x${i}.example`,
    }));
    const result = await probeFromClient(targets, fetch, 5000);
    expect(CLIENT_PROBE_BATCH_SIZE).toBeGreaterThan(0);
    // 7 个目标同时发起：总耗时 ≈ 最慢单个，而不是「批数 × 最慢单批」
    expect(maxActive).toBe(7);
    expect(Object.keys(result)).toHaveLength(7);
  });

  it("每凑满一批按完成计数回调 onBatch 与进度（显示分批，探测不等待）", async () => {
    mockFetch((_url) => {
      const id = Number(new URL(_url).hostname.replace("x", ""));
      return new Promise((resolve) =>
        setTimeout(() => resolve(new Response(null)), id === 0 ? 20 : 120),
      );
    });
    const targets = Array.from({ length: 7 }, (_, i) => ({
      id: i,
      url: `https://x${i}.example`,
    }));
    const progressSeq: { done: number; total: number }[] = [];
    const batchSizes: number[] = [];
    const result = await probeFromClient(targets, fetch, 5000, undefined, (batch, progress) => {
      progressSeq.push({ done: progress.done, total: progress.total });
      batchSizes.push(Object.keys(batch).length);
    });
    // 7 个结果按完成顺序凑批：前 6 个一批、剩余 1 个一批
    expect(progressSeq).toEqual([
      { done: 1, total: 2 },
      { done: 2, total: 2 },
    ]);
    expect(batchSizes).toEqual([6, 1]);
    expect(Object.keys(result)).toHaveLength(7);
  });

  it("批内结果仍逐条流式回调（首个快链接先点亮）", async () => {
    mockFetch((_url) => {
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
    await probeFromClient(targets, fetch, 5000, (id) => {
      seen.push(id);
    });
    expect(seen[0]).toBe(0);
  });
});
