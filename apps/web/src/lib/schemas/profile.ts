import { z } from "zod";

export const profileFormSchema = z.object({
  full_name: z.string().trim().min(1, "Required.").max(120, "Maximum 120 characters."),
  nationality: z
    .string()
    .trim()
    .length(2, "Two-letter ISO code.")
    .transform((v) => v.toUpperCase()),
  domicile: z
    .string()
    .trim()
    .length(2, "Two-letter ISO code.")
    .transform((v) => v.toUpperCase()),
  phone: z
    .string()
    .trim()
    .min(8, "Too short.")
    .max(20, "Too long.")
    .regex(/^\+\d[\d\s-]+$/, "Use international format, e.g. +14155551234."),
});

export type ProfileFormValues = z.infer<typeof profileFormSchema>;

export const profileResponseSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  full_name: z.string().nullable(),
  nationality: z.string().nullable(),
  domicile: z.string().nullable(),
  phone: z.string().nullable(),
});
export type Profile = z.infer<typeof profileResponseSchema>;
