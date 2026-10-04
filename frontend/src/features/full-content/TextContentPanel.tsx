"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useRef, useState, type FormEvent } from "react";
import { Card } from "@/components/Card";
import { ForwardArrowIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";
import { FieldError } from "@/components/ui/FieldError";
import { Notice } from "@/components/ui/Notice";
import { getDictionary } from "@/i18n";
import { extractClaims } from "@/lib/claims/client";
import { fromExtracted } from "@/lib/claims/review";
import { CLAIM_EXTRACTION_MAX_INPUT_CHARS } from "@/lib/claims/types";
import type { ExtractCallResult } from "@/lib/claims/types";
import { formatNumber } from "@/lib/format";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { validateContentText } from "@/lib/input/validation";

const t = getDictionary();
const MAX = formatNumber(CLAIM_EXTRACTION_MAX_INPUT_CHARS);

type Problem = { message: string; retryable: boolean; manual: boolean } | null;

/** Technical failures are never shown as "no claims". */
function problemFor(r: Exclude<ExtractCallResult, { kind: "extraction" }>): Problem {
  if (r.kind === "network_error") return { message: t.fullContent.extractNetwork, retryable: true, manual: false };
  if (r.kind === "input_error") {
    return r.code === "text_too_long"
      ? { message: t.fullContent.textErrorTooLong(MAX), retryable: false, manual: false }
      : { message: t.fullContent.textErrorEmpty, retryable: false, manual: false };
  }
  switch (r.code) {
    case "llm_rate_limited":
      return { message: t.fullContent.extractRateLimited, retryable: true, manual: false };
    case "llm_not_configured":
    case "llm_auth_failed":
      return { message: t.fullContent.extractNotConfigured, retryable: false, manual: true };
    case "llm_content_blocked":
      return { message: t.fullContent.extractBlocked, retryable: false, manual: true };
    default:
      return { message: t.fullContent.extractFailedTechnical, retryable: r.retryable, manual: false };
  }
}

/**
 * Full Content text → Claim Extraction (backend, LLM-assisted) → Claim Review.
 * Extraction is not verification; nothing is verified from here.
 */
export function TextContentPanel() {
  const router = useRouter();
  const { state, dispatch } = useInputSession();
  const [error, setError] = useState<string | null>(null);
  const [problem, setProblem] = useState<Problem>(null);
  const [extracting, setExtracting] = useState(false);
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const ids = { field: useId(), hint: useId(), error: useId(), count: useId(), status: useId() };
  const tooLong = state.contentText.length > CLAIM_EXTRACTION_MAX_INPUT_CHARS;
  const reviewMatches = state.review !== null && state.review.sourceText === state.contentText;

  const runExtraction = async () => {
    const text = state.contentText;
    setProblem(null);
    setExtracting(true);
    const result = await extractClaims(text);
    setExtracting(false);
    if (result.kind === "extraction") {
      dispatch({ type: "review/start", sourceText: text, claims: fromExtracted(result.claims) });
      router.push("/full-content/claims");
      return;
    }
    if (result.kind === "input_error") {
      setError(problemFor(result)?.message ?? null);
      return;
    }
    setProblem(problemFor(result));
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (extracting) return;
    if (validateContentText(state.contentText).status === "empty") {
      setError(t.fullContent.textErrorEmpty);
      fieldRef.current?.focus();
      return;
    }
    if (tooLong) {
      setError(t.fullContent.textErrorTooLong(MAX));
      fieldRef.current?.focus();
      return;
    }
    setError(null);
    void runExtraction();
  };

  const addManually = () => {
    dispatch({ type: "review/start", sourceText: state.contentText, claims: [] });
    router.push("/full-content/claims");
  };

  return (
    <Card>
      <form noValidate onSubmit={onSubmit} className="space-y-4" aria-busy={extracting || undefined}>
        <div className="space-y-2">
          <label htmlFor={ids.field} className="block text-lg font-bold">
            {t.fullContent.textLabel}
          </label>
          <p id={ids.hint} className="text-sm text-[var(--color-muted)]">
            {t.fullContent.textHint}
          </p>
          <textarea
            id={ids.field}
            ref={fieldRef}
            name="content"
            rows={10}
            dir={state.contentText ? "auto" : "rtl"}
            value={state.contentText}
            readOnly={extracting}
            onChange={(e) => {
              dispatch({ type: "content/setText", text: e.target.value });
              if (error) setError(null);
            }}
            placeholder={t.fullContent.textPlaceholder}
            aria-invalid={error ? true : undefined}
            aria-describedby={[ids.hint, ids.count, error ? ids.error : null].filter(Boolean).join(" ")}
            className="block min-h-56 w-full resize-y rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-4 text-lg leading-8 focus:border-[var(--color-brand)] aria-[invalid=true]:border-[var(--color-danger)]"
          />
          <div className="flex flex-wrap items-start justify-between gap-2">
            <FieldError id={ids.error} message={error} />
            <p
              id={ids.count}
              className={`text-sm ${tooLong ? "font-medium text-[var(--color-danger)]" : "text-[var(--color-muted)]"}`}
            >
              {t.fullContent.charCountOf(formatNumber(state.contentText.length), MAX)}
            </p>
          </div>
        </div>

        {problem ? (
          <Notice tone="warning" role="alert" title={t.fullContent.extractFailedTitle}>
            <p>{problem.message}</p>
            <div className="flex flex-wrap gap-2">
              {problem.retryable ? (
                <Button variant="secondary" onClick={() => void runExtraction()} disabled={extracting}>
                  {t.fullContent.retry}
                </Button>
              ) : null}
              {problem.manual ? (
                <Button variant="secondary" onClick={addManually}>
                  {t.fullContent.addManually}
                </Button>
              ) : null}
            </div>
          </Notice>
        ) : null}

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" className="w-full sm:w-auto" disabled={extracting}>
            {t.fullContent.textSubmit}
          </Button>
          <p id={ids.status} role="status" className="flex items-center gap-2 text-[var(--color-muted)]">
            {extracting ? (
              <>
                <span
                  aria-hidden="true"
                  className="size-4 animate-spin rounded-full border-2 border-[var(--color-brand)] border-t-transparent"
                />
                {t.fullContent.extracting}
              </>
            ) : null}
          </p>
          {reviewMatches && !extracting ? (
            <Link
              href="/full-content/claims"
              className="inline-flex items-center gap-1.5 font-medium text-[var(--color-brand)] underline-offset-4 hover:underline"
            >
              {t.fullContent.continueReview}
              <ForwardArrowIcon className="size-4" />
            </Link>
          ) : null}
        </div>
      </form>
    </Card>
  );
}
