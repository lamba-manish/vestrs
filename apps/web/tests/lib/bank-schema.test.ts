import { describe, expect, it } from "vitest";

import { bankLinkFormSchema, formatAccountType } from "@/lib/schemas/bank";

describe("formatAccountType", () => {
  it("renders the canonical labels", () => {
    expect(formatAccountType("checking")).toBe("Checking");
    expect(formatAccountType("savings")).toBe("Savings");
    expect(formatAccountType("money_market")).toBe("Money market");
  });

  it("title-cases unknown values as a fallback", () => {
    expect(formatAccountType("trust_brokerage")).toBe("Trust brokerage");
    expect(formatAccountType("ira")).toBe("Ira");
  });
});

describe("bankLinkFormSchema", () => {
  const valid = {
    bank_name: "Chase",
    account_holder_name: "Manish Lamba",
    account_type: "checking" as const,
    account_number: "123456789",
    routing_number: "11000000",
    currency: "USD",
  };

  it("accepts a well-formed payload", () => {
    expect(bankLinkFormSchema.safeParse(valid).success).toBe(true);
  });

  it("uppercases the currency", () => {
    const r = bankLinkFormSchema.safeParse({ ...valid, currency: "usd" });
    expect(r.success).toBe(true);
    if (r.success) expect(r.data.currency).toBe("USD");
  });

  it("rejects non-numeric account / routing numbers", () => {
    expect(bankLinkFormSchema.safeParse({ ...valid, account_number: "12-34-56" }).success).toBe(
      false,
    );
    expect(bankLinkFormSchema.safeParse({ ...valid, routing_number: "abcd1234" }).success).toBe(
      false,
    );
  });

  it("rejects unknown account types via zod enum", () => {
    expect(bankLinkFormSchema.safeParse({ ...valid, account_type: "trust" }).success).toBe(false);
  });

  it("rejects currency strings of the wrong length", () => {
    expect(bankLinkFormSchema.safeParse({ ...valid, currency: "US" }).success).toBe(false);
    expect(bankLinkFormSchema.safeParse({ ...valid, currency: "USDS" }).success).toBe(false);
  });
});
