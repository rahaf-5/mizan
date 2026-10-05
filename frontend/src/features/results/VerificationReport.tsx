"use client";

import { Card } from "@/components/Card";
import { getDictionary } from "@/i18n";
import type { ConfirmedClaim } from "@/lib/claims/types";
import { formatNumber } from "@/lib/format";
import { countBySection, runSection, SECTION_ORDER } from "@/lib/verify/report";
import { ClaimResultCard } from "./ClaimResultCard";
import { useVerificationRuns } from "./useVerificationRuns";

const t = getDictionary().results;

/**
 * Interactive verification report (spec §12, §15, §18): real per-claim progress, report
 * summary with counts, result groups, claim cards. Only CONFIRMED claims are verified.
 */
export function VerificationReport({ runKey, claims }: { runKey: string; claims: ConfirmedClaim[] }) {
  const { runs, retry, adopt } = useVerificationRuns(runKey, claims);
  if (runs.length === 0) return null;

  const total = runs.length;
  const pending = runs.filter((r) => r.state === "waiting" || r.state === "running");
  const currentIndex = runs.findIndex((r) => r.state === "running");
  const counts = countBySection(runs);
  const finished = total - pending.length;

  return (
    <div className="space-y-6">
      {pending.length ? (
        <Card as="section">
          <div role="status" aria-live="polite" className="space-y-3">
            <h2 className="text-lg font-bold">{t.progressTitle}</h2>
            <p>{t.progress(formatNumber(Math.max(currentIndex, finished) + 1), formatNumber(total))}</p>
            <p className="text-sm text-[var(--color-muted)]">{t.progressNote}</p>
            {total > 1 ? (
              <ol className="space-y-1 text-sm">
                {runs.map((r, i) => (
                  <li key={i} className="flex gap-2" data-state={r.state}>
                    <span className="min-w-20 font-medium">{t.runState[r.state]}</span>
                    <span dir="auto" className="truncate">{r.claim.confirmed_claim_text}</span>
                  </li>
                ))}
              </ol>
            ) : null}
          </div>
        </Card>
      ) : null}

      {finished > 0 ? (
        <Card as="section">
          <h2 className="text-lg font-bold">{t.summaryTitle}</h2>
          <p className="pt-1 text-sm text-[var(--color-muted)]">{t.summaryTotal(formatNumber(total))}</p>
          <ul className="grid gap-2 pt-3 sm:grid-cols-2">
            {SECTION_ORDER.filter((s) => counts[s] > 0).map((s) => (
              <li key={s} className="flex items-center justify-between rounded-xl border border-[var(--color-border)] px-3 py-2" data-section={s}>
                <span>{t.sections[s]}</span>
                <span className="font-bold">{formatNumber(counts[s])}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {SECTION_ORDER.filter((s) => counts[s] > 0).map((s) => (
        <section key={s} aria-labelledby={`section-${s}`} className="space-y-3">
          <h2 id={`section-${s}`} className="text-xl font-bold">
            {t.sections[s]} ({formatNumber(counts[s])})
          </h2>
          <ul className="space-y-4">
            {runs.map((r, i) =>
              runSection(r) === s ? (
                <ClaimResultCard key={i} run={r} index={i} onRetry={() => retry(i)} onAdopt={(alt) => adopt(i, alt)} />
              ) : null,
            )}
          </ul>
        </section>
      ))}
    </div>
  );
}
