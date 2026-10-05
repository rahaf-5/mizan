/**
 * Pure input validation for the Task 2 screens. UI guidance only —
 * this is NOT claim extraction and makes no judgement about content.
 */
export const isBlank = (text: string): boolean => text.trim().length === 0;

/** Sentence terminators used in Arabic and Latin text. */
const SENTENCE_SPLIT = /[.!?؟؛;]+(?=\s|$)/u;
const MIN_WORDS_PER_SENTENCE = 3;
const PARAGRAPH_WORD_THRESHOLD = 60;

const wordCount = (s: string): number => s.trim().split(/\s+/u).filter(Boolean).length;

/**
 * Heuristic: does the Quick Check input look like a paragraph or several claims?
 * Used only to SUGGEST Full Content Check (spec §2A); the user may continue anyway.
 */
export function looksLikeMultipleClaims(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed) return false;
  const lines = trimmed.split(/\n+/u).filter((l) => wordCount(l) > 0);
  if (lines.length >= 2) return true;
  if (wordCount(trimmed) > PARAGRAPH_WORD_THRESHOLD) return true;
  const sentences = trimmed
    .split(SENTENCE_SPLIT)
    .filter((s) => wordCount(s) >= MIN_WORDS_PER_SENTENCE);
  return sentences.length >= 2;
}

export type QuickCheckValidation =
  | { status: "ok" }
  | { status: "empty" }
  | { status: "multiple_claims_suspected" }
  | { status: "too_long"; max: number };

/** Same limit the backend confirmation gate enforces on one claim (MAX_CLAIM_CHARS). */
export const QUICK_CHECK_MAX_CHARS = 1_000;

export const isTooLongClaim = (text: string): boolean => text.length > QUICK_CHECK_MAX_CHARS;

export function validateQuickCheck(text: string): QuickCheckValidation {
  if (isBlank(text)) return { status: "empty" };
  // Several claims → guide to Full Content first (the right place for long text).
  if (looksLikeMultipleClaims(text)) return { status: "multiple_claims_suspected" };
  if (isTooLongClaim(text)) return { status: "too_long", max: QUICK_CHECK_MAX_CHARS };
  return { status: "ok" };
}

export type ContentTextValidation = { status: "ok" } | { status: "empty" };

export function validateContentText(text: string): ContentTextValidation {
  return isBlank(text) ? { status: "empty" } : { status: "ok" };
}
