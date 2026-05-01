import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import {
  type AccreditationCheck,
  type AccreditationSubmitValues,
  type AccreditationSummary,
  accreditationCheckSchema,
  accreditationSummarySchema,
} from "@/lib/schemas/accreditation";

export const accreditationQueryKey = ["accreditation"] as const;

export function useAccreditationSummary() {
  return useQuery<AccreditationSummary>({
    queryKey: accreditationQueryKey,
    queryFn: () => api.get("/api/v1/accreditation", accreditationSummarySchema),
    // Poll while pending — backend resolves via the ARQ worker after the
    // configured delay (5s in local).
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.status === "pending" ? 2_000 : false;
    },
  });
}

export function useSubmitAccreditation() {
  const qc = useQueryClient();
  return useMutation<AccreditationCheck, Error, AccreditationSubmitValues>({
    mutationFn: (body) => api.post("/api/v1/accreditation", accreditationCheckSchema, { body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: accreditationQueryKey }),
  });
}
