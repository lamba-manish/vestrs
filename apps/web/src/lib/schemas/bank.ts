import { z } from "zod";

export const bankLinkFormSchema = z.object({
  bank_name: z.string().trim().min(1).max(80),
  account_holder_name: z.string().trim().min(1).max(120),
  account_type: z.enum(["checking", "savings", "money_market"]),
  account_number: z.string().trim().regex(/^\d+$/, "Digits only.").min(4).max(34),
  routing_number: z.string().trim().regex(/^\d+$/, "Digits only.").min(8).max(12),
  currency: z
    .string()
    .trim()
    .length(3, "ISO-4217 (e.g. USD).")
    .transform((v) => v.toUpperCase()),
});
export type BankLinkFormValues = z.infer<typeof bankLinkFormSchema>;

export const bankAccountSchema = z.object({
  id: z.string().uuid(),
  bank_name: z.string(),
  account_holder_name: z.string(),
  account_type: z.string(),
  last_four: z.string(),
  currency: z.string(),
  mock_balance: z.string(),
  status: z.string(),
  linked_at: z.string(),
  unlinked_at: z.string().nullable(),
});
export type BankAccount = z.infer<typeof bankAccountSchema>;

export const bankSummarySchema = z.object({
  linked: z.boolean(),
  account: bankAccountSchema.nullable(),
});
export type BankSummary = z.infer<typeof bankSummarySchema>;
