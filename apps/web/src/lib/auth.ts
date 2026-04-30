/**
 * Auth state — derived from /api/v1/auth/me.
 *
 * Cookies are httpOnly so JS cannot inspect them directly. We treat /me as
 * the source of truth: on mount, call it. 200 → authenticated, 401 →
 * anonymous. Login / signup / logout invalidate this query so the rest of
 * the app re-renders.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { ApiError, api } from "@/lib/api";
import {
  type LoginValues,
  type SignupValues,
  type UserPublic,
  userPublicSchema,
} from "@/lib/schemas/auth";

const meSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
});

const authSuccessSchema = z.object({ user: userPublicSchema });
const logoutSchema = z.object({ logged_out: z.literal(true) });

export const meQueryKey = ["auth", "me"] as const;

export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: async () => {
      try {
        return await api.get("/api/v1/auth/me", meSchema);
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          return null;
        }
        throw e;
      }
    },
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: (values: Pick<LoginValues, "email" | "password">) =>
      api.post("/api/v1/auth/login", authSuccessSchema, { body: values }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: meQueryKey });
      navigate("/dashboard");
    },
  });
}

export function useSignup() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: (values: Pick<SignupValues, "email" | "password">) =>
      api.post("/api/v1/auth/signup", authSuccessSchema, { body: values }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: meQueryKey });
      navigate("/dashboard");
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: () => api.post("/api/v1/auth/logout", logoutSchema),
    onSuccess: () => {
      qc.setQueryData(meQueryKey, null);
      navigate("/");
    },
  });
}

export type { UserPublic };
