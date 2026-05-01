/**
 * User-facing labels and detail summaries for audit-log entries.
 *
 * The backend writes `action` as SCREAMING_SNAKE_CASE codes
 * (apps/api/app/models/audit_log.py) and stores small JSONB
 * `metadata` blobs whose shape varies by action. The UI shouldn't
 * leak either format directly — this module translates both into
 * something that reads like English in the audit feed.
 *
 * Add a new action by extending ACTION_LABELS + (optionally)
 * extending describeMetadata with a case.
 */

const ACTION_LABELS: Record<string, string> = {
  // Auth
  AUTH_SIGNUP: "Account created",
  AUTH_LOGIN: "Signed in",
  AUTH_LOGIN_FAILED: "Failed sign-in",
  AUTH_REFRESH: "Session refreshed",
  AUTH_REFRESH_REUSE_DETECTED: "Refresh token reuse detected",
  AUTH_LOGOUT: "Signed out",

  // Profile
  PROFILE_UPDATED: "Profile updated",

  // KYC
  KYC_SUBMITTED: "KYC submitted",
  KYC_RETRY_BLOCKED: "KYC retry blocked",
  KYC_RETRY_EXHAUSTED: "KYC retries exhausted",

  // Accreditation
  ACCREDITATION_SUBMITTED: "Accreditation submitted",
  ACCREDITATION_RESOLVED: "Accreditation resolved",
  ACCREDITATION_RETRY_BLOCKED: "Accreditation retry blocked",

  // Bank
  BANK_LINKED: "Bank linked",
  BANK_LINK_FAILED: "Bank link failed",
  BANK_UNLINKED: "Bank unlinked",
  BANK_LINK_BLOCKED: "Bank link blocked",

  // Investments
  INVESTMENT_CREATED: "Investment placed",
  INVESTMENT_FAILED: "Investment failed",
  INVESTMENT_BLOCKED: "Investment blocked",
  INVESTMENT_IDEMPOTENT_REPLAY: "Investment replay (idempotent)",
};

const STATUS_LABELS: Record<string, string> = {
  success: "Success",
  failure: "Failed",
  pending: "Pending",
};

export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? toTitleCase(action);
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? toTitleCase(status);
}

/**
 * Build a one-line human summary of the metadata blob for a given
 * action. Returns `null` when there's nothing user-meaningful to
 * surface — keep the row tight.
 */
export function describeMetadata(action: string, metadata: Record<string, unknown>): string | null {
  if (!metadata || Object.keys(metadata).length === 0) return null;
  const m = metadata;

  switch (action) {
    case "INVESTMENT_CREATED": {
      const amount = pickString(m, "amount");
      const currency = pickString(m, "currency");
      const escrow = pickString(m, "escrow_reference");
      const parts: string[] = [];
      if (amount && currency) parts.push(`${currency} ${amount}`);
      else if (amount) parts.push(amount);
      if (escrow) parts.push(`escrow ${escrow}`);
      return parts.length > 0 ? parts.join(" · ") : null;
    }
    case "INVESTMENT_BLOCKED":
    case "INVESTMENT_FAILED": {
      const reason = pickString(m, "reason");
      return reason ? humanizeReason(reason) : null;
    }
    case "INVESTMENT_IDEMPOTENT_REPLAY":
      return "Same key + body — replayed cached response.";
    case "KYC_SUBMITTED": {
      const attempt = pickNumber(m, "attempt");
      const status = pickString(m, "status");
      const parts: string[] = [];
      if (attempt) parts.push(`attempt ${attempt}`);
      if (status) parts.push(humanizeReason(status));
      return parts.length > 0 ? parts.join(" · ") : null;
    }
    case "KYC_RETRY_EXHAUSTED":
      return "All retry attempts used.";
    case "ACCREDITATION_SUBMITTED": {
      const attempt = pickNumber(m, "attempt");
      return attempt ? `attempt ${attempt}` : null;
    }
    case "ACCREDITATION_RESOLVED": {
      const status = pickString(m, "status");
      const reason = pickString(m, "failure_reason");
      if (status === "success") return "Verified as accredited investor.";
      if (status === "failed") return reason ? humanizeReason(reason) : "Not accredited.";
      return null;
    }
    case "BANK_LINKED": {
      const bank = pickString(m, "bank_name");
      const last_four = pickString(m, "last_four");
      if (bank && last_four) return `${bank} ••• ${last_four}`;
      return bank ?? null;
    }
    case "BANK_LINK_FAILED": {
      const reason = pickString(m, "reason");
      return reason ? humanizeReason(reason) : null;
    }
    case "BANK_UNLINKED":
      return null;
    case "AUTH_SIGNUP":
    case "AUTH_LOGIN":
    case "AUTH_LOGOUT":
    case "AUTH_REFRESH":
      return null;
    case "AUTH_LOGIN_FAILED": {
      const reason = pickString(m, "reason");
      return reason ? humanizeReason(reason) : null;
    }
    case "AUTH_REFRESH_REUSE_DETECTED":
      return "Token family revoked.";
    case "PROFILE_UPDATED": {
      const fields = pickStringArray(m, "fields");
      return fields && fields.length > 0
        ? `Updated ${fields.map(humanizeFieldName).join(", ")}`
        : null;
    }
    default:
      return null;
  }
}

/**
 * Human "x ago" rendering. Falls back to a localized date for
 * anything older than ~30 days so the relative copy stays honest.
 */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const ts = new Date(iso);
  const deltaMs = now.getTime() - ts.getTime();
  const sec = Math.round(deltaMs / 1000);
  if (sec < 5) return "just now";
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr} hr ago`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day} day${day === 1 ? "" : "s"} ago`;
  return ts.toLocaleDateString();
}

// ---------- helpers ----------

function pickString(m: Record<string, unknown>, key: string): string | undefined {
  const v = m[key];
  return typeof v === "string" ? v : undefined;
}

function pickNumber(m: Record<string, unknown>, key: string): number | undefined {
  const v = m[key];
  return typeof v === "number" ? v : undefined;
}

function pickStringArray(m: Record<string, unknown>, key: string): string[] | undefined {
  const v = m[key];
  return Array.isArray(v) && v.every((x) => typeof x === "string") ? (v as string[]) : undefined;
}

function humanizeReason(value: string): string {
  // "insufficient_balance" → "Insufficient balance"
  // "document_quality_insufficient" → "Document quality insufficient"
  return toTitleCase(value);
}

function humanizeFieldName(field: string): string {
  return field.replaceAll("_", " ");
}

function toTitleCase(raw: string): string {
  if (!raw) return raw;
  const lower = raw.toLowerCase().replaceAll(/[_-]+/g, " ");
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}
