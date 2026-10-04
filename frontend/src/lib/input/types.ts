/**
 * Typed input-stage contracts (Task 2).
 *
 * These describe what the user prepared on the input screens. They reuse the
 * Task 1 domain contracts (CheckMode, InputType, ExtractionInput) and do not
 * redefine any verification concept. Nothing here triggers verification.
 *
 * Approved flow:
 *   Quick Check:   claim text → (Task 4) review/confirm → verification
 *   Full (text):   text → (Task 4) claim extraction → claim review → verification
 *   Full (image):  image → (Task 3) OCR → review extracted text → claim extraction → …
 */
import type { CheckMode, InputType } from "@/lib/domain";

/** Mirrors backend `ExtractionInput` (backend/app/domain/inputs.py). */
export interface ExtractionInputPayload {
  mode: CheckMode;
  input_type: InputType;
  /** Exactly as the user entered it — never rewritten or "corrected". */
  text: string;
  /** Only meaningful for image input after OCR review (Task 3). */
  ocr_text_reviewed_by_user: boolean;
}

export const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png"] as const;
export type AcceptedImageType = (typeof ACCEPTED_IMAGE_TYPES)[number];
export const ACCEPTED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png"] as const;

export interface ImageSelection {
  file: File;
  name: string;
  type: AcceptedImageType;
  sizeBytes: number;
}

export type ContentMode = Extract<InputType, "text" | "image">;

/** The step each prepared submission is waiting for (none of them is verification). */
export type NextStep = "claim_confirmation" | "claim_extraction" | "ocr";

export type PreparedSubmission =
  | {
      kind: "quick_check_claim";
      preparedAt: string;
      extractionInput: ExtractionInputPayload;
      next: "claim_confirmation";
    }
  | {
      kind: "full_content_text";
      preparedAt: string;
      extractionInput: ExtractionInputPayload;
      next: "claim_extraction";
    }
  | {
      /**
       * Deliberately has NO text / ExtractionInputPayload: an image cannot reach
       * Claim Extraction until OCR text exists and the user has reviewed it (spec §16).
       */
      kind: "full_content_image";
      preparedAt: string;
      image: ImageSelection;
      next: "ocr";
    };
