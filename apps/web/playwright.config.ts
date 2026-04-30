import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config — happy-path e2e against a running stack.
 *
 * In CI: docker compose up the full stack first, then run `pnpm e2e`.
 * The compose web service exposes :3000, the API :8000.
 *
 * Locally: same — run `make up` first, then `pnpm e2e` from apps/web,
 * or `make e2e` from the repo root.
 *
 * The runner does NOT spawn its own webServer because the API + DB +
 * Redis + worker stack must already be present; spawning them inline
 * would only cover the FE.
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const apiURL = process.env.E2E_API_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false, // backend writes to a shared DB; serialise specs
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["html", { open: "never" }], ["github"]] : [["list"]],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL,
    extraHTTPHeaders: {
      // helps the API correlate browser-driven test traffic in logs
      "x-e2e-source": "playwright",
    },
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  metadata: { apiURL },
});
