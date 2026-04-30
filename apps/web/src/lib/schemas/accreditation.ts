import { z } from "zod";

export const accreditationStatusSchema = z.enum(["not_started", "pending", "success", "failed"]);
export type AccreditationStatus = z.infer<typeof accreditationStatusSchema>;

export const accreditationCheckSchema = z.object({
  id: z.string().uuid(),
  attempt_number: z.number().int(),
  status: accreditationStatusSchema,
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
