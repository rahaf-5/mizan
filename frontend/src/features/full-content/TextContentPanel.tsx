"use client";

import { useId, useRef, useState, type FormEvent } from "react";
import { Card } from "@/components/Card";
import { Button } from "@/components/ui/Button";
import { FieldError } from "@/components/ui/FieldError";
import { Notice } from "@/components/ui/Notice";
import { getDictionary } from "@/i18n";
import { formatNumber } from "@/lib/format";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { prepareContentText } from "@/lib/input/submission";
import { validateContentText } from "@/lib/input/validation";

const t = getDictionary();

/** Text mode: prepares content for Claim Extraction (Task 4). No extraction here. */
export function TextContentPanel() {
  const { state, dispatch } = useInputSession();
  const [error, setError] = useState<string | null>(null);
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const ids = { field: useId(), hint: useId(), error: useId(), count: useId() };
  const prepared = state.prepared?.kind === "full_content_text" ? state.prepared : null;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (validateContentText(state.contentText).status === "empty") {
      setError(t.fullContent.textErrorEmpty);
      fieldRef.current?.focus();
      return;
    }
    setError(null);
    dispatch({ type: "prepared/set", submission: prepareContentText(state.contentText) });
  };

  if (prepared) {
    return (
      <Notice tone="success" role="status" title={t.fullContent.textPreparedTitle}>
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

  return (
    <Card>
      <form noValidate onSubmit={onSubmit} className="space-y-4">
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
            <p id={ids.count} className="text-sm text-[var(--color-muted)]">
              {t.common.charCount(formatNumber(state.contentText.length))}
            </p>
          </div>
        </div>
        <Button type="submit" className="w-full sm:w-auto">
          {t.fullContent.textSubmit}
        </Button>
      </form>
    </Card>
  );
}
