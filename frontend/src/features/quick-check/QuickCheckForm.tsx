"use client";

import { useRouter } from "next/navigation";
import { useId, useRef, useState, type FormEvent } from "react";
import { Card } from "@/components/Card";
import { ForwardArrowIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";
import { FieldError } from "@/components/ui/FieldError";
import { Notice } from "@/components/ui/Notice";
import { getDictionary } from "@/i18n";
import { confirmClaims } from "@/lib/claims/client";
import { newClaimId } from "@/lib/claims/review";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { prepareQuickCheckClaim } from "@/lib/input/submission";
import { validateQuickCheck } from "@/lib/input/validation";
import { VerificationReport } from "@/features/results/VerificationReport";

const t = getDictionary();

/**
 * Quick Check (spec §2A): the user writes ONE claim (editable), submitting is the explicit
 * confirmation — it goes through the backend confirmation gate — and only the confirmed claim
 * is verified against the real backend.
 */
export function QuickCheckForm() {
  const router = useRouter();
  const { state, dispatch } = useInputSession();
  const [error, setError] = useState<string | null>(null);
  const [suggestFull, setSuggestFull] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const ids = { field: useId(), hint: useId(), error: useId(), suggest: useId() };

  const prepared = state.prepared?.kind === "quick_check_claim" ? state.prepared : null;

  const prepare = async () => {
    setSuggestFull(false);
    setConfirming(true);
    const text = state.quickCheckText;
    const res = await confirmClaims({
      explicit_user_confirmation: true,
      claims: [
        {
          claim_id: newClaimId(),
          origin: "manual",
          original_text: text,
          extracted_claim_text: null,
          text,
          selected: true,
          extraction_status: null,
          provided_evidence: null,
          provided_reference: null,
        },
      ],
    });
    setConfirming(false);
    if (res.kind === "confirmed" && res.result.confirmedClaims.length === 1) {
      dispatch({ type: "prepared/set", submission: prepareQuickCheckClaim(text, res.result.confirmedClaims[0]) });
    } else if (res.kind === "input_error" && res.code === "empty_claim_text") {
      setError(t.quickCheck.errorEmpty);
    } else {
      setError(t.quickCheck.confirmFailed);
    }
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
    void prepare();
  };

  const goToFullContent = () => {
    dispatch({ type: "quickCheck/moveToFullContent" });
    router.push("/full-content");
  };

  if (prepared) {
    const claim = prepared.confirmedClaim;
    return (
      <div className="space-y-5">
        <VerificationReport runKey={`quick:${claim.claim_id}`} claims={[claim]} />
        <Button
          variant="secondary"
          onClick={() => {
            dispatch({ type: "verification/clear" });
            dispatch({ type: "prepared/clear" });
          }}
        >
          {t.quickCheck.editClaim}
        </Button>
      </div>
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
              <Button variant="secondary" onClick={() => void prepare()}>
                {t.quickCheck.multiContinue}
              </Button>
            </div>
          </Notice>
        ) : null}

        {/* While the multi-claim guidance is shown, its two choices are the actions. */}
        {suggestFull ? null : (
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" className="w-full sm:w-auto" disabled={confirming}>
              {t.quickCheck.submit}
            </Button>
            <p role="status" className="text-[var(--color-muted)]">
              {confirming ? t.quickCheck.confirming : null}
            </p>
          </div>
        )}
      </form>
    </Card>
  );
}
