/**
 * Frontend mirror of the approved backend domain contracts.
 * Source of truth: backend/app/domain (exported to contracts/domain-contracts.json).
 * tests/contracts.test.ts fails if these drift from the shared snapshot.
 */

export const VERIFICATION_STATUSES = [
  "supported",
  "partially_supported",
  "contradicted",
  "insufficient_evidence",
  "no_evidence_found",
  "conflicting_evidence",
] as const;
export type VerificationStatus = (typeof VERIFICATION_STATUSES)[number];

/** `no_evidence_found` is a retrieval outcome, NOT an evidence relationship. */
export const EVIDENCE_RELATIONSHIPS = [
  "supports",
  "partially_supports",
  "contradicts",
  "insufficient",
] as const;
export type EvidenceRelationship = (typeof EVIDENCE_RELATIONSHIPS)[number];

export const CLAIM_TYPES = ["quran", "tafsir", "asbab_nuzul", "hadith"] as const;
export type ClaimType = (typeof CLAIM_TYPES)[number];

export const EXTRACTION_STATUSES = ["clear", "ambiguous", "incomplete"] as const;
export type ExtractionStatus = (typeof EXTRACTION_STATUSES)[number];

export const USER_CONFIRMATION_STATUSES = ["pending", "confirmed", "edited"] as const;
export type UserConfirmationStatus = (typeof USER_CONFIRMATION_STATUSES)[number];

export const RESULT_GROUPS = [
  "verified",
  "do_not_use_as_written",
  "needs_revision",
  "needs_evidence_review",
] as const;
export type ResultGroup = (typeof RESULT_GROUPS)[number];

/** A claim ends in exactly one of these structurally separate outcome kinds. */
export const CLAIM_OUTCOME_KINDS = [
  "verification",
  "out_of_scope",
  "system_error",
  /** A required trusted source (e.g. Hadith/Dorar) is unavailable: explicit abstention, not a status. */
  "required_source_unavailable",
] as const;
export type ClaimOutcomeKind = (typeof CLAIM_OUTCOME_KINDS)[number];

export const OUT_OF_SCOPE_REASONS = [
  "unsupported_claim_category",
  "outside_source_coverage",
] as const;
export type OutOfScopeReason = (typeof OUT_OF_SCOPE_REASONS)[number];

export const TRUSTED_SOURCE_IDS = [
  "quran",
  "tafsir_al_muyassar",
  "tafsir_ibn_kathir",
  "asbab_al_nuzul_al_wahidi",
  "al_muharrar_fi_asbab_al_nuzul",
  "dorar_hadith",
] as const;
export type TrustedSourceId = (typeof TRUSTED_SOURCE_IDS)[number];

/** Check modes (backend CheckMode). */
export const CHECK_MODES = ["quick_check", "full_content"] as const;
export type CheckMode = (typeof CHECK_MODES)[number];

/** Input types (backend InputType). MVP is text only — image/OCR is out of scope. */
export const INPUT_TYPES = ["text"] as const;
export type InputType = (typeof INPUT_TYPES)[number];
