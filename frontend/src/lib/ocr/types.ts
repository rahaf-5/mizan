/**
 * Mirror of backend OCR contracts (backend/app/domain/ocr.py, app/api/v1/ocr.py).
 * Checked against contracts/domain-contracts.json by tests/unit/contracts.test.ts.
 *
 * OCR confidence is a reading-quality signal only — never verification confidence.
 */

export const OCR_STATUSES = ["completed", "completed_with_warnings", "no_text_found"] as const;
export type OcrStatus = (typeof OCR_STATUSES)[number];

export const OCR_WARNING_CODES = ["low_confidence_text", "low_resolution_image"] as const;
export type OcrWarningCode = (typeof OCR_WARNING_CODES)[number];

export const OCR_INPUT_ERROR_CODES = [
  "unsupported_type",
  "empty_file",
  "file_too_large",
  "unreadable_image",
  "image_too_many_pixels",
] as const;
export type OcrInputErrorCode = (typeof OCR_INPUT_ERROR_CODES)[number];

/** LOCKED upload limit (7 MiB) — must equal backend MAX_UPLOAD_BYTES. */
export const OCR_MAX_UPLOAD_BYTES = 7 * 1024 * 1024;
export const OCR_MAX_UPLOAD_MB = 7;

export interface OcrWarning {
  code: OcrWarningCode;
  detail: string | null;
}

export interface OcrConfidence {
  page_confidence: number | null;
  word_count: number;
  low_confidence_threshold: number;
  low_confidence_word_count: number;
  low_confidence_words: { text: string; confidence: number }[];
}

/** Technically successful OCR. `raw_text` is exactly what the provider returned. */
export interface OcrExtraction {
  kind: "extraction";
  ocr_id: string;
  provider: string;
  status: OcrStatus;
  raw_text: string;
  warnings: OcrWarning[];
  confidence: OcrConfidence | null;
  detected_languages: string[];
  image: { mime_type: string; size_bytes: number; width: number; height: number };
  processed_at: string;
}

/** OCR could not run — a technical problem, never a verification status. */
export interface OcrFailure {
  kind: "failure";
  provider: string;
  error: { code: string; stage: string | null; message: string; retryable: boolean };
}

export interface OcrInputErrorResponse {
  kind: "input_error";
  code: OcrInputErrorCode;
  message: string;
}
