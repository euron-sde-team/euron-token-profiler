import { describe, expect, it } from "vitest";

import { prettyPayload } from "@/components/traces/span-panel";

describe("prettyPayload", () => {
  it("indents JSON", () => {
    expect(prettyPayload('{"a":[1,2]}')).toBe('{\n  "a": [\n    1,\n    2\n  ]\n}');
  });

  it("leaves other text alone", () => {
    expect(prettyPayload("plain words")).toBe("plain words");
    expect(prettyPayload("")).toBe("");
  });
});
