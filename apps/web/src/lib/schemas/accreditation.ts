import { z } from "zod";

export const accreditationStatusSchema = z.enum(["not_started", "pending", "success", "failed"]);
export type AccreditationStatus = z.infer<typeof accreditationStatusSchema>;

export const accreditationCheckSchema = z.object({
  id: z.string().uuid(),
  attempt_number: z.number().int(),
  status: accreditationStatusSchema,
  path: z.string().nullable().optional(),
  provider_name: z.string(),
  provider_reference: z.string().nullable(),
  failure_reason: z.string().nullable(),
  requested_at: z.string(),
  resolved_at: z.string().nullable(),
});
export type AccreditationCheck = z.infer<typeof accreditationCheckSchema>;

export const accreditationSummarySchema = z.object({
  status: accreditationStatusSchema,
  latest: accreditationCheckSchema.nullable(),
});
export type AccreditationSummary = z.infer<typeof accreditationSummarySchema>;

// ---------- slice 29: SEC accreditation paths ----------
//
// Mirrors apps/api/app/schemas/accreditation.py. Validation thresholds
// stay in lock-step with the backend so the form catches the same
// failures pydantic would, but the backend is still the source of truth.
//
// Reference:
// https://www.sec.gov/resources-small-businesses/capital-raising-building-blocks/accredited-investors

export const SEC_INCOME_INDIVIDUAL_USD = 200_000;
export const SEC_INCOME_JOINT_USD = 300_000;
export const SEC_NET_WORTH_USD = 1_000_000;
export const SEC_REQUIRED_INCOME_YEARS = 2;

const usdAmountSchema = z
  .union([z.string(), z.number()])
  .transform((v) => (typeof v === "number" ? v.toFixed(2) : v))
  .refine((v) => /^\d+(\.\d{0,2})?$/.test(v), "Enter a valid USD amount, e.g. 300000.00");

export const incomeAccreditationSchema = z
  .object({
    path: z.literal("income"),
    annual_income_usd: usdAmountSchema,
    joint_with_spouse: z.boolean(),
    years_at_or_above: z.number().int().min(1).max(10),
    expects_same_current_year: z.boolean(),
  })
  .superRefine((v, ctx) => {
    const threshold = v.joint_with_spouse ? SEC_INCOME_JOINT_USD : SEC_INCOME_INDIVIDUAL_USD;
    if (Number(v.annual_income_usd) < threshold) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["annual_income_usd"],
        message: v.joint_with_spouse
          ? "Joint income must be at least $300,000."
          : "Individual income must be at least $200,000.",
      });
    }
    if (v.years_at_or_above < SEC_REQUIRED_INCOME_YEARS) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["years_at_or_above"],
        message: "SEC requires income at this level for the past 2 years.",
      });
    }
    if (!v.expects_same_current_year) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["expects_same_current_year"],
        message: "A reasonable expectation of the same income this year is required.",
      });
    }
  });
export type IncomeAccreditationValues = z.input<typeof incomeAccreditationSchema>;

export const netWorthAccreditationSchema = z
  .object({
    path: z.literal("net_worth"),
    net_worth_usd: usdAmountSchema,
    joint_with_spouse: z.boolean(),
    excludes_primary_residence: z.boolean(),
  })
  .superRefine((v, ctx) => {
    if (!v.excludes_primary_residence) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["excludes_primary_residence"],
        message: "Net worth must exclude the value of your primary residence.",
      });
    }
    if (Number(v.net_worth_usd) < SEC_NET_WORTH_USD) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["net_worth_usd"],
        message: "Net worth must be at least $1,000,000.",
      });
    }
  });
export type NetWorthAccreditationValues = z.input<typeof netWorthAccreditationSchema>;

export const professionalCertAccreditationSchema = z.object({
  path: z.literal("professional_certification"),
  license_kind: z.enum(["series_7", "series_65", "series_82"]),
  license_number: z.string().min(3, "Enter your license number.").max(32),
});
export type ProfessionalCertAccreditationValues = z.input<
  typeof professionalCertAccreditationSchema
>;

export const accreditationSubmitSchema = z.discriminatedUnion("path", [
  incomeAccreditationSchema as unknown as z.ZodDiscriminatedUnionOption<"path">,
  netWorthAccreditationSchema as unknown as z.ZodDiscriminatedUnionOption<"path">,
  professionalCertAccreditationSchema as unknown as z.ZodDiscriminatedUnionOption<"path">,
]);
export type AccreditationSubmitValues = z.input<typeof accreditationSubmitSchema>;
