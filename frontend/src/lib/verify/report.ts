/** Pure report helpers (spec §12): grouping and counts. No network, no verdict logic. */
import type { ResultGroup } from "@/lib/domain";
import type { ClaimOutcome, ClaimRun, VerificationOutcome } from "./types";

/** Report sections: the four spec groups + outcomes that are NOT verification statuses. */
export type ReportSection = ResultGroup | "not_verifiable_now" | "technical";

/** Fallback only if a verification outcome arrives without a group (backend always sets it). */
const STATUS_GROUP: Record<VerificationOutcome["status"], ResultGroup> = {
  supported: "verified",
  contradicted: "do_not_use_as_written",
  partially_supported: "needs_revision",
  insufficient_evidence: "needs_evidence_review",
  no_evidence_found: "needs_evidence_review",
  conflicting_evidence: "needs_evidence_review",
};

export function sectionOf(outcome: ClaimOutcome): ReportSection {
  switch (outcome.kind) {
    case "verification":
      return outcome.result_group ?? STATUS_GROUP[outcome.status];
    case "out_of_scope":
    case "required_source_unavailable":
      return "not_verifiable_now";
    case "system_error":
      return "technical";
  }
}

export function runSection(run: ClaimRun): ReportSection | null {
  if (run.state === "done") return sectionOf(run.outcome);
  if (run.state === "failed") return "technical";
  return null;
}

export const ALTERNATIVE_ELIGIBLE = new Set(["partially_supported", "contradicted"]);

export function canOfferAlternative(outcome: ClaimOutcome): boolean {
  return (
    outcome.kind === "verification" &&
    ALTERNATIVE_ELIGIBLE.has(outcome.status) &&
    outcome.analysis.assessments.some((a) => a.evidence_span && a.relationship !== "insufficient")
  );
}

/**
 * User-facing decision groups for the Full Content summary (presentation only). Each maps
 * existing report sections; statuses and their meaning are unchanged, and every card still
 * shows its exact status.
 */
export type Decision = "usable" | "needs_review" | "do_not_use" | "unverifiable";

export const DECISION_ORDER: Decision[] = ["usable", "needs_review", "do_not_use", "unverifiable"];

const SECTION_DECISION: Record<ReportSection, Decision> = {
  verified: "usable",
  needs_revision: "needs_review",
  needs_evidence_review: "needs_review",
  do_not_use_as_written: "do_not_use",
  not_verifiable_now: "unverifiable",
  technical: "unverifiable",
};

export function runDecision(run: ClaimRun): Decision | null {
  const s = runSection(run);
  return s ? SECTION_DECISION[s] : null;
}

export function countByDecision(runs: ClaimRun[]): Record<Decision, number> {
  const counts = { usable: 0, needs_review: 0, do_not_use: 0, unverifiable: 0 };
  for (const r of runs) {
    const d = runDecision(r);
    if (d) counts[d] += 1;
  }
  return counts;
}
