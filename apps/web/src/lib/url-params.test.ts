import { describe, expect, it } from "vitest";

import { mergeParams } from "@/lib/url-params";

describe("mergeParams", () => {
  it("sets, replaces and removes keys", () => {
    const current = new URLSearchParams("user_id=amelia.novak&offset=50&q=sushi");
    expect(mergeParams(current, { offset: null, q: "jazz", pinned: true })).toBe(
      "user_id=amelia.novak&q=jazz&pinned=true",
    );
  });

  it("drops empty and false values", () => {
    const current = new URLSearchParams("q=a&pinned=true");
    expect(mergeParams(current, { q: "", pinned: false, agent_id: undefined })).toBe("");
  });

  it("repeats array values", () => {
    const current = new URLSearchParams("category=event");
    expect(mergeParams(current, { category: ["fact", "preference"] })).toBe("category=fact&category=preference");
    expect(mergeParams(current, { category: [] })).toBe("");
  });

  it("does not change the params it was given", () => {
    const current = new URLSearchParams("a=1");
    mergeParams(current, { a: null });
    expect(current.toString()).toBe("a=1");
  });
});
