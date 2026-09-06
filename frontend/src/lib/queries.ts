import { useMutation } from "@tanstack/react-query";
import { api } from "./api";
import { useAuth } from "./auth";
import type { History, Location, Sex, User } from "@/types/user";

interface LoginPayload {
  email: string;
  password: string;
}

interface RegisterPayload {
  email: string;
  password: string;
  username?: string;
  full_name?: string;
  date_of_birth?: string;
  sex?: Sex;
  location?: Location;
  history?: History;
}

export function useLogin() {
  const refresh = useAuth((s) => s.refresh);
  return useMutation({
    mutationFn: async (payload: LoginPayload) => {
      // fastapi-users login expects form-encoded "username"/"password"
      const body = new URLSearchParams();
      body.set("username", payload.email);
      body.set("password", payload.password);
      await api.post("/auth/login", body, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      await refresh();
    },
  });
}

export function useUpdateMe() {
  const refresh = useAuth((s) => s.refresh);
  return useMutation({
    mutationFn: async (payload: Partial<RegisterPayload> & { history?: History; location?: Location }) => {
      await api.patch<User>("/api/me", payload);
      await refresh();
    },
  });
}

export function useRegister() {
  const refresh = useAuth((s) => s.refresh);
  return useMutation({
    mutationFn: async (payload: RegisterPayload) => {
      await api.post<User>("/auth/register", payload);
      // fastapi-users register doesn't auto-login; do a login round-trip next.
      const body = new URLSearchParams();
      body.set("username", payload.email);
      body.set("password", payload.password);
      await api.post("/auth/login", body, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      await refresh();
    },
  });
}
