/** Pure report helpers (spec §12): grouping and counts. No network, no verdict logic. */
import type { ResultGroup } from "@/lib/domain";
import type { ClaimOutcome, ClaimRun, VerificationOutcome } from "./types";

/** Report sections: the four spec groups + outcomes that are NOT verification statuses. */
export type ReportSection = ResultGroup | "not_verifiable_now" | "technical";

export const SECTION_ORDER: ReportSection[] = [
  "do_not_use_as_written",
  "needs_revision",
  "needs_evidence_review",
  "verified",
  "not_verifiable_now",
  "technical",
];

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

export function countBySection(runs: ClaimRun[]): Record<ReportSection, number> {
  const counts = Object.fromEntries(SECTION_ORDER.map((s) => [s, 0])) as Record<ReportSection, number>;
  for (const r of runs) {
    const s = runSection(r);
    if (s) counts[s] += 1;
  }
  return counts;
}

export const ALTERNATIVE_ELIGIBLE = new Set(["partially_supported", "contradicted"]);

export function canOfferAlternative(outcome: ClaimOutcome): boolean {
  return (
    outcome.kind === "verification" &&
    ALTERNATIVE_ELIGIBLE.has(outcome.status) &&
    outcome.analysis.assessments.some((a) => a.evidence_span && a.relationship !== "insufficient")
  );
}
