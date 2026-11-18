import { describe, expect, it } from "vitest";

import { serializeEnv } from "@/lib/runtime-env";

describe("serializeEnv", () => {
  it("emits the configured values and trims trailing slashes", () => {
    const script = serializeEnv({
      API_URL: "https://api.example.com/",
      PRODUCT_NAME: "Acme Memory",
    });
    expect(script).toBe('window.__TP__={"apiUrl":"https://api.example.com","productName":"Acme Memory"};');
  });

  it("falls back to local defaults", () => {
    const script = serializeEnv({});
    expect(script).toContain('"apiUrl":"http://localhost:8210"');
    expect(script).toContain('"productName":"Euron TokenProfiler"');
  });

  it("cannot close the script tag it is served in", () => {
    const script = serializeEnv({ PRODUCT_NAME: "</script><script>alert(1)</script>" });
    expect(script).not.toContain("</script>");
  });
});
