import { z } from "zod";

export const kycStatusSchema = z.enum(["not_started", "pending", "success", "failed"]);
export type KycStatus = z.infer<typeof kycStatusSchema>;

export const kycCheckSchema = z.object({
  id: z.string().uuid(),
  attempt_number: z.number().int(),
  status: kycStatusSchema,
  provider_name: z.string(),
  provider_reference: z.string().nullable(),
  failure_reason: z.string().nullable(),
  requested_at: z.string(),
  resolved_at: z.string().nullable(),
});
export type KycCheck = z.infer<typeof kycCheckSchema>;

export const kycSummarySchema = z.object({
  status: kycStatusSchema,
  attempts_used: z.number().int(),
  attempts_remaining: z.number().int(),
  latest: kycCheckSchema.nullable(),
});
export type KycSummary = z.infer<typeof kycSummarySchema>;
