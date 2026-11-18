import { describe, expect, it } from "vitest";

import { isRange, rangeOr } from "@/lib/ranges";

describe("ranges", () => {
  it("accepts only the keys the API serves", () => {
    expect(isRange("24h")).toBe(true);
    expect(isRange("3y")).toBe(false);
    expect(isRange(null)).toBe(false);
  });

  it("falls back for anything else", () => {
    expect(rangeOr("14d", "24h")).toBe("14d");
    expect(rangeOr("bogus", "7d")).toBe("7d");
    expect(rangeOr(null, "24h")).toBe("24h");
  });
});
