import { describe, expect, it } from "vitest";

import { PASSWORD_RULES, signupSchema } from "@/lib/schemas/auth";

describe("PASSWORD_RULES", () => {
  it("flags missing length, case, digit, and symbol", () => {
    const r = (id: string) => PASSWORD_RULES.find((x) => x.id === id)!;
    expect(r("len").test("short")).toBe(false);
    expect(r("len").test("twelve-chars")).toBe(true);

    expect(r("lower").test("ALLCAPS123!")).toBe(false);
    expect(r("lower").test("hasLower1!")).toBe(true);

    expect(r("upper").test("alllower123!")).toBe(false);
    expect(r("upper").test("HasUpper1!")).toBe(true);

    expect(r("digit").test("NoDigitsAtAll!")).toBe(false);
    expect(r("digit").test("HasDigit1")).toBe(true);

    expect(r("symbol").test("NoSymbolAt1All")).toBe(false);
    expect(r("symbol").test("HasSymbol1!")).toBe(true);
  });
});

describe("signupSchema", () => {
  const ok = {
    email: "manish@example.com",
    password: "Strong-Password-1!",
    confirm_password: "Strong-Password-1!",
  };

  it("accepts a well-formed signup", () => {
    expect(signupSchema.safeParse(ok).success).toBe(true);
  });

  it("rejects mismatched confirm_password", () => {
    const r = signupSchema.safeParse({ ...ok, confirm_password: "different" });
    expect(r.success).toBe(false);
    if (!r.success) {
      const paths = r.error.issues.map((i) => i.path.join("."));
      expect(paths).toContain("confirm_password");
    }
  });

  it("rejects an invalid email", () => {
    expect(signupSchema.safeParse({ ...ok, email: "not-an-email" }).success).toBe(false);
  });

  it("rejects a password that fails any one rule", () => {
    // missing symbol
    expect(
      signupSchema.safeParse({
        ...ok,
        password: "NoSymbol123Long",
        confirm_password: "NoSymbol123Long",
      }).success,
    ).toBe(false);
    // missing digit
    expect(
      signupSchema.safeParse({
        ...ok,
        password: "NoDigitsHere!!",
        confirm_password: "NoDigitsHere!!",
      }).success,
    ).toBe(false);
    // too short
    expect(
      signupSchema.safeParse({ ...ok, password: "Short1!", confirm_password: "Short1!" }).success,
    ).toBe(false);
  });

  it("caps password length at 128", () => {
    const tooLong = "Aa1!" + "x".repeat(130);
    expect(
      signupSchema.safeParse({ ...ok, password: tooLong, confirm_password: tooLong }).success,
    ).toBe(false);
  });
});
