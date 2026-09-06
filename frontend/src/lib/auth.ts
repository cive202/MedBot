import { create } from "zustand";
import type { User } from "@/types/user";
import { api } from "./api";

type Status = "idle" | "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  user: User | null;
  status: Status;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
  setUser: (u: User | null) => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  status: "idle",
  setUser: (u) => set({ user: u, status: u ? "authenticated" : "unauthenticated" }),
  refresh: async () => {
    set({ status: "loading" });
    try {
      const r = await api.get<User>("/api/me");
      set({ user: r.data, status: "authenticated" });
    } catch {
      set({ user: null, status: "unauthenticated" });
    }
  },
  logout: async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* ignore */
    }
    set({ user: null, status: "unauthenticated" });
  },
}));
