/**
 * Error code → user-friendly message.
 *
 * The backend's envelope `error.code` is the stable contract. This module
 * is the only place that turns those codes into copy. Toasts and inline
 * messages should call ``userMessage(error)``; never echo `error.message`
 * raw, and never put a request_id in front of an end user.
 *
 * Anything missing from this map falls back to a generic message; the raw
 * error (including request_id) is logged to the console for debugging.
 */

import type { ApiError } from "@/lib/api";

const MESSAGES: Record<string, string> = {
  // auth — single vague code on bad-creds is intentional (CLAUDE.md sec.8)
  AUTH_INVALID_CREDENTIALS: "Invalid email or password.",
  AUTH_TOKEN_EXPIRED: "Your session has expired. Please sign in again.",
  AUTH_TOKEN_INVALID: "Please sign in to continue.",
  AUTH_REFRESH_REQUIRED: "Your session has expired. Please sign in again.",

  // generic
  VALIDATION_ERROR: "Please check the highlighted fields and try again.",
  CONFLICT: "This action conflicts with your current state.",
  NOT_FOUND: "We couldn't find what you were looking for.",
  FORBIDDEN: "You don't have access to that.",
  RATE_LIMITED: "Too many requests. Please wait a moment.",
  IDEMPOTENCY_KEY_REUSED: "This request was already submitted with a different payload.",

  // KYC
  KYC_NOT_STARTED: "Start KYC to continue your onboarding.",
  KYC_PENDING: "Your KYC review is in progress.",
  KYC_FAILED: "We couldn't verify your identity. Please review and retry.",
  KYC_RETRY_EXHAUSTED: "You've reached the retry limit for KYC. Please contact support.",

  // accreditation
  ACCREDITATION_PENDING: "Your accreditation review is in progress.",
  ACCREDITATION_FAILED: "We couldn't verify your accreditation. Please review and retry.",

  // bank
  BANK_LINK_FAILED: "Bank linking failed. Please verify the details.",
  BANK_NOT_LINKED: "Link a bank account to continue.",

  // investment
  INSUFFICIENT_BALANCE: "There aren't enough funds in your linked bank for this investment.",
  INVESTMENT_FAILED: "Your investment couldn't be processed.",

  // transport
  NETWORK_ERROR: "Couldn't reach the server. Please check your connection.",
  INVALID_RESPONSE: "Something went wrong. Please try again.",
  UNKNOWN_ERROR: "Something went wrong. Please try again.",
  INTERNAL_ERROR: "Something went wrong on our end. Please try again.",
};

const DEFAULT_FALLBACK = "Something went wrong. Please try again.";

/** User-facing copy for an ApiError (or null/undefined → fallback). */
export function userMessage(error: unknown, fallback?: string): string {
  if (!error || typeof error !== "object") return fallback ?? DEFAULT_FALLBACK;
  const e = error as ApiError;
  // Special-case 429s: when the server told us when to retry, prefer
  // the concrete "in N seconds" copy over the generic message.
  if (e.code === "RATE_LIMITED" && typeof e.retryAfterSeconds === "number") {
    return `Too many requests. Try again in ${formatDuration(e.retryAfterSeconds)}.`;
  }
  if (typeof e.code === "string" && MESSAGES[e.code]) {
    return MESSAGES[e.code];
  }
  return fallback ?? DEFAULT_FALLBACK;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds} second${seconds === 1 ? "" : "s"}`;
  const minutes = Math.ceil(seconds / 60);
  return `${minutes} minute${minutes === 1 ? "" : "s"}`;
}
