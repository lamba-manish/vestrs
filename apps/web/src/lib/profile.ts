import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { type Profile, profileResponseSchema } from "@/lib/schemas/profile";

export const profileQueryKey = ["users", "me"] as const;

/** Wire-shape for PUT /users/me. The form-side values (which split
 *  phone into country + national number) are composed into this
 *  shape inside the route component before submission. */
export interface ProfileUpdateBody {
  full_name: string;
  nationality: string;
  domicile: string;
  phone: string;
}

export function useProfile() {
  return useQuery<Profile>({
    queryKey: profileQueryKey,
    queryFn: () => api.get("/api/v1/users/me", profileResponseSchema),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileUpdateBody) =>
      api.put("/api/v1/users/me", profileResponseSchema, { body }),
    onSuccess: (data) => {
      qc.setQueryData(profileQueryKey, data);
    },
  });
}
