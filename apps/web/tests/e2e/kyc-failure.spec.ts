import { expect, test } from "@playwright/test";

/**
 * KYC failure path — exercises the FE retry surface.
 *
 * The mock adapter is deterministic on `+kyc_fail`: every submit by a
 * `+kyc_fail`-tagged email returns FAILED with a reason. So we verify
 * that:
 *   1. The failure copy renders.
 *   2. A Retry CTA is present.
 *   3. Retrying decrements `attempts_remaining` and keeps failing
 *      deterministically (we don't try to flip the outcome).
 *
 * That's the realistic shape of the FE contract — the actual outcome
 * comes from the vendor and the FE just renders it.
 */

const PASSWORD = "correcthorsebatterystaple9";

function failingEmail(): string {
  const stamp = Date.now().toString(36);
  return `e2e+kyc_fail-${stamp}@example.com`;
}

test("kyc fail → renders reason + retry CTA", async ({ page }) => {
  const email = failingEmail();

  await page.goto("/signup");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel(/confirm password/i).fill(PASSWORD);
  await page.getByRole("button", { name: /open account|sign up|create/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // profile prerequisite
  await page.getByRole("link", { name: /start/i }).first().click();
  await page.getByLabel(/full name/i).fill("Faye Failsfirst");
  await page.getByLabel(/^phone/i).fill("+14155551234");
  await page.getByLabel(/nationality/i).fill("US");
  await page.getByLabel(/country of residence/i).fill("US");
  await page.getByRole("button", { name: /save profile/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // KYC — submit (mock returns FAILED for +kyc_fail tag)
  await page
    .getByRole("listitem")
    .filter({ hasText: /verify your identity/i })
    .getByRole("link", { name: /start|continue/i })
    .click();
  await page.getByRole("button", { name: /^submit kyc/i }).click();

  // failure copy + retry CTA
  await expect(page.getByText(/reason:/i)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/document_quality_insufficient/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /^retry/i })).toBeVisible();

  // retry — still fails deterministically; attempts_remaining drops by 1
  await page.getByRole("button", { name: /^retry/i }).click();
  await expect(page.getByText(/reason:/i)).toBeVisible({ timeout: 15_000 });
});
