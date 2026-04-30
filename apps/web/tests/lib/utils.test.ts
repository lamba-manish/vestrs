import { describe, expect, it } from "vitest";

import { cn } from "@/lib/utils";

describe("cn", () => {
  it("joins truthy classes", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("filters falsy values", () => {
    expect(cn("a", false && "b", null, undefined, "c")).toBe("a c");
  });

  it("dedupes conflicting tailwind classes (last wins)", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
  });

  it("merges variants in object form", () => {
    expect(cn({ "rounded-md": true, "rounded-none": false })).toBe("rounded-md");
  });
});
