"use client";

import { useEffect, useRef } from "react";
import type { ConfirmedClaim } from "@/lib/claims/types";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { verifyClaims } from "@/lib/verify/client";
import type { AlternativeWording, ClaimRun } from "@/lib/verify/types";

/**
 * Verifies CONFIRMED claims one at a time against the real backend (POST /api/v1/verify),
 * so progress ("2 of 3") reflects real completion. Runs live in the in-memory session.
 * A failed request is a technical failure — never a verdict.
 */
export function useVerificationRuns(key: string, claims: ConfirmedClaim[]) {
  const { state, dispatch } = useInputSession();
  const runs = state.verification?.key === key ? state.verification.runs : null;
  const inFlight = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!runs && claims.length > 0) {
      dispatch({ type: "verification/set", key, runs: claims.map((c) => ({ state: "waiting", claim: c })) });
    }
  }, [key, runs, claims, dispatch]);

  useEffect(() => {
    if (!runs || runs.some((r) => r.state === "running")) return;
    const index = runs.findIndex((r) => r.state === "waiting");
    if (index < 0) return;
    const claim = runs[index].claim;
    const tag = `${key}:${index}:${claim.claim_id}`;
    if (inFlight.current.has(tag)) return;
    inFlight.current.add(tag);
    dispatch({ type: "verification/updateAt", key, index, run: { state: "running", claim } });
    void verifyClaims([claim]).then((res) => {
      inFlight.current.delete(tag);
      let run: ClaimRun;
      if (res.kind === "result" && res.result.outcomes.length === 1) {
        run = { state: "done", claim, runId: res.result.run_id, outcome: res.result.outcomes[0] };
      } else {
        const code = res.kind === "network_error" ? "network_error" : res.kind === "result" ? "invalid_response" : res.code;
        run = { state: "failed", claim, code };
      }
      dispatch({ type: "verification/updateAt", key, index, run });
    });
  }, [key, runs, dispatch]);

  const retry = (index: number) => {
    if (!runs?.[index]) return;
    dispatch({ type: "verification/updateAt", key, index, run: { state: "waiting", claim: runs[index].claim } });
  };

  /** Adopt a VERIFIED alternative wording: the claim text and its result are replaced. */
  const adopt = (index: number, alt: AlternativeWording) => {
    if (!runs?.[index] || !alt.verified || !alt.outcome || !alt.proposed_text) return;
    const old = runs[index].claim;
    dispatch({
      type: "verification/updateAt",
      key,
      index,
      run: {
        state: "done",
        claim: { ...old, confirmed_claim_text: alt.proposed_text, user_confirmation_status: "edited" },
        runId: alt.run_id,
        outcome: alt.outcome,
        adopted: true,
      },
    });
  };

  return { runs: runs ?? [], retry, adopt };
}
