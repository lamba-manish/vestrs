import { expect, type Page, test } from "@playwright/test";

/**
 * Open a Combobox by its label, search for a substring, and click
 * the first matching option. Used by the profile + bank forms where
 * country / currency / account-type pickers are searchable dropdowns
 * (slice 20).
 */
async function selectCombobox(page: Page, label: RegExp | string, search: string) {
  await page.getByLabel(label).first().click();
  // The popover renders a Command input; type to filter.
  await page.getByRole("combobox").first(); // ensure the trigger has rendered
  await page.locator("[cmdk-input]").fill(search);
  await page.getByRole("option").filter({ hasText: search }).first().click();
}

/**
 * Canonical happy-path: signup → profile → KYC → accreditation
 * (polling) → bank link → invest → audit log shows the journey.
 *
 * Each run uses a fresh email so the DB state is independent and the
 * spec is replayable without cleanup.
 */

// Password must satisfy the strong-password schema: 12+ chars,
// lowercase, uppercase, digit, symbol.
const PASSWORD = "Correct-Horse-Battery-9!";

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
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel(/confirm password/i).fill(PASSWORD);
  await page.getByRole("button", { name: /open account|sign up|create/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: /welcome/i })).toBeVisible();

  // ---------- profile ----------
  await page.getByRole("link", { name: /start/i }).first().click();
  await expect(page).toHaveURL(/\/onboarding\/profile$/);
  await page.getByLabel(/full name/i).fill("Eve E2E");
  await selectCombobox(page, /nationality/i, "United States");
  await selectCombobox(page, /country of residence/i, "United States");
  // Phone is split: dial-code combobox + national-number input.
  await selectCombobox(page, /phone/i, "United States");
  await page.getByPlaceholder(/9876543210/).fill("4155551234");
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
  // Currency + account_type are now Comboboxes (slice 20). Both default
  // to USD / Checking already, but exercise the picker on currency to
  // catch regressions.
  await selectCombobox(page, /currency/i, "USD");
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
  // Sonner toast and the CardTitle both render the words "Investment
  // placed"; the toast has a trailing period, the title doesn't.
  await expect(page.getByText("Investment placed", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/escrow reference/i)).toBeVisible();

  // ---------- audit log ----------
  await page.getByRole("link", { name: /view audit log/i }).click();
  await expect(page).toHaveURL(/\/audit$/);
  // Slice 22 humanized these codes — assert the user-facing labels
  // emitted by lib/audit-format.ts.
  for (const label of [
    "Account created",
    "Profile updated",
    "KYC submitted",
    "Accreditation resolved",
    "Bank linked",
    "Investment placed",
  ]) {
    await expect(page.getByText(label).first()).toBeVisible();
  }
});
