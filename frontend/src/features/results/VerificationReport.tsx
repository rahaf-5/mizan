"use client";

import { Card } from "@/components/Card";
import { getDictionary } from "@/i18n";
import type { ConfirmedClaim } from "@/lib/claims/types";
import { formatNumber } from "@/lib/format";
import { countByDecision, DECISION_ORDER, runDecision } from "@/lib/verify/report";
import { ClaimResultCard } from "./ClaimResultCard";
import { useVerificationRuns } from "./useVerificationRuns";

const t = getDictionary().results;

/**
 * Verification results. Only CONFIRMED claims are verified, one request per claim, so the
 * progress shown is real. `single` (Quick Check): one result card, no dashboard.
 * `report` (Full Content): a short summary by decision, then claims grouped by decision —
 * every card still shows its exact status.
 */
export function VerificationReport({
  runKey,
  claims,
  variant = "report",
}: {
  runKey: string;
  claims: ConfirmedClaim[];
  variant?: "single" | "report";
}) {
  const { runs, retry, adopt } = useVerificationRuns(runKey, claims);
  if (runs.length === 0) return null;

  const total = runs.length;
  const pending = runs.filter((r) => r.state === "waiting" || r.state === "running");
  const currentIndex = runs.findIndex((r) => r.state === "running");
  const finished = total - pending.length;
  const counts = countByDecision(runs);

  const card = (i: number) => (
    <ClaimResultCard
      key={i}
      run={runs[i]}
      index={i}
      showIndex={variant === "report"}
      onRetry={() => retry(i)}
      onAdopt={(alt) => adopt(i, alt)}
    />
  );

  const progress = pending.length ? (
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
  ) : null;

  if (variant === "single") {
    return (
      <div className="space-y-6">
        {progress}
        {finished > 0 ? <ul className="space-y-4">{runs.map((r, i) => (r.state === "done" || r.state === "failed" ? card(i) : null))}</ul> : null}
      </div>
    );
  }

  const tiles = DECISION_ORDER.filter((d) => d !== "unverifiable" || counts.unverifiable > 0);
  return (
    <div className="space-y-8">
      {progress}

      {finished > 0 ? (
        <Card as="section">
          <h2 className="text-lg font-bold">{t.summaryTitle}</h2>
          <p className="pt-1 text-sm text-[var(--color-muted)]">{t.summaryTotal(formatNumber(total))}</p>
          <ul className="grid grid-cols-2 gap-3 pt-4 sm:grid-cols-4">
            {tiles.map((d) => (
              <li key={d} data-decision={d} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                <p className="text-2xl font-bold">{formatNumber(counts[d])}</p>
                <p className="text-sm text-[var(--color-muted)]">{t.decisions[d]}</p>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {DECISION_ORDER.filter((d) => counts[d] > 0).map((d) => (
        <section key={d} aria-labelledby={`decision-${d}`} className="space-y-3">
          <h2 id={`decision-${d}`} className="text-xl font-bold">
            {t.decisions[d]} ({formatNumber(counts[d])})
          </h2>
          <ul className="space-y-4">{runs.map((r, i) => (runDecision(r) === d ? card(i) : null))}</ul>
        </section>
      ))}
    </div>
  );
}
