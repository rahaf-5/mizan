import { publicConfig } from "@/lib/config";
import type { OcrExtraction, OcrFailure, OcrInputErrorCode, OcrInputErrorResponse } from "./types";

/** Result of calling the backend OCR endpoint. Technical problems are kept separate. */
export type OcrCallResult =
  | { kind: "extraction"; data: OcrExtraction }
  | { kind: "input_error"; code: OcrInputErrorCode }
  | { kind: "failure"; code: string; retryable: boolean }
  | { kind: "network_error" };

export const OCR_ENDPOINT = "/api/v1/ocr";

/**
 * Send the image to the Mizan backend for OCR. The backend holds any provider
 * credentials; the browser never talks to an OCR provider directly.
 */
export async function runOcr(file: Blob, filename: string, timeoutMs = 60_000): Promise<OcrCallResult> {
  const form = new FormData();
  form.append("image", file, filename);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${publicConfig.apiBaseUrl}${OCR_ENDPOINT}`, {
      method: "POST",
      body: form,
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    const kind = (body as { kind?: string } | null)?.kind;
    if (res.ok && kind === "extraction") return { kind: "extraction", data: body as OcrExtraction };
    if (kind === "input_error") return { kind: "input_error", code: (body as OcrInputErrorResponse).code };
    if (kind === "failure") {
      const f = body as OcrFailure;
      return { kind: "failure", code: f.error.code, retryable: f.error.retryable };
    }
    return { kind: "failure", code: `http_${res.status}`, retryable: true };
  } catch {
    return { kind: "network_error" };
  } finally {
    clearTimeout(timer);
  }
}
