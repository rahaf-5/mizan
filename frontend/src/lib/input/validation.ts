/**
 * Pure input validation for the Task 2 screens. UI guidance only —
 * this is NOT claim extraction and makes no judgement about content.
 */
import {
  ACCEPTED_IMAGE_EXTENSIONS,
  ACCEPTED_IMAGE_TYPES,
  type AcceptedImageType,
} from "./types";
import { OCR_MAX_UPLOAD_BYTES } from "@/lib/ocr/types";

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
  | { status: "multiple_claims_suspected" };

export function validateQuickCheck(text: string): QuickCheckValidation {
  if (isBlank(text)) return { status: "empty" };
  if (looksLikeMultipleClaims(text)) return { status: "multiple_claims_suspected" };
  return { status: "ok" };
}

export type ContentTextValidation = { status: "ok" } | { status: "empty" };

export function validateContentText(text: string): ContentTextValidation {
  return isBlank(text) ? { status: "empty" } : { status: "ok" };
}

export type ImageValidation =
  | { ok: true; type: AcceptedImageType }
  | { ok: false; reason: "unsupported_type" | "empty_file" | "too_large" };

const extensionOf = (name: string): string => {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
};

/** Accept only JPG/PNG: declared MIME type and file extension must both agree. */
export function validateImageFile(file: Pick<File, "name" | "type" | "size">): ImageValidation {
  const ext = extensionOf(file.name);
  const extOk = (ACCEPTED_IMAGE_EXTENSIONS as readonly string[]).includes(ext);
  const mime = file.type.toLowerCase();
  const inferred: AcceptedImageType | null =
    ext === ".png" ? "image/png" : ext === ".jpg" || ext === ".jpeg" ? "image/jpeg" : null;
  let type: AcceptedImageType | null = null;
  if ((ACCEPTED_IMAGE_TYPES as readonly string[]).includes(mime)) {
    type = mime as AcceptedImageType;
    if (!extOk || inferred !== type) return { ok: false, reason: "unsupported_type" };
  } else if (mime === "" && inferred) {
    type = inferred; // some systems omit the MIME type
  } else {
    return { ok: false, reason: "unsupported_type" };
  }
  if (file.size === 0) return { ok: false, reason: "empty_file" };
  if (file.size > OCR_MAX_UPLOAD_BYTES) return { ok: false, reason: "too_large" };
  return { ok: true, type };
}

/** Check the file's leading bytes really are JPEG or PNG (guards renamed files). */
export async function hasImageSignature(file: Blob, type: AcceptedImageType): Promise<boolean> {
  const head = new Uint8Array(await file.slice(0, 8).arrayBuffer());
  if (type === "image/png") {
    const png = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
    return png.every((b, i) => head[i] === b);
  }
  return head[0] === 0xff && head[1] === 0xd8 && head[2] === 0xff;
}
