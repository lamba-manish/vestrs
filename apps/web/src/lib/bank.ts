import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import {
  type BankAccount,
  type BankLinkFormValues,
  type BankSummary,
  bankAccountSchema,
  bankSummarySchema,
} from "@/lib/schemas/bank";

export const bankQueryKey = ["bank"] as const;

export function useBankSummary() {
  return useQuery<BankSummary>({
    queryKey: bankQueryKey,
    queryFn: () => api.get("/api/v1/bank", bankSummarySchema),
  });
}

export function useLinkBank() {
  const qc = useQueryClient();
  return useMutation<BankAccount, Error, BankLinkFormValues>({
    mutationFn: (body) => api.post("/api/v1/bank/link", bankAccountSchema, { body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: bankQueryKey }),
  });
}

export function useUnlinkBank() {
  const qc = useQueryClient();
  return useMutation<BankAccount>({
    mutationFn: () => api.delete("/api/v1/bank", bankAccountSchema),
    onSuccess: () => qc.invalidateQueries({ queryKey: bankQueryKey }),
  });
}
