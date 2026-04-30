import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import {
  type KycCheck,
  type KycSummary,
  kycCheckSchema,
  kycSummarySchema,
} from "@/lib/schemas/kyc";

export const kycQueryKey = ["kyc"] as const;

export function useKycSummary() {
  return useQuery<KycSummary>({
    queryKey: kycQueryKey,
    queryFn: () => api.get("/api/v1/kyc", kycSummarySchema),
  });
}

export function useSubmitKyc() {
  const qc = useQueryClient();
  return useMutation<KycCheck>({
    mutationFn: () => api.post("/api/v1/kyc", kycCheckSchema),
    onSuccess: () => qc.invalidateQueries({ queryKey: kycQueryKey }),
  });
}

export function useRetryKyc() {
  const qc = useQueryClient();
  return useMutation<KycCheck>({
    mutationFn: () => api.post("/api/v1/kyc/retry", kycCheckSchema),
    onSuccess: () => qc.invalidateQueries({ queryKey: kycQueryKey }),
  });
}
