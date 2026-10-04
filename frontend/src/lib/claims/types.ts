/**
 * Claim Extraction / Claim Review contracts (Task 4).
 * Mirrors backend/app/api/v1/claims.py. Extraction is NOT verification:
 * nothing here carries a status, verdict, grading, evidence or citation.
 */
import type { ExtractionStatus, UserConfirmationStatus } from "@/lib/domain";

/** Limits — must equal backend `app/domain/inputs.py` (checked by contract tests). */
export const CLAIM_EXTRACTION_MAX_INPUT_CHARS = 10_000;
export const CLAIM_MAX_CHARS = 1_000;
export const MAX_REVIEW_CLAIMS = 50;

export interface ProvidedEvidence {
  provided_evidence_type: "quran" | "hadith";
  provided_evidence_text: string;
}

/** A claim as returned by POST /api/v1/claims/extract (always pending). */
export interface ExtractedClaim {
  claim_id: string;
  original_text: string;
  extracted_claim_text: string;
  extraction_status: ExtractionStatus;
  provided_evidence: ProvidedEvidence | null;
  provided_reference: string | null;
  user_confirmation_status: "pending";
}

/** A claim on the Claim Review screen (client-side, session only). */
export interface ReviewClaim {
  id: string;
  origin: "extracted" | "manual";
  /** Verbatim excerpt from the user's content (manual: the typed text). */
  originalText: string;
  /** Text as extracted (null for manual claims). Never overwritten by edits. */
  extractedText: string | null;
  /** Current text — becomes confirmed_claim_text on confirmation. */
  text: string;
  selected: boolean;
  extractionStatus: ExtractionStatus | null;
  providedEvidence: ProvidedEvidence | null;
  providedReference: string | null;
}

export interface ReviewSession {
  /** The Full Content text the claims were extracted from. */
  sourceText: string;
  claims: ReviewClaim[];
}

/** Backend ConfirmedClaim (domain gate output) — ready for the future pipeline. */
export interface ConfirmedClaim {
  claim_id: string;
  confirmed_claim_text: string;
  user_confirmation_status: Extract<UserConfirmationStatus, "confirmed" | "edited">;
  claim_type: null;
  provided_evidence: ProvidedEvidence | null;
  provided_reference: string | null;
}

export interface ConfirmationResult {
  confirmedClaims: ConfirmedClaim[];
  nextStage: "claim_classification";
}

export type ExtractCallResult =
  | { kind: "extraction"; claims: ExtractedClaim[]; discardedUngroundedCount: number }
  | { kind: "input_error"; code: string }
  | { kind: "failure"; code: string; retryable: boolean }
  | { kind: "network_error" };

export type ConfirmCallResult =
  | { kind: "confirmed"; result: ConfirmationResult }
  | { kind: "input_error"; code: string }
  | { kind: "failure"; code: string; retryable: boolean }
  | { kind: "network_error" };
