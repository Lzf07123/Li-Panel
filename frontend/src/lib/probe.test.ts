import { describe, expect, it, vi } from "vitest";

import {
  CLIENT_PROBE_CONCURRENCY,
  CLIENT_PROBE_TIMEOUT,
  probeFromClient,
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
    const result = await probeFromClient(
      [{ id: 3, url: "https://c.example" }],
      fetch,
      50,
    );
    expect(result[3]).toEqual({ status: "down", ms: null });
    expect(fn).toHaveBeenCalledTimes(1);
    // 确认确实设置了超时中止
    const init = fn.mock.calls[0][1] as RequestInit;
    expect(init.signal).toBeDefined();
    expect(CLIENT_PROBE_TIMEOUT).toBeGreaterThan(0);
  });

  it("按并发上限分批探测", async () => {
    let inFlight = 0;
    let maxInFlight = 0;
    mockFetch(() => {
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      return new Promise((resolve) =>
        setTimeout(() => {
          inFlight -= 1;
          resolve(new Response(null));
        }, 10),
      );
    });
    const targets = Array.from({ length: CLIENT_PROBE_CONCURRENCY + 3 }, (_, i) => ({
      id: i,
      url: `https://x${i}.example`,
    }));
    const result = await probeFromClient(targets);
    expect(Object.keys(result)).toHaveLength(targets.length);
    expect(maxInFlight).toBeLessThanOrEqual(CLIENT_PROBE_CONCURRENCY);
  });
});
