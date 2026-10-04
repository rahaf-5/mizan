"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type DragEvent, type FormEvent } from "react";
import { Card } from "@/components/Card";
import { ImageIcon, UploadIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";
import { FieldError } from "@/components/ui/FieldError";
import { Notice } from "@/components/ui/Notice";
import { getDictionary } from "@/i18n";
import { formatFileSize, formatNumber } from "@/lib/format";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { ACCEPTED_IMAGE_EXTENSIONS, ACCEPTED_IMAGE_TYPES } from "@/lib/input/types";
import { hasImageSignature, validateImageFile } from "@/lib/input/validation";
import { runOcr, type OcrCallResult } from "@/lib/ocr/client";
import { OCR_MAX_UPLOAD_MB } from "@/lib/ocr/types";

const t = getDictionary();
const ACCEPT = [...ACCEPTED_IMAGE_TYPES, ...ACCEPTED_IMAGE_EXTENSIONS].join(",");
const MB = formatNumber(OCR_MAX_UPLOAD_MB);

type OcrProblem = { message: string; retryable: boolean } | null;

/** Technical OCR problems — shown as processing errors, never as content judgements. */
function problemFor(result: Exclude<OcrCallResult, { kind: "extraction" | "input_error" }>): OcrProblem {
  if (result.kind === "network_error") return { message: t.fullContent.ocrFailedNetwork, retryable: true };
  if (result.code === "ocr_not_configured") return { message: t.fullContent.ocrNotConfigured, retryable: false };
  return { message: t.fullContent.ocrFailedTechnical, retryable: result.retryable };
}

function inputErrorMessage(code: string): string {
  switch (code) {
    case "file_too_large":
      return t.fullContent.imageErrorTooLarge(MB);
    case "empty_file":
      return t.fullContent.imageErrorEmpty;
    case "image_too_many_pixels":
      return t.fullContent.imageErrorTooManyPixels;
    case "unreadable_image":
      return t.fullContent.imageErrorCorrupt;
    default:
      return t.fullContent.imageErrorType;
  }
}

/** Object URL for previewing the selected image (revoked on change/unmount). */
export function usePreviewUrl(file: File | null): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!file || typeof URL.createObjectURL !== "function") return;
    const u = URL.createObjectURL(file);
    // Publish the URL created for this file; cleanup revokes it.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUrl(u);
    return () => {
      URL.revokeObjectURL(u);
      setUrl(null);
    };
  }, [file]);
  return file ? url : null;
}

/**
 * Image mode. Sends the image to the Mizan backend for OCR, then opens the
 * Review Extracted Text screen. OCR output is NEVER sent to claim extraction
 * or verification from here.
 */
export function ImageUploadPanel() {
  const router = useRouter();
  const { state, dispatch } = useInputSession();
  const [error, setError] = useState<string | null>(null);
  const [problem, setProblem] = useState<OcrProblem>(null);
  const [processing, setProcessing] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const ids = { input: useId(), hint: useId(), error: useId(), status: useId(), privacy: useId() };
  const image = state.image;
  const previewUrl = usePreviewUrl(image?.file ?? null);

  const selectFile = async (file: File | undefined) => {
    if (!file) return;
    setProblem(null);
    const check = validateImageFile(file);
    if (!check.ok) {
      setError(
        check.reason === "empty_file"
          ? t.fullContent.imageErrorEmpty
          : check.reason === "too_large"
            ? t.fullContent.imageErrorTooLarge(MB)
            : t.fullContent.imageErrorType,
      );
      return;
    }
    if (!(await hasImageSignature(file, check.type))) {
      setError(t.fullContent.imageErrorCorrupt);
      return;
    }
    setError(null);
    dispatch({
      type: "content/setImage",
      image: { file, name: file.name, type: check.type, sizeBytes: file.size },
    });
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!processing) void selectFile(e.dataTransfer.files?.[0]);
  };

  const startOcr = async () => {
    if (!image || processing) return;
    setError(null);
    setProblem(null);
    setProcessing(true);
    const result = await runOcr(image.file, image.name);
    setProcessing(false);
    if (result.kind === "extraction") {
      dispatch({ type: "ocr/received", image, extraction: result.data });
      router.push("/full-content/review");
    } else if (result.kind === "input_error") {
      setError(inputErrorMessage(result.code));
    } else {
      setProblem(problemFor(result));
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!image) {
      setError(t.fullContent.imageErrorMissing);
      inputRef.current?.focus();
      return;
    }
    void startOcr();
  };

  return (
    <Card>
      <form noValidate onSubmit={onSubmit} className="space-y-4" aria-busy={processing || undefined}>
        <div className="space-y-2">
          <p className="text-lg font-bold">{t.fullContent.imageLabel}</p>
          <p id={ids.hint} className="text-sm text-[var(--color-muted)]">
            {t.fullContent.imageHint}
          </p>
          <Notice id={ids.privacy} tone="info" title={t.fullContent.privacyTitle} className="text-sm">
            <p>{t.fullContent.privacyNotice}</p>
          </Notice>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            data-dragging={dragging || undefined}
            className="rounded-2xl border-2 border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface)] p-6 text-center transition-colors focus-within:outline focus-within:outline-3 focus-within:outline-offset-2 focus-within:outline-[var(--color-focus)] data-[dragging]:border-[var(--color-brand)] data-[dragging]:bg-[var(--color-brand-soft)] sm:p-8"
          >
            {image ? (
              <div className="flex flex-col items-center gap-4 sm:flex-row sm:text-start">
                {previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element -- local blob preview
                  <img
                    src={previewUrl}
                    alt={t.fullContent.imagePreviewAlt}
                    className="max-h-48 w-auto max-w-full rounded-xl border border-[var(--color-border)] object-contain"
                  />
                ) : (
                  <ImageIcon className="size-12 text-[var(--color-muted)]" />
                )}
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="text-sm text-[var(--color-muted)]">{t.fullContent.imageSelected}</p>
                  <p className="break-all font-medium" dir="auto">
                    {image.name}
                  </p>
                  <p className="text-sm text-[var(--color-muted)]">{formatFileSize(image.sizeBytes)}</p>
                  <div className="flex flex-wrap justify-center gap-2 pt-2 sm:justify-start">
                    <label
                      htmlFor={ids.input}
                      className="inline-flex min-h-11 cursor-pointer items-center rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-card)] px-4 py-2 font-medium hover:border-[var(--color-brand)]"
                    >
                      {t.fullContent.imageReplace}
                    </label>
                    <Button
                      variant="ghost"
                      disabled={processing}
                      onClick={() => {
                        setProblem(null);
                        dispatch({ type: "content/setImage", image: null });
                        if (inputRef.current) inputRef.current.value = "";
                      }}
                    >
                      {t.fullContent.imageRemove}
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <span className="grid size-14 place-items-center rounded-2xl bg-[var(--color-brand-soft)] text-[var(--color-brand)]">
                  <UploadIcon className="size-7" />
                </span>
                <p className="font-medium">{t.fullContent.imageDropTitle}</p>
                <p className="text-sm text-[var(--color-muted)]">{t.fullContent.imageFormats(MB)}</p>
                <label
                  htmlFor={ids.input}
                  className="inline-flex min-h-11 cursor-pointer items-center rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-card)] px-5 py-2 font-medium hover:border-[var(--color-brand)]"
                >
                  {t.fullContent.imageChoose}
                </label>
              </div>
            )}
            <input
              id={ids.input}
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              disabled={processing}
              aria-label={t.fullContent.imageChoose}
              aria-describedby={[ids.hint, ids.privacy, error ? ids.error : null].filter(Boolean).join(" ")}
              aria-invalid={error ? true : undefined}
              className="sr-only"
              onChange={(e) => void selectFile(e.target.files?.[0])}
            />
          </div>
          <FieldError id={ids.error} message={error} />
        </div>

        {problem ? (
          <Notice tone="warning" role="alert" title={t.fullContent.ocrFailedTitle}>
            <p>{problem.message}</p>
            {problem.retryable ? (
              <Button variant="secondary" onClick={() => void startOcr()}>
                {t.fullContent.ocrRetry}
              </Button>
            ) : null}
          </Notice>
        ) : null}

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" className="w-full sm:w-auto" disabled={processing}>
            {t.fullContent.imageSubmit}
          </Button>
          <p id={ids.status} role="status" className="flex items-center gap-2 text-[var(--color-muted)]">
            {processing ? (
              <>
                <span
                  aria-hidden="true"
                  className="size-4 animate-spin rounded-full border-2 border-[var(--color-brand)] border-t-transparent"
                />
                {t.fullContent.ocrProcessing}
              </>
            ) : null}
          </p>
        </div>
      </form>
    </Card>
  );
}
