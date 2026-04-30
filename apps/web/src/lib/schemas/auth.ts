/**
 * Form schemas for the auth flows. Mirrors the backend Pydantic schemas in
 * apps/api/app/schemas/auth.py (kept manually in sync — small surface).
 */

import { z } from "zod";

export const signupSchema = z
  .object({
    email: z.string().email("Enter a valid email address."),
    password: z.string().min(12, "Use at least 12 characters.").max(128, "Maximum 128 characters."),
    confirm_password: z.string(),
  })
  .refine((v) => v.password === v.confirm_password, {
    message: "Passwords do not match.",
    path: ["confirm_password"],
  });

export const loginSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Required."),
});

export type SignupValues = z.infer<typeof signupSchema>;
export type LoginValues = z.infer<typeof loginSchema>;

export const userPublicSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  full_name: z.string().nullable().optional(),
});

export type UserPublic = z.infer<typeof userPublicSchema>;
