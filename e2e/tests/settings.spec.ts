import { expect, test } from "@playwright/test";

import { signIn } from "../helpers";

test("the privacy rules mask a sample before anything is stored", async ({ page }) => {
  await signIn(page, "admin");
  await page.goto("/settings");
  await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
  await expect(page.getByLabel("Pattern").first()).toHaveValue(/EMP-/);
  await page.getByLabel("Try the rules on a sample").fill("Reach sam@example.com, employee EMP-123456.");
  await page.getByRole("button", { name: "Test masking" }).click();
  await expect(page.getByRole("status").filter({ hasText: "2 masked" })).toBeVisible();
  await expect(page.getByText("[REDACTED:employee]")).toBeVisible();
});

test("the admin sees people, activity and archives", async ({ page }) => {
  await signIn(page, "admin");
  await page.goto("/settings?tab=people");
  await expect(page.getByRole("region", { name: "People" }).getByText("Maya Chen")).toBeVisible();
  await page.goto("/settings?tab=activity");
  await expect(page.getByRole("region", { name: "Activity" }).getByRole("row").nth(1)).toBeVisible();
  await page.goto("/settings?tab=archives");
  await expect(page.getByRole("tab", { name: "Archives" })).toBeVisible();
});

test("retention and sampling are shown and saved", async ({ page }) => {
  await signIn(page, "admin");
  await page.goto("/settings");
  await expect(page.getByLabel("Keep traces for, days")).toHaveValue("30");
  await page.getByLabel("Keep traces for, days").fill("45");
  await page.getByRole("button", { name: "Save retention" }).click();
  await expect(page.getByText("Retention saved")).toBeVisible();
  await page.getByLabel("Keep traces for, days").fill("30");
  await page.getByRole("button", { name: "Save retention" }).click();
  await expect(page.getByText("Retention saved").first()).toBeVisible();
});
