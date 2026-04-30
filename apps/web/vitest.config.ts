import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    css: false,
    // Playwright owns tests/e2e — exclude them from the unit runner so
    // `pnpm test` doesn't try to import @playwright/test in jsdom.
    exclude: ["**/node_modules/**", "**/dist/**", "tests/e2e/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      reportsDirectory: "./coverage",
      // Mirror sonar.coverage.exclusions in sonar-project.properties:
      // route wiring + UI shell + vendored shadcn primitives + config
      // files don't have unit tests by design (covered by Playwright
      // e2e or are pure config).
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        // Route + view glue — exercised by Playwright e2e, not unit tests.
        "src/main.tsx",
        "src/App.tsx",
        "src/routes/**",
        "src/components/providers.tsx",
        "src/components/route-transitions.tsx",
        "src/components/theme-provider.tsx",
        "src/components/theme-toggle.tsx",
        "src/components/top-nav.tsx",
        "src/components/auth/**",
        "src/components/onboarding/**",
        // Vendored shadcn primitives — upstream-tested.
        "src/components/ui/**",
        // TanStack Query hook wrappers — thin glue; meaningful behaviour
        // is the network call shape, which Playwright covers end-to-end.
        "src/lib/accreditation.ts",
        "src/lib/audit.ts",
        "src/lib/auth.ts",
        "src/lib/bank.ts",
        "src/lib/investments.ts",
        "src/lib/kyc.ts",
        "src/lib/profile.ts",
        // Schema files that are pure type re-exports / API response shapes.
        "src/lib/schemas/accreditation.ts",
        "src/lib/schemas/audit.ts",
        "src/lib/schemas/investments.ts",
        "src/lib/schemas/kyc.ts",
        "src/lib/env.ts",
        "src/vite-env.d.ts",
      ],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
