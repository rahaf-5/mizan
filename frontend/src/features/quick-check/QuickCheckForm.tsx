"use client";

import { useRouter } from "next/navigation";
import { useId, useRef, useState, type FormEvent } from "react";
import { Card } from "@/components/Card";
import { ForwardArrowIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";
import { FieldError } from "@/components/ui/FieldError";
import { Notice } from "@/components/ui/Notice";
import { getDictionary } from "@/i18n";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { prepareQuickCheckClaim } from "@/lib/input/submission";
import { validateQuickCheck } from "@/lib/input/validation";

const t = getDictionary();

/**
 * Quick Check input. Submitting PREPARES the claim for the later
 * review/confirmation step (Task 4). It never runs verification.
 */
export function QuickCheckForm() {
  const router = useRouter();
  const { state, dispatch } = useInputSession();
  const [error, setError] = useState<string | null>(null);
  const [suggestFull, setSuggestFull] = useState(false);
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const ids = { field: useId(), hint: useId(), error: useId(), suggest: useId() };

  const prepared = state.prepared?.kind === "quick_check_claim" ? state.prepared : null;

  const prepare = () => {
    dispatch({ type: "prepared/set", submission: prepareQuickCheckClaim(state.quickCheckText) });
    setSuggestFull(false);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const result = validateQuickCheck(state.quickCheckText);
    if (result.status === "empty") {
      setError(t.quickCheck.errorEmpty);
      fieldRef.current?.focus();
      return;
    }
    setError(null);
    if (result.status === "multiple_claims_suspected") {
      setSuggestFull(true);
      return;
    }
    prepare();
  };

  const goToFullContent = () => {
    dispatch({ type: "quickCheck/moveToFullContent" });
    router.push("/full-content");
  };

  if (prepared) {
    return (
      <Notice tone="success" role="status" title={t.quickCheck.preparedTitle}>
        <p className="text-sm text-[var(--color-muted)]">{t.quickCheck.preparedClaimLabel}</p>
        <blockquote className="whitespace-pre-wrap rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-lg">
          {prepared.extractionInput.text}
        </blockquote>
        <p className="text-sm text-[var(--color-muted)]">{t.common.nextStepPending}</p>
        <Button variant="secondary" onClick={() => dispatch({ type: "prepared/clear" })}>
          {t.common.edit}
        </Button>
      </Notice>
    );
  }

  const describedBy = [ids.hint, error ? ids.error : null, suggestFull ? ids.suggest : null]
    .filter(Boolean)
    .join(" ");

  return (
    <Card>
      <form noValidate onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor={ids.field} className="block text-lg font-bold">
            {t.quickCheck.fieldLabel}
          </label>
          <p id={ids.hint} className="text-sm text-[var(--color-muted)]">
            {t.quickCheck.hint}
          </p>
          <textarea
            id={ids.field}
            ref={fieldRef}
            name="claim"
            rows={4}
            dir={state.quickCheckText ? "auto" : "rtl"}
            value={state.quickCheckText}
            onChange={(e) => {
              dispatch({ type: "quickCheck/setText", text: e.target.value });
              if (error) setError(null);
              if (suggestFull) setSuggestFull(false);
            }}
            placeholder={t.quickCheck.placeholder}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className="block w-full resize-y rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-4 text-lg leading-8 focus:border-[var(--color-brand)] aria-[invalid=true]:border-[var(--color-danger)]"
          />
          <FieldError id={ids.error} message={error} />
        </div>

        {suggestFull ? (
          <Notice id={ids.suggest} tone="info" role="status" title={t.quickCheck.multiTitle}>
            <p>{t.quickCheck.multiBody}</p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button onClick={goToFullContent}>
                {t.quickCheck.multiGoFull}
                <ForwardArrowIcon className="size-4" />
              </Button>
              <Button variant="secondary" onClick={prepare}>
                {t.quickCheck.multiContinue}
              </Button>
            </div>
          </Notice>
        ) : null}

        {/* While the multi-claim guidance is shown, its two choices are the actions. */}
        {suggestFull ? null : (
          <Button type="submit" className="w-full sm:w-auto">
            {t.quickCheck.submit}
          </Button>
        )}
      </form>
    </Card>
  );
}
