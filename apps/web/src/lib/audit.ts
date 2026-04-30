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
  });
}
