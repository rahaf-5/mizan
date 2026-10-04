import { publicConfig } from "./config";

export interface ComponentStatus {
  status: string;
  detail: string | null;
}

/** Shape of GET /api/v1/health (backend/app/api/v1/health.py). */
export interface HealthReport {
  status: "ok" | "degraded";
  app: string;
  version: string;
  environment: string;
  config_loaded: boolean;
  database: ComponentStatus;
  llm_provider: ComponentStatus;
  trusted_sources: Record<string, ComponentStatus>;
}

/** Technical API failure — never to be presented as a verification result. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly httpStatus?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiGet<T>(path: string, timeoutMs = 5000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${publicConfig.apiBaseUrl}${path}`, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status);
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(err instanceof Error ? err.message : "network error");
  } finally {
    clearTimeout(timer);
  }
}

export function getHealth(): Promise<HealthReport> {
  return apiGet<HealthReport>("/api/v1/health");
}
