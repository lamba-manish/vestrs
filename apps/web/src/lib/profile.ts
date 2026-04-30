import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { type Profile, type ProfileFormValues, profileResponseSchema } from "@/lib/schemas/profile";

export const profileQueryKey = ["users", "me"] as const;

export function useProfile() {
  return useQuery<Profile>({
    queryKey: profileQueryKey,
    queryFn: () => api.get("/api/v1/users/me", profileResponseSchema),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileFormValues) =>
      api.put("/api/v1/users/me", profileResponseSchema, { body }),
    onSuccess: (data) => {
      qc.setQueryData(profileQueryKey, data);
    },
  });
}
