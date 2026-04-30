import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { ApiError, api } from "@/lib/api";

const dataSchema = z.object({ value: z.number() });

function mockFetch(body: unknown, init: ResponseInit = { status: 200 }) {
  global.fetch = vi.fn(async () => new Response(JSON.stringify(body), init));
}

describe("api", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("unwraps a success envelope to the data payload", async () => {
    mockFetch({ success: true, data: { value: 42 }, request_id: "rid" });
    const out = await api.get("/x", dataSchema);
    expect(out).toEqual({ value: 42 });
  });

  it("throws ApiError with code + message on a failure envelope", async () => {
    mockFetch(
      {
        success: false,
        error: { code: "VALIDATION_ERROR", message: "Bad input." },
        details: { email: ["Required."] },
        request_id: "rid-1",
      },
      { status: 422 },
    );
    await expect(api.post("/x", dataSchema, { body: {} })).rejects.toMatchObject({
      name: "ApiError",
      code: "VALIDATION_ERROR",
      status: 422,
      message: "Bad input.",
      requestId: "rid-1",
    });
  });

  it("exposes per-field details via fieldMessage", async () => {
    mockFetch(
      {
        success: false,
        error: { code: "VALIDATION_ERROR", message: "Bad." },
        details: { email: ["Required.", "And valid."] },
      },
      { status: 422 },
    );
    try {
      await api.post("/x", dataSchema, { body: {} });
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const err = e as ApiError;
      expect(err.fieldMessage("email")).toBe("Required.");
      expect(err.fieldMessage("missing")).toBeUndefined();
    }
  });

  it("throws INVALID_RESPONSE on shape mismatch", async () => {
    mockFetch({ success: true, data: { value: "not-a-number" } });
    await expect(api.get("/x", dataSchema)).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
  });

  it("throws NETWORK_ERROR on fetch rejection", async () => {
    global.fetch = vi.fn(async () => {
      throw new Error("fail");
    });
    await expect(api.get("/x", dataSchema)).rejects.toMatchObject({
      code: "NETWORK_ERROR",
      status: 0,
    });
  });

  it("parses Retry-After (seconds) on 429 into ApiError.retryAfterSeconds", async () => {
    global.fetch = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            success: false,
            error: { code: "RATE_LIMITED", message: "Too many." },
          }),
          { status: 429, headers: { "retry-after": "47" } },
        ),
    );
    await expect(api.get("/x", dataSchema)).rejects.toMatchObject({
      code: "RATE_LIMITED",
      status: 429,
      retryAfterSeconds: 47,
    });
  });

  it("parses Retry-After (HTTP-date) into seconds-from-now", async () => {
    const future = new Date(Date.now() + 90_000).toUTCString();
    global.fetch = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            success: false,
            error: { code: "RATE_LIMITED", message: "Too many." },
          }),
          { status: 429, headers: { "retry-after": future } },
        ),
    );
    try {
      await api.get("/x", dataSchema);
      expect.fail("should have thrown");
    } catch (e) {
      const err = e as ApiError;
      expect(err.retryAfterSeconds).toBeGreaterThanOrEqual(80);
      expect(err.retryAfterSeconds).toBeLessThanOrEqual(95);
    }
  });

  it("leaves retryAfterSeconds undefined when header is missing", async () => {
    mockFetch(
      { success: false, error: { code: "RATE_LIMITED", message: "Too many." } },
      { status: 429 },
    );
    try {
      await api.get("/x", dataSchema);
      expect.fail("should have thrown");
    } catch (e) {
      expect((e as ApiError).retryAfterSeconds).toBeUndefined();
    }
  });

  it("sends credentials and JSON content-type on POST", async () => {
    const f = vi.fn(
      async () => new Response(JSON.stringify({ success: true, data: { value: 1 } })),
    );
    global.fetch = f as unknown as typeof fetch;
    await api.post("/x", dataSchema, { body: { foo: "bar" } });

    expect(f).toHaveBeenCalledOnce();
    const args = f.mock.calls[0] as unknown as [string, RequestInit];
    const init = args[1];
    expect(init.credentials).toBe("include");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ foo: "bar" }));
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });
});
