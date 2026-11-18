import { expect, test } from "@playwright/test";

import { signIn, unique } from "../helpers";

test("models, agents and tools break down cost and latency", async ({ page }) => {
  await signIn(page, "admin");
  await page.goto("/models?range=14d");
  const models = page.getByRole("region", { name: "Model breakdown" });
  await expect(models.getByRole("row", { name: /claude-sonnet-4-5/ })).toBeVisible();
  await expect(models.getByRole("row", { name: /gpt-4o-mini/ })).toBeVisible();

  await page.goto("/agents?range=14d");
  const agents = page.getByRole("region", { name: "Agent breakdown" });
  for (const agent of ["support-agent", "research-agent", "sql-analyst"]) {
    await expect(agents.getByRole("row", { name: new RegExp(agent) })).toBeVisible();
  }
  await page.getByRole("tab", { name: "Tools" }).click();
  await expect(page).toHaveURL(/tab=tools/);
  const tools = page.getByRole("region", { name: "Tool breakdown" });
  for (const tool of ["web_search", "vector_search", "run_sql"]) {
    await expect(tools.getByRole("row", { name: new RegExp(tool) })).toBeVisible();
  }
});

test("a price override can be added and removed", async ({ page }) => {
  const model = unique("custom-model");
  await signIn(page, "member");
  await page.goto("/models?tab=pricing");
  const prices = page.getByRole("region", { name: "Model prices" });
  await expect(prices.getByRole("row", { name: /gpt-4o\b/ }).first()).toBeVisible();
  await page.getByRole("button", { name: "Add override" }).click();
  await page.getByLabel("Model name").fill(model);
  await page.getByLabel("Input, USD per 1M").fill("0.5");
  await page.getByLabel("Output, USD per 1M").fill("1.5");
  await page.getByRole("button", { name: "Save override" }).click();
  const row = prices.getByRole("row", { name: new RegExp(model) });
  await expect(row.getByText("This project")).toBeVisible();
  await row.getByRole("button", { name: `Remove override for ${model}` }).click();
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(prices.getByRole("row", { name: new RegExp(model) })).toHaveCount(0);
});
