import axios, { AxiosError } from "axios";

export const api = axios.create({
  baseURL: "/",
  withCredentials: true, // send the httpOnly auth cookie
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (r) => r,
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response?.status === 401) {
      // Auth store handles redirects; just bubble.
    }
    return Promise.reject(error);
  },
);

export function apiErrorMessage(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data as { detail?: string | { msg: string }[] } | undefined;
    if (typeof d?.detail === "string") return d.detail;
    if (Array.isArray(d?.detail)) return d.detail.map((x) => x.msg).join("; ");
    return e.message;
  }
  return e instanceof Error ? e.message : String(e);
}
