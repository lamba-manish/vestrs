import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import {
  type Investment,
  type InvestmentFormValues,
  type InvestmentList,
  investmentListSchema,
  investmentSchema,
} from "@/lib/schemas/investments";

export const investmentsQueryKey = ["investments"] as const;

export function useInvestments() {
  return useQuery<InvestmentList>({
    queryKey: investmentsQueryKey,
    queryFn: () => api.get("/api/v1/investments", investmentListSchema),
  });
}

/** Generates a fresh idempotency key per submission. UUIDv4 from the
 * platform crypto API — sufficient entropy, RFC-4122 shape. */
export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  // Fallback for ancient runtimes (jsdom in tests sometimes).
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function useCreateInvestment() {
  const qc = useQueryClient();
  return useMutation<Investment, Error, InvestmentFormValues>({
    mutationFn: (form) =>
      api.post("/api/v1/investments", investmentSchema, {
        body: form,
        headers: { "Idempotency-Key": newIdempotencyKey() },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: investmentsQueryKey });
      qc.invalidateQueries({ queryKey: ["bank"] });
    },
  });
}
