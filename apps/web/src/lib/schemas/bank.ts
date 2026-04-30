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
    .length(3, "Pick a currency from the list.")
    .transform((v) => v.toUpperCase()),
});
export type BankLinkFormValues = z.infer<typeof bankLinkFormSchema>;

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  checking: "Checking",
  savings: "Savings",
  money_market: "Money market",
};

/** Human-readable form of `account_type` from the backend (e.g.
 *  "money_market" → "Money market"). Falls back to title-casing for
 *  unknown future values. */
export function formatAccountType(raw: string): string {
  if (raw in ACCOUNT_TYPE_LABELS) return ACCOUNT_TYPE_LABELS[raw];
  return raw
    .split("_")
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w.toLowerCase()))
    .join(" ");
}

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
