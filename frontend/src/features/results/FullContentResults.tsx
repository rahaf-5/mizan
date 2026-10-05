"use client";

import Link from "next/link";
import { Notice } from "@/components/ui/Notice";
import { getDictionary } from "@/i18n";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { VerificationReport } from "./VerificationReport";

const t = getDictionary().results;
const linkCls = "font-medium text-[var(--color-brand)] underline underline-offset-4";

/** Full Content report: verifies ONLY the claims the user explicitly confirmed. */
export function FullContentResults() {
  const { state } = useInputSession();
  const confirmed = state.confirmation?.confirmedClaims ?? [];
  if (confirmed.length === 0) {
    return (
      <Notice tone="info" title={t.noClaims}>
        <Link href="/full-content" className={linkCls}>
          {t.goToFullContent}
        </Link>
      </Notice>
    );
  }
  const key = `full:${confirmed.map((c) => `${c.claim_id}=${c.confirmed_claim_text}`).join("|")}`;
  return (
    <div className="space-y-6">
      <VerificationReport runKey={key} claims={confirmed} />
      <div className="flex flex-wrap gap-4">
        <Link href="/full-content/claims" className={linkCls}>
          {t.backToReview}
        </Link>
        <Link href="/full-content" className={linkCls}>
          {t.restart}
        </Link>
      </div>
    </div>
  );
}
