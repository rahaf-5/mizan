/** Pure Claim Review helpers (no network). */
import type { ConfirmPayload } from "./client";
import type { ExtractedClaim, ReviewClaim, ReviewSession } from "./types";

let counter = 0;
export function newClaimId(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  counter += 1;
  return `manual-${Date.now()}-${counter}`;
}

export function fromExtracted(claims: ExtractedClaim[]): ReviewClaim[] {
  return claims.map((c) => ({
    id: c.claim_id,
    origin: "extracted",
    originalText: c.original_text,
    extractedText: c.extracted_claim_text,
    text: c.extracted_claim_text,
    selected: true,
    extractionStatus: c.extraction_status,
    providedEvidence: c.provided_evidence,
    providedReference: c.provided_reference,
  }));
}

export function manualClaim(text: string): ReviewClaim {
  return {
    id: newClaimId(),
    origin: "manual",
    originalText: text,
    extractedText: null,
    text,
    selected: true,
    extractionStatus: null,
    providedEvidence: null,
    providedReference: null,
  };
}

export const isEdited = (c: ReviewClaim): boolean =>
  c.origin === "extracted" && c.extractedText !== null && c.text !== c.extractedText;

export const selectedClaims = (review: ReviewSession): ReviewClaim[] =>
  review.claims.filter((c) => c.selected);

/** Build the explicit confirmation request. Deleted claims are simply absent. */
export function buildConfirmPayload(review: ReviewSession): ConfirmPayload {
  return {
    explicit_user_confirmation: true,
    claims: review.claims.map((c) => ({
      claim_id: c.id,
      origin: c.origin,
      original_text: c.originalText,
      extracted_claim_text: c.extractedText,
      text: c.text,
      selected: c.selected,
      extraction_status: c.extractionStatus,
      provided_evidence: c.providedEvidence,
      provided_reference: c.providedReference,
    })),
  };
}
