import { describe, expect, it } from "vitest";

import { CURRENCIES, findCurrency } from "@/lib/currencies";

describe("currencies", () => {
  it("ships ≥30 ISO-4217 codes", () => {
    expect(CURRENCIES.length).toBeGreaterThanOrEqual(30);
  });

  it("has unique codes", () => {
    const codes = new Set(CURRENCIES.map((c) => c.code));
    expect(codes.size).toBe(CURRENCIES.length);
  });

  it("findCurrency resolves by uppercase code", () => {
    expect(findCurrency("USD")?.symbol).toBe("$");
    expect(findCurrency("inr")?.name).toBe("Indian Rupee");
    expect(findCurrency("EUR")?.symbol).toBe("€");
  });

  it("returns undefined for unknown / falsy input", () => {
    expect(findCurrency("XYZ")).toBeUndefined();
    expect(findCurrency(undefined)).toBeUndefined();
    expect(findCurrency("")).toBeUndefined();
  });

  it("every currency has code, symbol, name", () => {
    for (const c of CURRENCIES) {
      expect(c.code).toMatch(/^[A-Z]{3}$/);
      expect(c.symbol.length).toBeGreaterThan(0);
      expect(c.name.length).toBeGreaterThan(0);
    }
  });
});
