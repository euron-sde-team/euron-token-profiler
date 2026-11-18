/**
 * Exploratory QA crawl: every page at desktop and mobile widths, signed in as the demo admin,
 * and once more in the dark theme.
 *
 * A page fails on console errors, uncaught exceptions, failed or 4xx/5xx requests, sideways
 * scrolling, broken internal links and serious or critical axe violations (WCAG 2 A and AA).
 * A capture of the whole of every page lands in e2e/.qa/ for a visual review.
 */
import { mkdirSync } from "node:fs";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { settle, signIn } from "../helpers";

const OUT = path.resolve(__dirname, "../.qa");
mkdirSync(OUT, { recursive: true });

const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 },
] as const;

type Crawl = { page: Page; label: string; problems: string[]; links: Set<string> };

function watch(page: Page, label: string): Crawl {
  const crawl: Crawl = { page, label, problems: [], links: new Set() };
  page.on("console", (message) => {
    if (message.type() === "error") crawl.problems.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => crawl.problems.push(`uncaught: ${error.message}`));
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText ?? "";
    // Aborted requests are navigations away or cancelled queries, not failures.
    if (!reason.includes("ERR_ABORTED")) crawl.problems.push(`request failed: ${request.url()} ${reason}`);
  });
  page.on("response", (response) => {
    if (response.status() >= 400) crawl.problems.push(`HTTP ${response.status()}: ${response.url()}`);
  });
  return crawl;
}

/** Capture the whole page: the app scrolls inside <main>, so grow the window to fit it. */
async function captureWhole(page: Page, file: string): Promise<void> {
  const size = page.viewportSize();
  if (!size) return;
  const needed = await page.evaluate(() => {
    const main = document.querySelector("main");
    if (!main) return 0;
    return Math.ceil(main.scrollHeight + main.getBoundingClientRect().top);
  });
  const height = Math.min(Math.max(needed, size.height), 5000);
  if (height > size.height) await page.setViewportSize({ width: size.width, height });
  await page.waitForTimeout(250);
  await page.screenshot({ path: file });
  if (height > size.height) await page.setViewportSize(size);
}

async function inspect(crawl: Crawl, name: string): Promise<void> {
  const { page } = crawl;
  await settle(page);
  // The app shell scrolls inside <main>, so sideways overflow can hide there too. Code and
  // diffs scroll inside their own containers and do not count.
  const overflow = await page.evaluate(() => {
    const outer = document.documentElement.scrollWidth - window.innerWidth;
    const main = document.querySelector("main");
    return Math.max(outer, main ? main.scrollWidth - main.clientWidth : 0);
  });
  if (overflow > 1) crawl.problems.push(`${name}: scrolls sideways by ${overflow}px`);

  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  for (const violation of axe.violations) {
    if (violation.impact !== "serious" && violation.impact !== "critical") continue;
    const nodes = violation.nodes
      .slice(0, 3)
      .map((node) => node.target.join(" "))
      .join(" | ");
    crawl.problems.push(`${name}: axe ${violation.id} (${violation.impact}) at ${nodes}`);
  }

  const hrefs = await page.$$eval('a[href^="/"]', (anchors) => anchors.map((a) => a.getAttribute("href") ?? ""));
  for (const href of hrefs) crawl.links.add(href.split("#")[0] ?? href);
  await captureWhole(page, path.join(OUT, `${crawl.label}-${name}.png`));
}

/** What shows that a page has loaded: its title (a string) or some text (`{ text }`). */
type Ready = string | { text: string };

async function visit(crawl: Crawl, name: string, url: string, ready?: Ready): Promise<void> {
  const response = await crawl.page.goto(url);
  expect(response?.status(), url).toBeLessThan(400);
  if (ready) {
    // Scoped to the page content: on phones the sidebar (and its links) is off screen.
    const main = crawl.page.getByRole("main");
    const shown =
      typeof ready === "string"
        ? main.getByRole("heading", { level: 1, name: ready })
        : main.getByText(ready.text).first();
    await expect(shown).toBeVisible();
  }
  await inspect(crawl, name);
}

/** Every page of the web app, with the states that hide things behind a click. */
async function crawlApp(page: Page, crawl: Crawl): Promise<void> {
  await visit(crawl, "overview", "/overview", "Overview");
  await page.getByRole("radio", { name: "14 days" }).click();
  await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
  await inspect(crawl, "overview-14d");

  await visit(crawl, "traces", "/traces?range=7d", "Traces");
  await expect(page.getByRole("region", { name: "Traces" }).getByRole("row").nth(2)).toBeVisible();
  await page.getByLabel("Status").selectOption("error");
  await expect(page).toHaveURL(/status=error/);
  await inspect(crawl, "traces-errors");
  await page.getByRole("region", { name: "Traces" }).getByRole("link").first().click();
  await expect(page.getByRole("list", { name: "Spans" }).getByRole("listitem").first()).toBeVisible();
  await inspect(crawl, "trace-detail");

  await visit(crawl, "prompts", "/prompts", "Prompts");
  await page.getByRole("link", { name: "sql-generator" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "sql-generator" })).toBeVisible();
  await inspect(crawl, "prompt-detail");
  await page.getByRole("button", { name: "New version" }).click();
  await expect(page.getByRole("dialog", { name: /New version of/ })).toBeVisible();
  await inspect(crawl, "prompt-dialog");
  await page.keyboard.press("Escape");

  await visit(crawl, "models", "/models", "Models");
  await expect(page.getByRole("region", { name: "Model breakdown" })).toBeVisible();
  await page.getByRole("tab", { name: "Pricing" }).click();
  await expect(page.getByRole("region", { name: "Model prices" })).toBeVisible();
  await inspect(crawl, "models-pricing");

  await visit(crawl, "agents", "/agents", "Agents and tools");
  await expect(page.getByRole("region", { name: "Agent breakdown" })).toBeVisible();
  await page.getByRole("tab", { name: "Tools" }).click();
  await expect(page.getByRole("region", { name: "Tool breakdown" })).toBeVisible();
  await inspect(crawl, "tools");

  await visit(crawl, "budgets", "/budgets", "Budgets and alerts");
  await expect(page.getByRole("progressbar").first()).toBeVisible();
  await page.getByRole("button", { name: "New budget" }).click();
  await expect(page.getByRole("dialog", { name: "New budget" })).toBeVisible();
  await inspect(crawl, "budget-dialog");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "New rule" }).click();
  await expect(page.getByRole("dialog", { name: "New alert rule" })).toBeVisible();
  await inspect(crawl, "rule-dialog");
  await page.keyboard.press("Escape");

  await visit(crawl, "keys", "/keys", "API keys");
  await page.getByRole("button", { name: "Create key" }).first().click();
  await expect(page.getByRole("dialog", { name: "Create an API key" })).toBeVisible();
  await inspect(crawl, "key-dialog");
  await page.keyboard.press("Escape");

  await visit(crawl, "settings", "/settings", "Settings");
  for (const tab of ["people", "activity", "archives", "account"]) {
    await visit(crawl, `settings-${tab}`, `/settings?tab=${tab}`, "Settings");
  }
}

for (const viewport of VIEWPORTS) {
  test.describe(`${viewport.name} ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });
    test.setTimeout(600_000);

    test("signed-out pages", async ({ page }) => {
      const crawl = watch(page, viewport.name);
      await visit(crawl, "sign-in", "/login", { text: "Welcome back" });
      expect(crawl.problems).toEqual([]);
    });

    test("every page", async ({ page }) => {
      await signIn(page, "admin");
      const crawl = watch(page, viewport.name);
      await crawlApp(page, crawl);
      expect(crawl.problems, crawl.problems.join("\n")).toEqual([]);

      // Every internal link the crawl saw leads somewhere that exists.
      const broken: string[] = [];
      for (const href of crawl.links) {
        if (href === "") continue;
        const response = await page.request.get(new URL(href, page.url()).toString());
        if (response.status() >= 400) broken.push(`${response.status()} ${href}`);
      }
      expect(broken, "broken internal links").toEqual([]);
    });
  });
}

test.describe("dark theme", () => {
  test.use({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });
  test.setTimeout(600_000);

  test("every page", async ({ page }) => {
    await signIn(page, "admin");
    await page.evaluate(() => localStorage.setItem("tokenprofiler-theme", "dark"));
    const crawl = watch(page, "dark");
    await crawlApp(page, crawl);
    expect(crawl.problems, crawl.problems.join("\n")).toEqual([]);
  });
});
