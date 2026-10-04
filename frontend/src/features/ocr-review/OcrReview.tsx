"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useRef, useState, type FormEvent } from "react";
import { Card } from "@/components/Card";
import { ImageIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";
import { FieldError } from "@/components/ui/FieldError";
import { Notice } from "@/components/ui/Notice";
import { usePreviewUrl } from "@/features/full-content/ImageUploadPanel";
import { getDictionary } from "@/i18n";
import { formatNumber } from "@/lib/format";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { prepareReviewedOcrText } from "@/lib/input/submission";
import { isBlank } from "@/lib/input/validation";
import type { OcrExtraction } from "@/lib/ocr/types";

const t = getDictionary();

/** Status banner derived only from OCR facts (no numeric confidence shown). */
function OcrStatusNotice({
  extraction,
  onReplace,
}: {
  extraction: OcrExtraction;
  onReplace: () => void;
}) {
  if (extraction.status === "completed") {
    return (
      <Notice tone="info" title={t.ocrReview.infoTitle}>
        <p>{t.ocrReview.infoBody}</p>
      </Notice>
    );
  }
  const lowRes = extraction.warnings.some((w) => w.code === "low_resolution_image");
  const words = extraction.confidence?.low_confidence_words ?? [];
  return (
    <Notice tone="warning" role="alert" title={t.ocrReview.partialTitle}>
      <p>{t.ocrReview.partialBody}</p>
      {words.length > 0 ? (
        <div className="space-y-1.5">
          <p className="text-sm font-medium">{t.ocrReview.lowConfidenceWords}</p>
          <ul className="flex flex-wrap gap-1.5">
            {words.map((w, i) => (
              <li
                key={`${w.text}-${i}`}
                dir="auto"
                className="rounded-lg border border-[var(--color-warning-border)] bg-[var(--color-card)] px-2 py-0.5 text-sm"
              >
                {w.text}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {lowRes ? <p className="text-sm">{t.ocrReview.lowResolution}</p> : null}
      <Button variant="secondary" onClick={onReplace}>
        {t.ocrReview.uploadClearer}
      </Button>
    </Notice>
  );
}

/**
 * Review Extracted Text (spec §16). The user must see and may correct the OCR
 * output. Confirming saves the REVIEWED text for Claim Extraction (Task 4);
 * it does not extract claims or verify anything. Raw OCR text is never modified.
 */
export function OcrReview() {
  const router = useRouter();
  const { state, dispatch } = useInputSession();
  const [error, setError] = useState<string | null>(null);
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const ids = { field: useId(), hint: useId(), error: useId(), count: useId(), edited: useId() };
  const ocr = state.ocr;
  const previewUrl = usePreviewUrl(ocr?.image.file ?? null);

  const replaceImage = () => {
    dispatch({ type: "ocr/clear" });
    dispatch({ type: "content/setMode", mode: "image" });
    router.push("/full-content");
  };

  const typeManually = () => {
    dispatch({ type: "ocr/clear" });
    dispatch({ type: "content/setMode", mode: "text" });
    router.push("/full-content");
  };

  if (!ocr) {
    return (
      <Notice tone="info" title={t.ocrReview.missingTitle}>
        <p>{t.ocrReview.missingBody}</p>
        <Link href="/full-content" className="font-medium text-[var(--color-brand)] underline underline-offset-4">
          {t.ocrReview.backToUpload}
        </Link>
      </Notice>
    );
  }

  const { extraction, reviewedText } = ocr;
  const prepared = state.prepared?.kind === "full_content_reviewed_ocr_text" ? state.prepared : null;
  const edited = reviewedText !== extraction.raw_text;

  const imageCard = (
    <Card as="section" className="space-y-3 lg:sticky lg:top-6 lg:col-start-2 lg:row-start-1">
      <h2 className="font-bold">{t.ocrReview.imageHeading}</h2>
      {previewUrl ? (
        // eslint-disable-next-line @next/next/no-img-element -- local blob preview
        <img
          src={previewUrl}
          alt={t.fullContent.imagePreviewAlt}
          className="max-h-56 w-full rounded-xl border border-[var(--color-border)] object-contain lg:max-h-[28rem]"
        />
      ) : (
        <ImageIcon className="size-12 text-[var(--color-muted)]" />
      )}
      <p className="break-all text-sm text-[var(--color-muted)]" dir="auto">
        {ocr.image.name}
      </p>
      <Button variant="secondary" className="w-full" onClick={replaceImage}>
        {t.ocrReview.replaceImage}
      </Button>
    </Card>
  );

  if (extraction.status === "no_text_found") {
    return (
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        {imageCard}
        <Notice tone="warning" role="alert" title={t.ocrReview.noTextTitle} className="lg:col-start-1 lg:row-start-1">
          <p>{t.ocrReview.noTextBody}</p>
          {extraction.warnings.some((w) => w.code === "low_resolution_image") ? (
            <p className="text-sm">{t.ocrReview.lowResolution}</p>
          ) : null}
          <div className="flex flex-wrap gap-2 pt-1">
            <Button onClick={replaceImage}>{t.ocrReview.uploadAnother}</Button>
            <Button variant="secondary" onClick={typeManually}>
              {t.ocrReview.typeManually}
            </Button>
          </div>
        </Notice>
      </div>
    );
  }

  if (prepared) {
    return (
      <Notice tone="success" role="status" title={t.ocrReview.preparedTitle}>
        <p>{t.ocrReview.preparedBody}</p>
        <blockquote className="max-h-64 overflow-auto whitespace-pre-wrap rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
          {prepared.extractionInput.text}
        </blockquote>
        <p className="text-sm text-[var(--color-muted)]">{t.common.nextStepPending}</p>
        <Button variant="secondary" onClick={() => dispatch({ type: "prepared/clear" })}>
          {t.common.edit}
        </Button>
      </Notice>
    );
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (isBlank(reviewedText)) {
      setError(t.ocrReview.errorEmpty);
      fieldRef.current?.focus();
      return;
    }
    setError(null);
    dispatch({ type: "prepared/set", submission: prepareReviewedOcrText(ocr) });
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      {imageCard}
      <div className="space-y-5 lg:col-start-1 lg:row-start-1">
        <OcrStatusNotice extraction={extraction} onReplace={replaceImage} />
        <Card>
          <form noValidate onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor={ids.field} className="block text-lg font-bold">
                {t.ocrReview.textLabel}
              </label>
              <p id={ids.hint} className="text-sm text-[var(--color-muted)]">
                {t.ocrReview.textHint}
              </p>
              <textarea
                id={ids.field}
                ref={fieldRef}
                name="reviewed-text"
                rows={12}
                dir={reviewedText ? "auto" : "rtl"}
                value={reviewedText}
                onChange={(e) => {
                  dispatch({ type: "ocr/editReviewed", text: e.target.value });
                  if (error) setError(null);
                }}
                aria-invalid={error ? true : undefined}
                aria-describedby={[ids.hint, ids.count, edited ? ids.edited : null, error ? ids.error : null]
                  .filter(Boolean)
                  .join(" ")}
                className="block min-h-72 w-full resize-y rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-4 text-lg leading-8 focus:border-[var(--color-brand)] aria-[invalid=true]:border-[var(--color-danger)]"
              />
              <div className="flex flex-wrap items-start justify-between gap-2">
                <FieldError id={ids.error} message={error} />
                <p id={ids.count} className="text-sm text-[var(--color-muted)]">
                  {t.common.charCount(formatNumber(reviewedText.length))}
                </p>
              </div>
              {edited ? (
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <p id={ids.edited} className="font-medium">
                    <span aria-hidden="true">✎ </span>
                    {t.ocrReview.edited}
                  </p>
                  <Button variant="ghost" className="min-h-9 px-3 py-1 text-sm" onClick={() => dispatch({ type: "ocr/restoreRaw" })}>
                    {t.ocrReview.restoreRaw}
                  </Button>
                </div>
              ) : null}
            </div>
            <Button type="submit" className="w-full sm:w-auto">
              {t.ocrReview.confirm}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
