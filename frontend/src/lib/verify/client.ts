import { failureOf, postJson } from "@/lib/claims/client";
import type { ConfirmedClaim } from "@/lib/claims/types";
import type { AlternativeCallResult, AlternativeWording, FinalUserResult, VerifyCallResult } from "./types";

export const VERIFY_ENDPOINT = "/api/v1/verify";
export const ALTERNATIVE_ENDPOINT = "/api/v1/alternative-wording";

/** Verify user-CONFIRMED claims only (they come from the backend confirmation gate). */
export async function verifyClaims(claims: ConfirmedClaim[]): Promise<VerifyCallResult> {
  const raw = await postJson(VERIFY_ENDPOINT, { claims }, 180_000);
  if (!raw) return { kind: "network_error" };
  if (raw.status === 200 && Array.isArray(raw.body?.outcomes)) {
    return { kind: "result", result: raw.body as unknown as FinalUserResult };
  }
  return failureOf(raw);
}

/** Ask for ONE alternative wording; the backend re-verifies it through the full pipeline. */
export async function requestAlternative(runId: string, claimId: string): Promise<AlternativeCallResult> {
  const raw = await postJson(ALTERNATIVE_ENDPOINT, { run_id: runId, claim_id: claimId }, 240_000);
  if (!raw) return { kind: "network_error" };
  if (raw.status === 200 && raw.body?.kind === "alternative_wording") {
    return { kind: "alternative", result: raw.body as unknown as AlternativeWording };
  }
  return failureOf(raw);
}
