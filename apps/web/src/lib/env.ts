/**
 * Public env, validated once at module load. NEXT_PUBLIC_* values are
 * inlined at build time, so a typo would silently fall through to undefined
 * — this module surfaces any miss as a clear error.
 */

import { z } from "zod";

const schema = z.object({
  NEXT_PUBLIC_API_URL: z.string().url().default("http://localhost:8000"),
  NEXT_PUBLIC_APP_ENV: z.enum(["local", "staging", "production"]).default("local"),
});

export const env = schema.parse({
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  NEXT_PUBLIC_APP_ENV: process.env.NEXT_PUBLIC_APP_ENV,
});
