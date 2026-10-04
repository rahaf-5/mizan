"use client";

import { useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { FieldError } from "@/components/ui/FieldError";
import { getDictionary } from "@/i18n";
import { isEdited } from "@/lib/claims/review";
import { CLAIM_MAX_CHARS, type ReviewClaim } from "@/lib/claims/types";
import { formatNumber } from "@/lib/format";

const t = getDictionary();

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-0.5 text-xs font-medium">
      {children}
    </span>
  );
}

/** One claim on Claim Review: select, edit, delete. Badges are text (never colour-only). */
export function ClaimCard({
  claim,
  index,
  onToggle,
  onEdit,
  onDelete,
}: {
  claim: ReviewClaim;
  index: number;
  onToggle: () => void;
  onEdit: (text: string) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(claim.text);
  const [error, setError] = useState<string | null>(null);
  const editRef = useRef<HTMLTextAreaElement>(null);
  const ids = { text: useId(), edit: useId(), error: useId() };
  const n = formatNumber(index + 1);

  const startEdit = () => {
    setDraft(claim.text);
    setError(null);
    setEditing(true);
    setTimeout(() => editRef.current?.focus(), 0);
  };

  const save = () => {
    if (!draft.trim()) {
      setError(t.claimReview.errorEmptyClaim);
      editRef.current?.focus();
      return;
    }
    if (draft.length > CLAIM_MAX_CHARS) {
      setError(t.claimReview.errorClaimTooLong(formatNumber(CLAIM_MAX_CHARS)));
      return;
    }
    onEdit(draft);
    setEditing(false);
  };

  return (
    <li>
      <article
        aria-label={t.claimReview.claimNumber(n)}
        data-selected={claim.selected || undefined}
        className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 shadow-sm transition-colors data-[selected]:border-[var(--color-brand)] sm:p-5"
      >
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={claim.selected}
            onChange={onToggle}
            aria-label={t.claimReview.selectClaim(n)}
            aria-describedby={ids.text}
            className="mt-1.5 size-5 shrink-0 accent-[var(--color-brand)]"
          />
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-sm font-bold text-[var(--color-muted)]">{t.claimReview.claimNumber(n)}</span>
              {claim.origin === "manual" ? <Badge>{t.claimReview.badgeManual}</Badge> : null}
              {isEdited(claim) ? <Badge>✎ {t.claimReview.badgeEdited}</Badge> : null}
              {claim.extractionStatus === "ambiguous" ? <Badge>? {t.claimReview.badgeAmbiguous}</Badge> : null}
              {claim.extractionStatus === "incomplete" ? <Badge>… {t.claimReview.badgeIncomplete}</Badge> : null}
            </div>

            {editing ? (
              <div className="space-y-2">
                <label htmlFor={ids.edit} className="sr-only">
                  {t.claimReview.editLabel(n)}
                </label>
                <textarea
                  id={ids.edit}
                  ref={editRef}
                  rows={3}
                  dir="auto"
                  value={draft}
                  onChange={(e) => {
                    setDraft(e.target.value);
                    if (error) setError(null);
                  }}
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? ids.error : undefined}
                  className="block w-full resize-y rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-3 text-lg leading-8 focus:border-[var(--color-brand)]"
                />
                <FieldError id={ids.error} message={error} />
                <div className="flex flex-wrap gap-2">
                  <Button onClick={save}>{t.claimReview.save}</Button>
                  <Button variant="secondary" onClick={() => setEditing(false)}>
                    {t.claimReview.cancel}
                  </Button>
                </div>
              </div>
            ) : (
              <p id={ids.text} dir="auto" className="whitespace-pre-wrap text-lg leading-8">
                {claim.text}
              </p>
            )}

            {claim.origin === "extracted" && claim.originalText && !editing ? (
              <p className="text-sm text-[var(--color-muted)]">
                {t.claimReview.originalExcerpt} <span dir="auto">«{claim.originalText}»</span>
              </p>
            ) : null}
            {claim.providedEvidence ? (
              <p className="text-sm">
                <span className="font-medium">{t.claimReview.providedEvidence}</span>{" "}
                <span dir="auto">{claim.providedEvidence.provided_evidence_text}</span>
              </p>
            ) : null}
            {claim.providedReference ? (
              <p className="text-sm">
                <span className="font-medium">{t.claimReview.providedReference}</span>{" "}
                <span dir="auto">{claim.providedReference}</span>
              </p>
            ) : null}

            {!editing ? (
              <div className="flex flex-wrap gap-2 pt-1">
                <Button variant="ghost" className="min-h-9 px-3 py-1 text-sm" onClick={startEdit} aria-label={`${t.claimReview.edit} — ${t.claimReview.claimNumber(n)}`}>
                  {t.claimReview.edit}
                </Button>
                <Button variant="ghost" className="min-h-9 px-3 py-1 text-sm" onClick={onDelete} aria-label={`${t.claimReview.delete} — ${t.claimReview.claimNumber(n)}`}>
                  {t.claimReview.delete}
                </Button>
              </div>
            ) : null}
          </div>
        </div>
      </article>
    </li>
  );
}
