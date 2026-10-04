"use client";

import { useEffect, useId, useRef, useState, type DragEvent, type FormEvent } from "react";
import { Card } from "@/components/Card";
import { ImageIcon, UploadIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";
import { FieldError } from "@/components/ui/FieldError";
import { Notice } from "@/components/ui/Notice";
import { getDictionary } from "@/i18n";
import { formatFileSize } from "@/lib/format";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { prepareContentImage } from "@/lib/input/submission";
import { ACCEPTED_IMAGE_EXTENSIONS, ACCEPTED_IMAGE_TYPES } from "@/lib/input/types";
import { hasImageSignature, validateImageFile } from "@/lib/input/validation";

const t = getDictionary();
const ACCEPT = [...ACCEPTED_IMAGE_TYPES, ...ACCEPTED_IMAGE_EXTENSIONS].join(",");

/** Object URL for previewing the selected image (revoked on change/unmount). */
function usePreviewUrl(file: File | null): string | null {
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
 * Image mode — upload UI and state only (Task 2). OCR is Task 3: no text is
 * produced or faked here. Next: Image → OCR → Review Extracted Text → Claim Extraction.
 */
export function ImageUploadPanel() {
  const { state, dispatch } = useInputSession();
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const ids = { input: useId(), hint: useId(), error: useId() };
  const image = state.image;
  const previewUrl = usePreviewUrl(image?.file ?? null);
  const prepared = state.prepared?.kind === "full_content_image" ? state.prepared : null;

  const selectFile = async (file: File | undefined) => {
    if (!file) return;
    const check = validateImageFile(file);
    if (!check.ok) {
      setError(check.reason === "empty_file" ? t.fullContent.imageErrorEmpty : t.fullContent.imageErrorType);
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
    void selectFile(e.dataTransfer.files?.[0]);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!image) {
      setError(t.fullContent.imageErrorMissing);
      inputRef.current?.focus();
      return;
    }
    setError(null);
    dispatch({ type: "prepared/set", submission: prepareContentImage(image) });
  };

  if (prepared) {
    return (
      <Notice tone="success" role="status" title={t.fullContent.imagePreparedTitle}>
        <p className="font-medium" dir="auto">
          {prepared.image.name}
        </p>
        <p>{t.fullContent.imagePreparedNext}</p>
        <p className="text-sm text-[var(--color-muted)]">{t.common.nextStepPending}</p>
        <Button variant="secondary" onClick={() => dispatch({ type: "prepared/clear" })}>
          {t.common.edit}
        </Button>
      </Notice>
    );
  }

  return (
    <Card>
      <form noValidate onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-2">
          <p className="text-lg font-bold">{t.fullContent.imageLabel}</p>
          <p id={ids.hint} className="text-sm text-[var(--color-muted)]">
            {t.fullContent.imageHint}
          </p>

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
                      onClick={() => {
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
                <p className="text-sm text-[var(--color-muted)]">{t.fullContent.imageFormats}</p>
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
              aria-label={t.fullContent.imageChoose}
              aria-describedby={[ids.hint, error ? ids.error : null].filter(Boolean).join(" ")}
              aria-invalid={error ? true : undefined}
              className="sr-only"
              onChange={(e) => void selectFile(e.target.files?.[0])}
            />
          </div>
          <FieldError id={ids.error} message={error} />
        </div>
        <Button type="submit" className="w-full sm:w-auto">
          {t.fullContent.imageSubmit}
        </Button>
      </form>
    </Card>
  );
}
