import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { userMessage } from "@/lib/error-messages";

function rateLimitedError(retryAfterSeconds?: number): ApiError {
  return new ApiError(
    { code: "RATE_LIMITED", message: "Too many requests." },
    429,
    undefined,
    null,
    retryAfterSeconds,
  );
}

describe("userMessage", () => {
  it("renders the precise wait time for RATE_LIMITED with retryAfterSeconds < 60", () => {
    expect(userMessage(rateLimitedError(15))).toBe("Too many requests. Try again in 15 seconds.");
  });

  it("singularises seconds when retryAfterSeconds is 1", () => {
    expect(userMessage(rateLimitedError(1))).toBe("Too many requests. Try again in 1 second.");
  });

  it("rounds up to whole minutes when retryAfterSeconds >= 60", () => {
    expect(userMessage(rateLimitedError(60))).toBe("Too many requests. Try again in 1 minute.");
    expect(userMessage(rateLimitedError(61))).toBe("Too many requests. Try again in 2 minutes.");
    expect(userMessage(rateLimitedError(180))).toBe("Too many requests. Try again in 3 minutes.");
  });

  it("falls back to the static RATE_LIMITED copy when retryAfter is unknown", () => {
    expect(userMessage(rateLimitedError(undefined))).toBe(
      "Too many requests. Please wait a moment.",
    );
  });

  it("returns the mapped copy for known error codes", () => {
    const err = new ApiError({ code: "AUTH_INVALID_CREDENTIALS", message: "ignored" }, 401);
    expect(userMessage(err)).toBe("Invalid email or password.");
  });

  it("returns the fallback for unknown codes", () => {
    const err = new ApiError({ code: "SOMETHING_WEIRD", message: "ignored" }, 500);
    expect(userMessage(err)).toBe("Something went wrong. Please try again.");
    expect(userMessage(err, "custom fallback")).toBe("custom fallback");
  });

  it("returns the fallback for non-objects", () => {
    expect(userMessage(null)).toBe("Something went wrong. Please try again.");
    expect(userMessage("oops")).toBe("Something went wrong. Please try again.");
    expect(userMessage(undefined, "x")).toBe("x");
  });
});
