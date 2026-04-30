import { describe, expect, it } from "vitest";

import { composePhone, profileFormSchema, splitPhone } from "@/lib/schemas/profile";

describe("profileFormSchema", () => {
  const valid = {
    full_name: "Manish Lamba",
    nationality: "IN",
    domicile: "IN",
    phone_country: "IN",
    phone_number: "9876543210",
  };

  it("accepts a well-formed profile", () => {
    expect(profileFormSchema.safeParse(valid).success).toBe(true);
  });

  it("rejects full_name shorter than 2", () => {
    const r = profileFormSchema.safeParse({ ...valid, full_name: "M" });
    expect(r.success).toBe(false);
  });

  it("rejects unknown ISO-2 codes", () => {
    expect(profileFormSchema.safeParse({ ...valid, nationality: "XX" }).success).toBe(false);
    expect(profileFormSchema.safeParse({ ...valid, domicile: "ZZ" }).success).toBe(false);
  });

  it("uppercases ISO codes via the transform", () => {
    const r = profileFormSchema.safeParse({ ...valid, nationality: "in", domicile: "us" });
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.nationality).toBe("IN");
      expect(r.data.domicile).toBe("US");
    }
  });

  it("rejects non-digit phone bodies", () => {
    const r = profileFormSchema.safeParse({ ...valid, phone_number: "abc-123" });
    expect(r.success).toBe(false);
  });

  it("rejects too-short phone bodies", () => {
    const r = profileFormSchema.safeParse({ ...valid, phone_number: "12345" });
    expect(r.success).toBe(false);
  });
});

describe("composePhone", () => {
  it("builds an E.164 string from the country dial + national number", () => {
    expect(
      composePhone({
        full_name: "x",
        nationality: "IN",
        domicile: "IN",
        phone_country: "IN",
        phone_number: "9876543210",
      }),
    ).toBe("+919876543210");
  });

  it("strips non-digit chars from the national number", () => {
    expect(
      composePhone({
        full_name: "x",
        nationality: "US",
        domicile: "US",
        phone_country: "US",
        phone_number: "415-555-1234",
      }),
    ).toBe("+14155551234");
  });

  it("returns empty string when phone_country is unknown", () => {
    expect(
      composePhone({
        full_name: "x",
        nationality: "US",
        domicile: "US",
        phone_country: "XX",
        phone_number: "1234567890",
      }),
    ).toBe("");
  });
});

describe("splitPhone", () => {
  it("splits +91… into IN + national", () => {
    expect(splitPhone("+919876543210", "IN")).toEqual({
      phone_country: "IN",
      phone_number: "9876543210",
    });
  });

  it("prefers the longest-prefix dial-code match", () => {
    // +1268 (Antigua) vs +1 (US). The US/Canada dial is "1"; Antigua is "1268".
    expect(splitPhone("+12684641234", "US")).toEqual({
      phone_country: "AG",
      phone_number: "4641234",
    });
  });

  it("falls back to the domicile when phone is empty", () => {
    expect(splitPhone(null, "IN")).toEqual({ phone_country: "IN", phone_number: "" });
    expect(splitPhone(undefined, undefined)).toEqual({
      phone_country: "US",
      phone_number: "",
    });
  });

  it("falls back to the domicile when no dial code matches", () => {
    expect(splitPhone("+9999999999", "IN")).toEqual({
      phone_country: "IN",
      phone_number: "9999999999",
    });
  });
});
