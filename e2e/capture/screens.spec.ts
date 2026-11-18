/**
 * README screenshots (1440x900 at 2x) and tour frames, from the seeded demo data.
 * Every image shows the real stack: nothing here is mocked. Run this right after
 * `make demo`, before the e2e suite adds its scratch models, keys and benchmarks.
 */
import { mkdirSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { API_URL, settle, signIn } from "../helpers";

const SHOTS = path.resolve(__dirname, "../../docs/assets/screenshots");
const FRAMES = path.resolve(__dirname, "../.capture/frames");
mkdirSync(SHOTS, { recursive: true });
mkdirSync(FRAMES, { recursive: true });

let frame = 0;

async function shot(page: Page, name: string): Promise<void> {
  await settle(page);
  // Clicking inside a long page scrolls the app's own scroll area: start every picture at the top.
  await page.evaluate(() => document.querySelector("main")?.scrollTo(0, 0));
  // The clicked control keeps a keyboard focus ring: the picture is of the page.
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
}

async function tourFrame(page: Page, holdMs = 1800): Promise<void> {
  frame += 1;
  const file = path.join(FRAMES, `${String(frame).padStart(3, "0")}-${holdMs}.png`);
  await page.screenshot({ path: file, scale: "css" });
}

test.describe.configure({ mode: "serial" });
test.setTimeout(300_000);

test("sign-in page", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("See what every token does and what it costs.")).toBeVisible();
  await shot(page, "00-sign-in");
  await tourFrame(page, 1600);
});

type Row = { id: string; span_count: number };

/** A trace of the given agent that is rich enough to read, found through the API. */
async function pickTrace(page: Page, agent: string, spans: [number, number]): Promise<string> {
  const projects = await page.request.get(`${API_URL}/api/v1/projects`);
  const project = (await projects.json()).items[0] as { id: string };
  const list = await page.request.get(
    `${API_URL}/api/v1/projects/${project.id}/traces?range=7d&agent=${agent}&limit=100&sort=cost`,
  );
  const items = ((await list.json()).items as Row[]).filter(
    (t) => t.span_count >= spans[0] && t.span_count <= spans[1],
  );
  expect(items.length).toBeGreaterThan(0);
  return items[0]!.id;
}

test("the web app, page by page", async ({ page }) => {
  await signIn(page, "admin");

  await page.goto("/overview?range=7d");
  await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
  await expect(page.getByText("Top models")).toBeVisible();
  await expect(page.getByText("claude-sonnet-4-5").first()).toBeVisible();
  await shot(page, "01-overview");
  await tourFrame(page, 3000);

  await page.goto("/traces?range=7d");
  await expect(page.getByRole("region", { name: "Traces" }).getByRole("row").nth(5)).toBeVisible();
  await shot(page, "02-traces");
  await tourFrame(page, 2400);

  const research = await pickTrace(page, "research-agent", [12, 24]);
  await page.goto(`/traces/${research}`);
  await expect(page.getByRole("list", { name: "Spans" }).getByText("web_search").first()).toBeVisible();
  await page
    .getByRole("list", { name: "Spans" })
    .getByRole("button", { name: /synthesise-report/ })
    .click();
  await expect(page.getByText("Total cost").first()).toBeVisible();
  await shot(page, "03-trace-waterfall");
  await tourFrame(page, 3200);

  await page.goto("/traces?range=14d&status=error");
  await expect(page.getByRole("region", { name: "Traces" }).getByRole("row").nth(3)).toBeVisible();
  await shot(page, "04-trace-errors");

  await page.goto("/prompts?range=14d");
  await expect(page.getByRole("link", { name: "support-triage" })).toBeVisible();
  await shot(page, "05-prompts");
  await tourFrame(page, 2200);

  await page.goto("/prompts/view?name=support-triage&range=14d");
  await expect(page.getByText("Cost per 1,000 calls by version")).toBeVisible();
  await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
  await shot(page, "06-prompt-versions");
  await tourFrame(page, 3000);

  await page.goto("/models?range=14d");
  await expect(page.getByRole("region", { name: "Model breakdown" }).getByRole("row").nth(6)).toBeVisible();
  await shot(page, "07-models");
  await tourFrame(page, 2600);

  await page.goto("/models?tab=pricing");
  await expect(page.getByRole("region", { name: "Model prices" }).getByRole("row").nth(8)).toBeVisible();
  await shot(page, "08-pricing");

  await page.goto("/agents?range=14d");
  await expect(page.getByRole("region", { name: "Agent breakdown" }).getByRole("row").nth(3)).toBeVisible();
  await shot(page, "09-agents");
  await tourFrame(page, 2600);
  await page.getByRole("tab", { name: "Tools" }).click();
  await expect(page.getByRole("region", { name: "Tool breakdown" }).getByRole("row").nth(4)).toBeVisible();
  await shot(page, "10-tools");

  await page.goto("/budgets");
  await expect(page.getByRole("progressbar").first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Alert history" })).toBeVisible();
  await shot(page, "11-budgets");
  await tourFrame(page, 3000);

  await page.goto("/keys");
  await expect(page.getByRole("region", { name: "API keys" }).getByText("production-sdk")).toBeVisible();
  await shot(page, "12-api-keys");
  await tourFrame(page, 2400);

  await page.goto("/settings");
  await expect(page.getByLabel("Pattern").first()).toBeVisible();
  await page.getByRole("button", { name: "Test masking" }).click();
  await expect(page.getByRole("status").filter({ hasText: "masked" })).toBeVisible();
  await shot(page, "13-settings");
  await tourFrame(page, 2600);
});

test("dark theme", async ({ page }) => {
  await signIn(page, "admin");
  await page.evaluate(() => localStorage.setItem("tokenprofiler-theme", "dark"));
  await page.goto("/overview?range=7d");
  await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
  await shot(page, "14-overview-dark");
  const research = await pickTrace(page, "support-agent", [5, 9]);
  await page.goto(`/traces/${research}`);
  await expect(page.getByRole("list", { name: "Spans" }).getByRole("listitem").first()).toBeVisible();
  await shot(page, "15-trace-dark");
});
