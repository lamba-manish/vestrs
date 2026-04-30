import { z } from "zod";

export const investmentFormSchema = z.object({
  amount: z
    .string()
    .trim()
    .regex(/^\d+(\.\d{1,4})?$/, "Use a number with up to 4 decimal places.")
    .refine((v) => Number(v) > 0, "Must be positive."),
  notes: z.string().trim().max(500).optional(),
});
export type InvestmentFormValues = z.infer<typeof investmentFormSchema>;

export const investmentSchema = z.object({
  id: z.string().uuid(),
  amount: z.string(),
  currency: z.string(),
  status: z.string(),
  escrow_reference: z.string(),
  notes: z.string().nullable(),
  bank_account_id: z.string().uuid(),
  settled_at: z.string().nullable(),
  created_at: z.string(),
});
export type Investment = z.infer<typeof investmentSchema>;

export const investmentListSchema = z.object({
  items: z.array(investmentSchema),
  total: z.number().int(),
});
export type InvestmentList = z.infer<typeof investmentListSchema>;
