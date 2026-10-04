import { publicConfig } from "@/lib/config";
import type { ConfirmCallResult, ConfirmedClaim, ExtractCallResult, ExtractedClaim } from "./types";

export const EXTRACT_ENDPOINT = "/api/v1/claims/extract";
export const CONFIRM_ENDPOINT = "/api/v1/claims/confirm";

type Raw = { status: number; body: Record<string, unknown> | null } | null;

async function postJson(path: string, payload: unknown, timeoutMs: number): Promise<Raw> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${publicConfig.apiBaseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    let body: Record<string, unknown> | null = null;
    try {
      body = (await res.json()) as Record<string, unknown>;
    } catch {
      body = null;
    }
    return { status: res.status, body };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

function failureOf(raw: NonNullable<Raw>): { kind: "failure"; code: string; retryable: boolean } | { kind: "input_error"; code: string } {
  const body = raw.body ?? {};
  if (body.kind === "input_error") return { kind: "input_error", code: String(body.code ?? "invalid") };
  const err = (body.error ?? {}) as { code?: string; retryable?: boolean };
  return { kind: "failure", code: err.code ?? `http_${raw.status}`, retryable: err.retryable ?? raw.status >= 500 };
}

/** Ask the backend to extract claims. Never runs verification. */
export async function extractClaims(text: string): Promise<ExtractCallResult> {
  const raw = await postJson(EXTRACT_ENDPOINT, { text }, 90_000);
  if (!raw) return { kind: "network_error" };
  if (raw.status === 200 && raw.body?.kind === "extraction") {
    return {
      kind: "extraction",
      claims: (raw.body.claims as ExtractedClaim[]) ?? [],
      discardedUngroundedCount: Number(raw.body.discarded_ungrounded_count ?? 0),
    };
  }
  return failureOf(raw);
}

export interface ConfirmPayload {
  explicit_user_confirmation: true;
  claims: {
    claim_id: string;
    origin: "extracted" | "manual";
    original_text: string;
    extracted_claim_text: string | null;
    text: string;
    selected: boolean;
    extraction_status: string | null;
    provided_evidence: unknown;
    provided_reference: string | null;
  }[];
}

/** Send the user's explicit confirmation through the backend confirmation gate. */
export async function confirmClaims(payload: ConfirmPayload): Promise<ConfirmCallResult> {
  const raw = await postJson(CONFIRM_ENDPOINT, payload, 30_000);
  if (!raw) return { kind: "network_error" };
  if (raw.status === 200 && raw.body?.kind === "confirmed") {
    return {
      kind: "confirmed",
      result: {
        confirmedClaims: (raw.body.confirmed_claims as ConfirmedClaim[]) ?? [],
        nextStage: "claim_classification",
      },
    };
  }
  return failureOf(raw);
}
