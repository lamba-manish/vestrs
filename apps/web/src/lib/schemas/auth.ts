/**
 * Form schemas for the auth flows. Mirrors the backend Pydantic schemas in
 * apps/api/app/schemas/auth.py (kept manually in sync — small surface).
 */

import { z } from "zod";

export const PASSWORD_RULES = [
  {
    id: "len",
    label: "12+ characters",
    nudge: "Use at least 12 characters.",
    test: (p: string) => p.length >= 12,
  },
  {
    id: "lower",
    label: "Lowercase letter",
    nudge: "Add a lowercase letter.",
    test: (p: string) => /[a-z]/.test(p),
  },
  {
    id: "upper",
    label: "Uppercase letter",
    nudge: "Add an uppercase letter.",
    test: (p: string) => /[A-Z]/.test(p),
  },
  {
    id: "digit",
    label: "Digit",
    nudge: "Add a digit.",
    test: (p: string) => /\d/.test(p),
  },
  {
    id: "symbol",
    label: "Symbol",
    nudge: "Add a symbol (e.g. !@#).",
    test: (p: string) => /[^A-Za-z0-9]/.test(p),
  },
] as const;

const strongPassword = z
  .string()
  .max(128, "Maximum 128 characters.")
  .superRefine((value, ctx) => {
    for (const rule of PASSWORD_RULES) {
      if (!rule.test(value)) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: rule.nudge });
        return;
      }
    }
  });

export const signupSchema = z
  .object({
    email: z.string().email("Enter a valid email address."),
    password: strongPassword,
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
