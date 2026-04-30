/**
 * Public env, validated once at module load.
 *
 * Vite inlines `import.meta.env.VITE_*` at build time. Anything outside the
 * VITE_ prefix is unavailable to client code, by design.
 */

import { z } from "zod";

const schema = z.object({
  VITE_API_URL: z.string().url().default("http://localhost:8000"),
  VITE_APP_ENV: z.enum(["local", "staging", "production"]).default("local"),
});

const raw = import.meta.env as Record<string, string | undefined>;

const parsed = schema.parse({
  VITE_API_URL: raw.VITE_API_URL,
  VITE_APP_ENV: raw.VITE_APP_ENV,
});

export const env = {
  API_URL: parsed.VITE_API_URL,
  APP_ENV: parsed.VITE_APP_ENV,
} as const;
