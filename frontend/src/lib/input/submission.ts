/** Builders for prepared submissions. They preserve the user's text exactly. */
import type { ImageSelection, PreparedSubmission } from "./types";

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

export function prepareContentImage(image: ImageSelection): PreparedSubmission {
  return { kind: "full_content_image", preparedAt: now(), next: "ocr", image };
}
