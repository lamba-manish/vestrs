/**
 * Mirrors the backend response envelope from CLAUDE.md sec.7.
 */

import { z } from "zod";

export const errorPayloadSchema = z.object({
  code: z.string(),
  message: z.string(),
});

export const successEnvelopeSchema = <T extends z.ZodTypeAny>(data: T) =>
  z.object({
    success: z.literal(true),
    data,
    request_id: z.string().nullable().optional(),
  });

export const failureEnvelopeSchema = z.object({
  success: z.literal(false),
  error: errorPayloadSchema,
  details: z.record(z.string(), z.array(z.string())).optional(),
  request_id: z.string().nullable().optional(),
});

export type FailureEnvelope = z.infer<typeof failureEnvelopeSchema>;
export type ErrorPayload = z.infer<typeof errorPayloadSchema>;
