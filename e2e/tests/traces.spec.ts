import { expect, test } from "@playwright/test";

import { apiGet, defaultProject, signIn } from "../helpers";

type Trace = { id: string; name: string; span_count: number; status: string };

test("filter failures, open a trace and read its span tree", async ({ page }) => {
  await signIn(page, "admin");
  await page.goto("/traces?range=14d");
  await expect(page.getByRole("heading", { level: 1, name: "Traces" })).toBeVisible();
  const table = page.getByRole("region", { name: "Traces" });
  await expect(table.getByRole("row").nth(1)).toBeVisible();

  await page.getByLabel("Status").selectOption("error");
  await expect(page).toHaveURL(/status=error/);
  await expect(table.getByText("Error", { exact: true }).first()).toBeVisible();
  await expect(table.getByText("OK", { exact: true })).toHaveCount(0);

  await page.getByLabel("Status").selectOption("");
  await page.getByLabel("Agent").selectOption("research-agent");
  await page.getByLabel("Sort").selectOption("cost");
  await expect(page).toHaveURL(/agent=research-agent/);
  await table.getByRole("link").first().click();
  await expect(page).toHaveURL(/\/traces\/[0-9a-f]{32}/);

  const spans = page.getByRole("list", { name: "Spans" });
  await expect(spans.getByRole("listitem").first()).toBeVisible();
  await expect(spans.getByText("research-agent").first()).toBeVisible();
  await expect(spans.getByText("web_search").first()).toBeVisible();
  await expect(page.getByText("Model calls")).toBeVisible();

  // Collapse the root: its subtree disappears, expanding brings it back.
  const rows = await spans.getByRole("listitem").count();
  await page.getByRole("button", { name: "Collapse research-agent" }).click();
  await expect(spans.getByRole("listitem")).toHaveCount(1);
  await page.getByRole("button", { name: "Expand research-agent" }).click();
  await expect(spans.getByRole("listitem")).toHaveCount(rows);

  await spans
    .getByRole("button", { name: /^web_search/ })
    .first()
    .click();
  await expect(page).toHaveURL(/span=/);
});

test("search finds a trace by user and the API agrees", async ({ page }) => {
  await signIn(page, "admin");
  const project = await defaultProject(page);
  const sample = await apiGet<{ items: { user_id: string | null }[] }>(
    page,
    `/projects/${project.id}/traces?range=14d&limit=20`,
  );
  const user = sample.items.find((t) => t.user_id)?.user_id ?? "";
  expect(user).not.toBe("");
  await page.goto("/traces?range=14d");
  await page.getByRole("searchbox", { name: "Search traces" }).fill(user);
  await expect(page).toHaveURL(new RegExp(`q=${user}`));
  const table = page.getByRole("region", { name: "Traces" });
  await expect(table.getByRole("link", { name: user }).first()).toBeVisible();
  const api = await apiGet<{ total: number }>(page, `/projects/${project.id}/traces?range=14d&q=${user}`);
  expect(api.total).toBeGreaterThan(0);
});

test("a trace id that does not exist says so", async ({ page }) => {
  await signIn(page, "admin");
  await page.goto("/traces/ffffffffffffffffffffffffffffffff");
  await expect(page.getByText("Trace not found").first()).toBeVisible();
});
