import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 3000,
    strictPort: true,
  },
  preview: {
    host: "0.0.0.0",
    port: 3000,
    strictPort: true,
  },
  build: {
    target: "es2022",
    sourcemap: false,
    // Manual vendor chunking — keeps the app entry chunk small and
    // lets the browser cache long-lived deps across deploys (the
    // `react-vendor` chunk only changes when react itself updates).
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.match(/node_modules\/(react|react-dom|react-router-dom|react-router)\//)) {
            return "react-vendor";
          }
          if (id.includes("@tanstack/react-query")) return "tanstack-vendor";
          if (id.includes("framer-motion")) return "framer-vendor";
          if (id.includes("@radix-ui")) return "radix-vendor";
          if (id.includes("@fontsource-variable")) return "font-vendor";
          if (id.match(/node_modules\/(zod|@hookform\/resolvers|react-hook-form)\//)) {
            return "form-vendor";
          }
          return undefined;
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
});
