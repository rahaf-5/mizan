/**
 * Frontend -> backend connectivity check using the real frontend API client.
 * Requires a running backend. Run with:  npm run test:integration
 * (uses NEXT_PUBLIC_API_BASE_URL, default http://localhost:8000).
 */
import { describe, expect, it } from "vitest";
import { getHealth } from "@/lib/api";
import { publicConfig } from "@/lib/config";

const FRONTEND_ORIGIN = process.env.MIZAN_FRONTEND_ORIGIN ?? "http://localhost:3000";

describe("frontend can reach backend", () => {
  it("loads the health report through the frontend API client", async () => {
    const report = await getHealth();
    expect(report.config_loaded).toBe(true);
    expect(["ok", "degraded"]).toContain(report.status);
  });

  it("backend allows the frontend origin (CORS)", async () => {
    const res = await fetch(`${publicConfig.apiBaseUrl}/api/v1/health/live`, {
      headers: { Origin: FRONTEND_ORIGIN },
    });
    expect(res.ok).toBe(true);
    expect(res.headers.get("access-control-allow-origin")).toBe(FRONTEND_ORIGIN);
  });
});
