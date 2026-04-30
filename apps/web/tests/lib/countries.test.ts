import { describe, expect, it } from "vitest";

import { COUNTRIES, findCountry } from "@/lib/countries";

describe("countries", () => {
  it("includes the popular markets at the top of the list", () => {
    const top = COUNTRIES.slice(0, 10).map((c) => c.code);
    expect(top).toEqual(["US", "GB", "IN", "AE", "SG", "DE", "FR", "CA", "AU", "CH"]);
  });

  it("has unique ISO-2 codes", () => {
    const codes = new Set(COUNTRIES.map((c) => c.code));
    expect(codes.size).toBe(COUNTRIES.length);
  });

  it("ships ~190 entries", () => {
    expect(COUNTRIES.length).toBeGreaterThan(180);
    expect(COUNTRIES.length).toBeLessThan(220);
  });

  it("findCountry resolves by uppercase code", () => {
    expect(findCountry("US")?.name).toBe("United States");
    expect(findCountry("IN")?.name).toBe("India");
    expect(findCountry("us")?.name).toBe("United States");
    expect(findCountry("xx")).toBeUndefined();
    expect(findCountry(undefined)).toBeUndefined();
    expect(findCountry("")).toBeUndefined();
  });

  it("each country has a non-empty dial code", () => {
    for (const c of COUNTRIES) {
      expect(c.dial).toMatch(/^\d+$/);
    }
  });
});
