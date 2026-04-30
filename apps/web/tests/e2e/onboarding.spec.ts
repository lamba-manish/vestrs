import { expect, test } from "@playwright/test";

/**
 * Canonical happy-path: signup → profile → KYC → accreditation
 * (polling) → bank link → invest → audit log shows the journey.
 *
 * Each run uses a fresh email so the DB state is independent and the
 * spec is replayable without cleanup.
 */

const PASSWORD = "correcthorsebatterystaple9";

function freshEmail(): string {
  const stamp = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 7);
  return `e2e-${stamp}-${rand}@example.com`;
}

test("happy path — onboard a new investor end-to-end", async ({ page }) => {
  const email = freshEmail();

  // ---------- signup ----------
  await page.goto("/signup");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(PASSWORD);
  await page.getByRole("button", { name: /open account|sign up|create/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: /welcome/i })).toBeVisible();

  // ---------- profile ----------
  await page.getByRole("link", { name: /start/i }).first().click();
  await expect(page).toHaveURL(/\/onboarding\/profile$/);
  await page.getByLabel(/full name/i).fill("Eve E2E");
  await page.getByLabel(/^phone/i).fill("+14155551234");
  await page.getByLabel(/nationality/i).fill("US");
  await page.getByLabel(/country of residence/i).fill("US");
  await page.getByRole("button", { name: /save profile/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // ---------- KYC ----------
  await page
    .getByRole("listitem")
    .filter({ hasText: /verify your identity/i })
    .getByRole("link", { name: /start|continue/i })
    .click();
  await expect(page).toHaveURL(/\/onboarding\/kyc$/);
  await page.getByRole("button", { name: /^submit kyc/i }).click();
  await expect(page.getByText(/identity has been verified/i)).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("link", { name: /continue to accreditation/i }).click();

  // ---------- accreditation (async, polled) ----------
  await expect(page).toHaveURL(/\/onboarding\/accreditation$/);
  await page.getByRole("button", { name: /submit accreditation/i }).click();
  await expect(page.getByText(/accredited investor/i)).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("link", { name: /continue to bank/i }).click();

  // ---------- bank link ----------
  await expect(page).toHaveURL(/\/onboarding\/bank$/);
  await page.getByLabel(/bank name/i).fill("Chase");
  await page.getByLabel(/account holder name/i).fill("Eve E2E");
  await page.getByLabel(/^account number/i).fill("123456789");
  await page.getByLabel(/routing number/i).fill("110000000");
  await page.getByLabel(/currency/i).fill("USD");
  await page.getByRole("button", { name: /link bank/i }).click();
  await expect(page.getByText(/bank account linked/i)).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("link", { name: /continue to investment/i }).click();

  // ---------- investment ----------
  await expect(page).toHaveURL(/\/onboarding\/invest$/);
  await page.getByLabel(/^amount/i).fill("1500.00");
  await page.getByLabel(/notes/i).fill("E2E happy-path");
  await page.getByRole("button", { name: /place investment/i }).click();
  await expect(page.getByText(/investment placed/i)).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/escrow reference/i)).toBeVisible();

  // ---------- audit log ----------
  await page.getByRole("link", { name: /view audit log/i }).click();
  await expect(page).toHaveURL(/\/audit$/);
  for (const action of [
    "AUTH_SIGNUP",
    "PROFILE_UPDATED",
    "KYC_SUBMITTED",
    "ACCREDITATION_RESOLVED",
    "BANK_LINKED",
    "INVESTMENT_CREATED",
  ]) {
    await expect(page.getByText(action).first()).toBeVisible();
  }
});
