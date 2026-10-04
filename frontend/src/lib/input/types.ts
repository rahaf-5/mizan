/**
 * Typed input-stage contracts.
 *
 * These describe what the user prepared on the input screens. They reuse the
 * domain contracts (CheckMode, InputType, ExtractionInput) and do not redefine
 * any verification concept. Nothing here triggers verification.
 *
 * MVP flow (text only — image input/OCR is out of MVP scope):
 *   Quick Check:   claim text → (Task 4) review/confirm → verification
 *   Full Content:  text → claim extraction → claim review → explicit confirmation
 *                  (lib/claims) → (Task 5+) verification
 */
import type { CheckMode, InputType } from "@/lib/domain";

/** Mirrors backend `ExtractionInput` (backend/app/domain/inputs.py). */
export interface ExtractionInputPayload {
  mode: CheckMode;
  input_type: InputType;
  /** Exactly as the user entered it — never rewritten or "corrected". */
  text: string;
}

/** The step each prepared submission is waiting for (none of them is verification). */
export type NextStep = "claim_confirmation";

export type PreparedSubmission =
  | {
      kind: "quick_check_claim";
      preparedAt: string;
      extractionInput: ExtractionInputPayload;
      next: "claim_confirmation";
    };
