"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { BackArrowIcon } from "@/components/icons";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/Notice";
import { getDictionary } from "@/i18n";
import { confirmClaims } from "@/lib/claims/client";
import { buildConfirmPayload, manualClaim, selectedClaims } from "@/lib/claims/review";
import { formatNumber } from "@/lib/format";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { AddClaimForm } from "./AddClaimForm";
import { ClaimCard } from "./ClaimCard";

const t = getDictionary();

/**
 * Claim Review (spec §3, §18). The user reviews, edits, deletes, (de)selects and adds
 * claims, then EXPLICITLY confirms. Confirmation goes through the backend domain gate; only the
 * returned confirmed claims (with the user's edits) are verified, on the results page.
 */
export function ClaimReview() {
  const router = useRouter();
  const { state, dispatch } = useInputSession();
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const ids = { counts: useId(), error: useId(), list: useId() };
  const review = state.review;

  if (!review) {
    return (
      <Notice tone="info" title={t.claimReview.missingTitle}>
        <p>{t.claimReview.missingBody}</p>
        <Link href="/full-content" className="font-medium text-[var(--color-brand)] underline underline-offset-4">
          {t.claimReview.goToFullContent}
        </Link>
      </Notice>
    );
  }

  const backLink = (
    <Link
      href="/full-content"
      className="inline-flex min-h-11 items-center gap-1.5 rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-card)] px-5 py-2.5 font-medium hover:border-[var(--color-brand)]"
    >
      <BackArrowIcon className="size-4" />
      {t.claimReview.backToText}
    </Link>
  );

  if (state.confirmation) {
    const confirmed = state.confirmation.confirmedClaims;
    return (
      <Notice tone="success" role="status" title={t.claimReview.confirmedTitle(formatNumber(confirmed.length))}>
        <p>{t.claimReview.confirmedBody}</p>
        <ol className="list-decimal space-y-1 ps-6">
          {confirmed.map((c) => (
            <li key={c.claim_id} dir="auto">
              {c.confirmed_claim_text}
            </li>
          ))}
        </ol>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/full-content/results"
            className="inline-flex min-h-11 items-center rounded-xl bg-[var(--color-brand)] px-5 py-2.5 font-medium text-[var(--color-on-brand)]"
          >
            {t.claimReview.viewResults}
          </Link>
          <Button variant="secondary" onClick={() => dispatch({ type: "confirmation/clear" })}>
            {t.claimReview.backToReview}
          </Button>
        </div>
      </Notice>
    );
  }

  const claims = review.claims;
  const selected = selectedClaims(review).length;

  const onConfirm = async () => {
    setFailure(null);
    if (selected === 0) {
      setError(t.claimReview.errorNoneSelected);
      return;
    }
    setError(null);
    setConfirming(true);
    const result = await confirmClaims(buildConfirmPayload(review));
    setConfirming(false);
    if (result.kind === "confirmed") {
      dispatch({ type: "confirmation/set", result: result.result });
      router.push("/full-content/results");
    } else if (result.kind === "input_error" && result.code === "no_claims_selected") {
      setError(t.claimReview.errorNoneSelected);
    } else if (result.kind === "input_error" && result.code === "empty_claim_text") {
      setError(t.claimReview.errorEmptyClaim);
    } else {
      setFailure(t.claimReview.confirmFailed);
    }
  };

  return (
    <div className="space-y-5">
      <p className="text-sm text-[var(--color-muted)]">{t.claimReview.gateNote}</p>

      {claims.length === 0 ? (
        <Notice tone="info" title={t.claimReview.emptyTitle}>
          <p>{t.claimReview.emptyBody}</p>
          <div className="pt-1">{backLink}</div>
        </Notice>
      ) : (
        <section aria-labelledby={ids.list} className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id={ids.list} className="text-lg font-bold">
              {t.claimReview.listLabel}
            </h2>
            <p id={ids.counts} aria-live="polite" className="text-sm font-medium">
              {t.claimReview.counts(formatNumber(claims.length), formatNumber(selected))}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" className="min-h-9 px-3 py-1 text-sm" onClick={() => dispatch({ type: "review/setAll", selected: true })}>
              {t.claimReview.selectAll}
            </Button>
            <Button variant="ghost" className="min-h-9 px-3 py-1 text-sm" onClick={() => dispatch({ type: "review/setAll", selected: false })}>
              {t.claimReview.selectNone}
            </Button>
          </div>
          <ul className="space-y-3">
            {claims.map((c, i) => (
              <ClaimCard
                key={c.id}
                claim={c}
                index={i}
                onToggle={() => {
                  setError(null);
                  dispatch({ type: "review/toggle", id: c.id });
                }}
                onEdit={(text) => dispatch({ type: "review/edit", id: c.id, text })}
                onDelete={() => dispatch({ type: "review/delete", id: c.id })}
              />
            ))}
          </ul>
        </section>
      )}

      <AddClaimForm
        count={claims.length}
        onAdd={(text) => {
          setError(null);
          dispatch({ type: "review/add", claim: manualClaim(text) });
        }}
      />

      {error ? (
        <Notice id={ids.error} tone="warning" role="alert" title={error} />
      ) : null}
      {failure ? (
        <Notice tone="warning" role="alert" title={failure} />
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => void onConfirm()} disabled={confirming} aria-describedby={error ? ids.error : ids.counts}>
          {t.claimReview.confirm}
        </Button>
        {claims.length > 0 ? backLink : null}
        <p role="status" className="text-[var(--color-muted)]">
          {confirming ? t.claimReview.confirming : null}
        </p>
      </div>
    </div>
  );
}
