import { z } from "zod";

import { COUNTRIES, findCountry } from "@/lib/countries";

export const profileFormSchema = z.object({
  full_name: z
    .string()
    .trim()
    .min(2, "Use at least 2 characters.")
    .max(120, "Maximum 120 characters."),
  nationality: z
    .string()
    .trim()
    .length(2, "Pick a country from the list.")
    .transform((v) => v.toUpperCase())
    .refine((v) => findCountry(v) !== undefined, {
      message: "Pick a country from the list.",
    }),
  domicile: z
    .string()
    .trim()
    .length(2, "Pick a country from the list.")
    .transform((v) => v.toUpperCase())
    .refine((v) => findCountry(v) !== undefined, {
      message: "Pick a country from the list.",
    }),
  // Two halves: the country dial code (digits only, no leading +)
  // and the national number (digits only). The form combines them
  // into the single E.164 string the API expects on submit.
  phone_country: z
    .string()
    .trim()
    .min(2, "Pick a country code.")
    .refine((v) => findCountry(v) !== undefined, {
      message: "Pick a country from the list.",
    }),
  phone_number: z
    .string()
    .trim()
    .superRefine((value, ctx) => {
      if (value.length === 0) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Required." });
        return;
      }
      if (!/^[\d\s-]+$/.test(value)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Digits only (spaces and dashes are fine).",
        });
        return;
      }
      const digits = value.replaceAll(/\D/g, "");
      if (digits.length < 6 || digits.length > 15) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Use 6-15 digits — no country code.",
        });
      }
    }),
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

/** Build the canonical E.164 phone string the backend expects from the
 *  form's split country / national-number fields. */
export function composePhone(values: ProfileFormValues): string {
  const country = findCountry(values.phone_country);
  if (!country) return "";
  const digits = values.phone_number.replaceAll(/\D/g, "");
  return `+${country.dial}${digits}`;
}

/** Reverse of composePhone — given an E.164 string from the API, find
 *  the country whose dial code is the longest prefix match. Falls back
 *  to "US" when no candidate fits (rare; profile is fresh in that case). */
export function splitPhone(
  phone: string | null | undefined,
  domicile: string | null | undefined,
): { phone_country: string; phone_number: string } {
  if (!phone) return { phone_country: domicile ?? "US", phone_number: "" };
  const digits = phone.replace(/^\+/, "").replaceAll(/\D/g, "");
  // Match longest dial code first to disambiguate +1 vs +1268, +44 vs +442 etc.
  const country = findLongestDialMatch(digits);
  if (!country) return { phone_country: domicile ?? "US", phone_number: digits };
  return {
    phone_country: country.code,
    phone_number: digits.slice(country.dial.length),
  };
}

function findLongestDialMatch(digits: string): { code: string; dial: string } | undefined {
  let best: { code: string; dial: string } | undefined;
  for (const c of COUNTRIES) {
    if (digits.startsWith(c.dial)) {
      if (!best || c.dial.length > best.dial.length) best = c;
    }
  }
  return best;
}
