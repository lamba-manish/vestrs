import { describe, expect, it } from "vitest";

import { actionLabel, describeMetadata, relativeTime, statusLabel } from "@/lib/audit-format";

describe("actionLabel", () => {
  it("maps known codes to user-facing labels", () => {
    expect(actionLabel("KYC_SUBMITTED")).toBe("KYC submitted");
    expect(actionLabel("INVESTMENT_CREATED")).toBe("Investment placed");
    expect(actionLabel("BANK_LINKED")).toBe("Bank linked");
    expect(actionLabel("AUTH_SIGNUP")).toBe("Account created");
    expect(actionLabel("ACCREDITATION_RESOLVED")).toBe("Accreditation resolved");
  });

  it("falls back to title-case for unknown codes (forward compat)", () => {
    expect(actionLabel("FOO_BAR_BAZ")).toBe("Foo bar baz");
  });
});

describe("statusLabel", () => {
  it("title-cases statuses", () => {
    expect(statusLabel("success")).toBe("Success");
    expect(statusLabel("failure")).toBe("Failed");
    expect(statusLabel("pending")).toBe("Pending");
  });
});

describe("describeMetadata", () => {
  it("returns null for empty metadata", () => {
    expect(describeMetadata("KYC_SUBMITTED", {})).toBeNull();
  });

  it("formats INVESTMENT_CREATED amount + currency + escrow", () => {
    expect(
      describeMetadata("INVESTMENT_CREATED", {
        amount: "1500.00",
        currency: "USD",
        escrow_reference: "escrow-abc123",
      }),
    ).toBe("USD 1500.00 · escrow escrow-abc123");
  });

  it("humanizes INVESTMENT_BLOCKED reason", () => {
    expect(describeMetadata("INVESTMENT_BLOCKED", { reason: "insufficient_balance" })).toBe(
      "Insufficient balance",
    );
  });

  it("formats BANK_LINKED with bank + last_four", () => {
    expect(describeMetadata("BANK_LINKED", { bank_name: "Chase", last_four: "6789" })).toBe(
      "Chase ••• 6789",
    );
  });

  it("formats KYC_SUBMITTED attempt", () => {
    expect(describeMetadata("KYC_SUBMITTED", { attempt: 2 })).toBe("attempt 2");
  });

  it("renders ACCREDITATION_RESOLVED outcomes", () => {
    expect(describeMetadata("ACCREDITATION_RESOLVED", { status: "success" })).toBe(
      "Verified as accredited investor.",
    );
    expect(
      describeMetadata("ACCREDITATION_RESOLVED", {
        status: "failed",
        failure_reason: "income_threshold_not_met",
      }),
    ).toBe("Income threshold not met");
  });

  it("returns null for actions whose metadata is internal-only", () => {
    expect(describeMetadata("AUTH_LOGIN", {})).toBeNull();
    expect(describeMetadata("BANK_UNLINKED", { foo: "bar" })).toBeNull();
  });

  it("formats PROFILE_UPDATED field list", () => {
    expect(describeMetadata("PROFILE_UPDATED", { fields: ["full_name", "phone"] })).toBe(
      "Updated full name, phone",
    );
  });
});

describe("relativeTime", () => {
  const fixedNow = new Date("2026-04-30T12:00:00Z");

  it("renders 'just now' for sub-5s", () => {
    expect(relativeTime("2026-04-30T11:59:58Z", fixedNow)).toBe("just now");
  });

  it("renders seconds < 60", () => {
    expect(relativeTime("2026-04-30T11:59:30Z", fixedNow)).toBe("30s ago");
  });

  it("renders minutes < 60", () => {
    expect(relativeTime("2026-04-30T11:45:00Z", fixedNow)).toBe("15 min ago");
  });

  it("renders hours < 24", () => {
    expect(relativeTime("2026-04-30T08:00:00Z", fixedNow)).toBe("4 hr ago");
  });

  it("renders days < 30", () => {
    expect(relativeTime("2026-04-25T12:00:00Z", fixedNow)).toBe("5 days ago");
    expect(relativeTime("2026-04-29T12:00:00Z", fixedNow)).toBe("1 day ago");
  });

  it("falls back to a localized date for old entries", () => {
    const out = relativeTime("2026-01-01T12:00:00Z", fixedNow);
    expect(out).not.toMatch(/ago|just now/);
  });
});
