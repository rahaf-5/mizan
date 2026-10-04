"use client";

import { useId, useState, type FormEvent } from "react";
import { Card } from "@/components/Card";
import { Button } from "@/components/ui/Button";
import { FieldError } from "@/components/ui/FieldError";
import { getDictionary } from "@/i18n";
import { CLAIM_MAX_CHARS, MAX_REVIEW_CLAIMS } from "@/lib/claims/types";
import { formatNumber } from "@/lib/format";

const t = getDictionary();

/** Manually add a claim; it goes through the same confirmation path as extracted claims. */
export function AddClaimForm({ onAdd, count }: { onAdd: (text: string) => void; count: number }) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const ids = { field: useId(), error: useId(), title: useId() };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return setError(t.claimReview.errorEmptyClaim);
    if (text.length > CLAIM_MAX_CHARS) return setError(t.claimReview.errorClaimTooLong(formatNumber(CLAIM_MAX_CHARS)));
    if (count >= MAX_REVIEW_CLAIMS) return setError(t.claimReview.errorTooMany(formatNumber(MAX_REVIEW_CLAIMS)));
    onAdd(text);
    setText("");
    setError(null);
  };

  return (
    <Card as="section" className="space-y-3">
      <h2 id={ids.title} className="text-lg font-bold">
        {t.claimReview.addTitle}
      </h2>
      <form noValidate onSubmit={onSubmit} aria-labelledby={ids.title} className="space-y-2">
        <label htmlFor={ids.field} className="block text-sm font-medium">
          {t.claimReview.addLabel}
        </label>
        <textarea
          id={ids.field}
          rows={2}
          dir={text ? "auto" : "rtl"}
          value={text}
          placeholder={t.claimReview.addPlaceholder}
          onChange={(e) => {
            setText(e.target.value);
            if (error) setError(null);
          }}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? ids.error : undefined}
          className="block w-full resize-y rounded-xl border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-3 text-lg leading-8 focus:border-[var(--color-brand)]"
        />
        <FieldError id={ids.error} message={error} />
        <Button type="submit" variant="secondary">
          {t.claimReview.addSubmit}
        </Button>
      </form>
    </Card>
  );
}
