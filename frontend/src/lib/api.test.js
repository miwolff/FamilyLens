import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, requestJson } from "./api";

function jsonResponse(body, { status = 200 } = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("requestJson", () => {
  beforeEach(() => {
    vi.stubGlobal("window", globalThis);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("returns the parsed JSON body on success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ ok: 1 })));

    await expect(requestJson("/api/status")).resolves.toEqual({ ok: 1 });
  });

  it("uses the backend detail message for HTTP errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: "Indexing already running" }, { status: 409 })
        )
    );

    const error = await requestJson("/api/index").catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(409);
    expect(error.kind).toBe("http");
    expect(error.message).toBe("Indexing already running");
  });

  it("falls back to the default message when the error has no detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("", { status: 500 }))
    );

    const error = await requestJson("/api/search", {}, {
      defaultMessage: "Unable to run the search.",
    }).catch((e) => e);

    expect(error.message).toBe("Unable to run the search.");
    expect(error.status).toBe(500);
  });

  it("rejects successful responses that are not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html></html>", {
          status: 200,
          headers: { "Content-Type": "text/html" },
        })
      )
    );

    const error = await requestJson("/api/status").catch((e) => e);

    expect(error.kind).toBe("parse");
  });

  it("reports network failures with a dedicated message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    const error = await requestJson("/api/status").catch((e) => e);

    expect(error.kind).toBe("network");
    expect(error.message).toMatch(/Unable to reach the server/);
  });

  it("aborts and reports a timeout when the request takes too long", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url, { signal }) =>
          new Promise((_resolve, reject) => {
            signal.addEventListener("abort", () => {
              reject(new DOMException("Aborted", "AbortError"));
            });
          })
      )
    );

    const pending = requestJson("/api/status", {}, {
      timeoutMs: 1000,
      timeoutMessage: "Too slow.",
    }).catch((e) => e);
    await vi.advanceTimersByTimeAsync(1000);
    const error = await pending;

    expect(error.kind).toBe("timeout");
    expect(error.message).toBe("Too slow.");
  });
});
