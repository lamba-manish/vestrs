import { type InfiniteData, useInfiniteQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { type AuditList, auditListSchema } from "@/lib/schemas/audit";

export const auditQueryKey = ["audit"] as const;

export function useAuditFeed() {
  return useInfiniteQuery<
    AuditList,
    Error,
    InfiniteData<AuditList, string | null>,
    typeof auditQueryKey,
    string | null
  >({
    queryKey: auditQueryKey,
    initialPageParam: null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams();
      params.set("limit", "20");
      if (pageParam) params.set("cursor", pageParam);
      return api.get(`/api/v1/audit?${params.toString()}`, auditListSchema);
    },
    getNextPageParam: (last) => last.next_cursor,
    // The audit feed mutates on every onboarding step (signup, KYC,
    // accreditation, bank, invest). With the dashboard now pre-fetching
    // the feed for the Recent activity card, the global 30s staleTime
    // would otherwise serve a stale snapshot when the user navigates
    // from invest → /audit a few seconds later. Refetch on every mount
    // so the page is always current.
    staleTime: 0,
    refetchOnMount: "always",
  });
}
