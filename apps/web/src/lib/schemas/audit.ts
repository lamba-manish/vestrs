import { z } from "zod";

export const auditEntrySchema = z.object({
  id: z.string().uuid(),
  timestamp: z.string(),
  user_id: z.string().uuid().nullable().optional(),
  action: z.string(),
  resource_type: z.string().nullable().optional(),
  resource_id: z.string().uuid().nullable().optional(),
  status: z.string(),
  request_id: z.string().nullable().optional(),
  metadata: z.record(z.string(), z.unknown()).default({}),
});
export type AuditEntry = z.infer<typeof auditEntrySchema>;

export const auditListSchema = z.object({
  items: z.array(auditEntrySchema),
  next_cursor: z.string().nullable(),
});
export type AuditList = z.infer<typeof auditListSchema>;
