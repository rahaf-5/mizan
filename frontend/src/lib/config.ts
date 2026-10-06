/** Public runtime configuration (no secrets — NEXT_PUBLIC_* values are visible to browsers). */
export const publicConfig = {
  apiBaseUrl: (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").trim().replace(/\/+$/, ""),
} as const;
