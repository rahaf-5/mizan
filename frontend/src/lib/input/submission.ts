/** Builders for prepared submissions. They preserve the user's text exactly. */
import type { OcrSession, PreparedSubmission } from "./types";

const now = () => new Date().toISOString();

export function prepareQuickCheckClaim(text: string): PreparedSubmission {
  return {
    kind: "quick_check_claim",
    preparedAt: now(),
    next: "claim_confirmation",
    extractionInput: {
      mode: "quick_check",
      input_type: "text",
      text,
      ocr_text_reviewed_by_user: false,
    },
  };
}

export function prepareContentText(text: string): PreparedSubmission {
  return {
    kind: "full_content_text",
    preparedAt: now(),
    next: "claim_extraction",
    extractionInput: {
      mode: "full_content",
      input_type: "text",
      text,
      ocr_text_reviewed_by_user: false,
    },
  };
}

/** Build the Task 4 input from the USER-REVIEWED OCR text (raw text kept alongside). */
export function prepareReviewedOcrText(ocr: OcrSession): PreparedSubmission {
  return {
    kind: "full_content_reviewed_ocr_text",
    preparedAt: now(),
    next: "claim_extraction",
    extractionInput: {
      mode: "full_content",
      input_type: "image",
      text: ocr.reviewedText,
      ocr_text_reviewed_by_user: true,
    },
    ocr: {
      ocrId: ocr.extraction.ocr_id,
      provider: ocr.extraction.provider,
      rawText: ocr.extraction.raw_text,
      editedByUser: ocr.reviewedText !== ocr.extraction.raw_text,
    },
  };
}
