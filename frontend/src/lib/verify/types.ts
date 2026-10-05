/**
 * Verification result contracts (Tasks 5b, 7, 8). Mirrors backend
 * `app/domain/results.py`, `verification.py`, `evidence.py` and `api/v1/verify.py`.
 * Statuses / outcome kinds come from the shared contract (lib/domain.ts).
 */
import type { ResultGroup, TrustedSourceId, VerificationStatus } from "@/lib/domain";
import type { ConfirmedClaim } from "@/lib/claims/types";

export type ComponentOutcome =
  | "supported"
  | "partially_supported"
  | "contradicted"
  | "conflicting"
  | "insufficient"
  | "not_established";

export interface AyahRef {
  surah_number: number;
  ayah_number: number;
  quranpedia_ayah_id: number;
}

export interface ClaimComponent {
  component_id: string;
  text: string;
  kind: "quran_quote" | "quran_location" | "quran_reference_assertion" | "statement";
  role: "substantive" | "anchor";
  claim_type: "quran" | "tafsir" | "asbab_nuzul" | "hadith";
  outcome: ComponentOutcome | null;
  evidence_ids: string[];
  verified_location: AyahRef[];
  detail: string | null;
}

export interface StrengthObservation {
  signal: string;
  basis: string;
}

export interface EvidenceAssessment {
  evidence_id: string;
  relationship: "supports" | "partially_supports" | "contradicts" | "insufficient";
  claim_component: string | null;
  component_id: string | null;
  evidence_span: string | null;
  supported_part: string | null;
  unsupported_part: string | null;
  rationale: string;
  assessed_by: "deterministic" | "llm_analysis";
  strength: { observations: StrengthObservation[] };
}

export interface Evidence {
  evidence_id: string;
  source_type: "quran" | "tafsir" | "asbab_nuzul" | "hadith";
  text: string;
  source_name: string;
  provider: string;
  trusted_source_id: TrustedSourceId;
  reference: string;
  source_address: string;
  source_url: string | null;
  source_record_id: string | null;
  retrieval_channel: "official_dump" | "live_api";
  source_version: string | null;
  retrieved_at: string;
  text_sha256: string;
  metadata: Record<string, unknown> & {
    relation_type?: string;
    provider_author?: string | null;
    page_kind?: "printed" | "provider" | "none";
  };
}

export interface VerificationOutcome {
  kind: "verification";
  claim_id: string;
  confirmed_claim_text: string;
  status: VerificationStatus;
  result_group: ResultGroup | null;
  why: string | null;
  what_to_do: string | null;
  evidence: Evidence[];
  analysis: {
    assessments: EvidenceAssessment[];
    components: ClaimComponent[];
    related_unverified_addresses: string[];
    evidence_conflicts: { evidence_ids: string[]; description: string }[];
  };
  validation: { outcome: "pass" | "retry" | "abstain" };
}

export interface OutOfScopeOutcome {
  kind: "out_of_scope";
  claim_id: string;
  reason: "unsupported_claim_category" | "outside_source_coverage";
  detail: string | null;
}

export interface RequiredSourceUnavailableOutcome {
  kind: "required_source_unavailable";
  claim_id: string;
  confirmed_claim_text: string;
  required_claim_types: string[];
  unavailable_sources: TrustedSourceId[];
  detail: string | null;
}

export interface SystemErrorOutcome {
  kind: "system_error";
  claim_id: string;
  error: { code: string; stage: string | null; message: string; retryable: boolean };
}

export type ClaimOutcome =
  | VerificationOutcome
  | OutOfScopeOutcome
  | RequiredSourceUnavailableOutcome
  | SystemErrorOutcome;

export interface FinalUserResult {
  run_id: string;
  created_at: string;
  outcomes: ClaimOutcome[];
  limitations: string[];
}

/** One claim in the report (client state). */
export type ClaimRun =
  | { state: "waiting"; claim: ConfirmedClaim }
  | { state: "running"; claim: ConfirmedClaim }
  | { state: "done"; claim: ConfirmedClaim; runId: string; outcome: ClaimOutcome }
  /** The request itself failed (network / service) — a technical problem, never a verdict. */
  | { state: "failed"; claim: ConfirmedClaim; code: string };

export type VerifyCallResult =
  | { kind: "result"; result: FinalUserResult }
  | { kind: "input_error"; code: string }
  | { kind: "failure"; code: string; retryable: boolean }
  | { kind: "network_error" };

export interface AlternativeWording {
  kind: "alternative_wording";
  original_claim_id: string;
  run_id: string;
  proposed_text: string | null;
  verified: boolean;
  outcome: ClaimOutcome | null;
}

export type AlternativeCallResult =
  | { kind: "alternative"; result: AlternativeWording }
  | { kind: "input_error"; code: string }
  | { kind: "failure"; code: string; retryable: boolean }
  | { kind: "network_error" };
