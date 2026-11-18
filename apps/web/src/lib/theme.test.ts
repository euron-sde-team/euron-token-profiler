import { describe, expect, it } from "vitest";

import { parseTheme, resolveTheme } from "@/lib/theme";
import { THEME_SCRIPT } from "@/lib/theme-script";

describe("theme", () => {
  it("treats anything but light and dark as system", () => {
    expect(parseTheme("dark")).toBe("dark");
    expect(parseTheme("light")).toBe("light");
    expect(parseTheme("system")).toBe("system");
    expect(parseTheme("sepia")).toBe("system");
    expect(parseTheme(null)).toBe("system");
  });

  it("resolves the system choice from the operating system", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("ships a pre-paint script that reads the same storage key", () => {
    expect(THEME_SCRIPT).toContain("tokenprofiler-theme");
    expect(THEME_SCRIPT).toContain("prefers-color-scheme: dark");
  });
});
