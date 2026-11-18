import { describe, expect, it } from "vitest";

import { curlSnippet, otlpSnippet, pythonSnippet } from "@/lib/snippets";

const input = { apiUrl: "http://localhost:8210", key: "tp_abc_secret" };

describe("snippets", () => {
  it("carry the endpoint and the key", () => {
    for (const text of [pythonSnippet(input), otlpSnippet(input), curlSnippet(input)]) {
      expect(text).toContain("http://localhost:8210");
      expect(text).toContain("tp_abc_secret");
    }
  });

  it("use the paths the API serves", () => {
    expect(curlSnippet(input)).toContain("/v1/ingest");
    expect(otlpSnippet(input)).toContain("/v1/otlp");
  });

  it("send valid JSON from curl", () => {
    const body = /-d '([\s\S]*)'$/.exec(curlSnippet(input))?.[1] ?? "";
    expect(() => JSON.parse(body)).not.toThrow();
  });
});
