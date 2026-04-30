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
        "src/main.tsx",
        "src/App.tsx",
        "src/components/providers.tsx",
        "src/components/route-transitions.tsx",
        "src/components/theme-provider.tsx",
        "src/components/theme-toggle.tsx",
        "src/components/top-nav.tsx",
        "src/components/auth/auth-guard.tsx",
        "src/components/auth/side-info.tsx",
        "src/components/onboarding/**",
        "src/components/ui/**",
        "src/lib/env.ts",
        "src/routes/**",
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
