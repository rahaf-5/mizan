"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/Notice";
import { getDictionary } from "@/i18n";
import { formatNumber } from "@/lib/format";
import { evidencePreview, explainResult } from "@/lib/verify/presentation";
import { canOfferAlternative } from "@/lib/verify/report";
import type { AlternativeWording, ClaimRun, Evidence, VerificationOutcome } from "@/lib/verify/types";
import { AlternativeWordingPanel } from "./AlternativeWordingPanel";
import { EvidenceCard } from "./EvidenceCard";
import { StatusBadge } from "./StatusBadge";

const t = getDictionary().results;

const SOURCE_NAMES: Record<string, string> = {
  dorar_hadith: "الدرر السنية — الموسوعة الحديثية",
};

function technicalReason(code: string): string {
  if (code === "llm_rate_limited" || code === "llm_timeout") return t.technical.busy;
  if (code === "source_unavailable" || code === "verification_incomplete") return t.technical.source;
  if (code === "network_error") return t.technical.network;
  if (code === "llm_not_configured") return t.technical.notConfigured;
  if (code === "claim_too_long" || code === "http_422" || code === "invalid_request") return t.technical.invalidInput;
  return "";
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h3 className="text-sm font-semibold text-[var(--color-muted)]">{title}</h3>
      <div className="space-y-1.5 leading-8">{children}</div>
    </section>
  );
}

type ConflictGroup = keyof typeof t.conflictGroups;

/** Conflicting evidence only: supporting / opposing / other, shown separately (spec §13). */
function conflictGroups(outcome: VerificationOutcome): { group: ConflictGroup; items: Evidence[] }[] {
  const groupOf = (ev: Evidence): ConflictGroup => {
    const rels = outcome.analysis.assessments.filter((a) => a.evidence_id === ev.evidence_id).map((a) => a.relationship);
    if (rels.includes("contradicts")) return "contradicts";
    if (rels.includes("supports") || rels.includes("partially_supports")) return "supports";
    return "other";
  };
  return (["supports", "contradicts", "other"] as const)
    .map((group) => ({ group, items: outcome.evidence.filter((ev) => groupOf(ev) === group) }))
    .filter((g) => g.items.length > 0);
}

/** Level 2: short evidence preview + one button; level 3 (on demand): evidence details. */
function EvidenceSection({ outcome }: { outcome: VerificationOutcome }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const preview = evidencePreview(outcome);
  if (!preview.length) return null;
  const card = (ev: Evidence) => <EvidenceCard key={ev.evidence_id} evidence={ev} assessments={outcome.analysis.assessments} />;
  return (
    <section className="space-y-3 border-t border-[var(--color-border)] pt-4">
      <h3 className="text-sm font-semibold text-[var(--color-muted)]">{t.evidenceSummaryTitle}</h3>
      <ul className="space-y-1 text-sm">
        {preview.map((p) => (
          <li key={p.key}>
            {p.source} <span className="text-[var(--color-muted)]">— {p.place}</span>
          </li>
        ))}
      </ul>
      <Button variant="secondary" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((v) => !v)}>
        {open ? t.hideDetails : t.showDetails}
      </Button>
      {open ? (
        <div id={panelId} className="space-y-3">
          {outcome.status === "conflicting_evidence"
            ? conflictGroups(outcome).map(({ group, items }) => (
                <section key={group} className="space-y-2" aria-label={t.conflictGroups[group]}>
                  <h4 className="text-sm font-semibold">
                    {t.conflictGroups[group]} ({formatNumber(items.length)})
                  </h4>
                  {items.map(card)}
                </section>
              ))
            : outcome.evidence.map(card)}
          {outcome.limitations.length ? (
            <section className="space-y-1 text-sm">
              <h4 className="font-semibold">{t.limitationsTitle}</h4>
              <ul className="list-disc space-y-1 ps-6 text-[var(--color-muted)]">
                {outcome.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

/**
 * The single result card used by Quick Check and by every claim in Full Content:
 * decision (status) → claim → why → what to do (+ verified alternative) → evidence on demand.
 */
export function ClaimResultCard({
  run,
  index,
  showIndex = true,
  onRetry,
  onAdopt,
}: {
  run: ClaimRun;
  index: number;
  showIndex?: boolean;
  onRetry: () => void;
  onAdopt: (alt: AlternativeWording) => void;
}) {
  let badge: React.ReactNode;
  let why: React.ReactNode = null;
  let what: React.ReactNode = null;
  let after: React.ReactNode = null;
  const retry = (
    <Button variant="secondary" onClick={onRetry}>
      {t.technical.retry}
    </Button>
  );

  if (run.state === "waiting" || run.state === "running") {
    badge = <span className="text-sm text-[var(--color-muted)]">{t.runState[run.state]}</span>;
  } else if (run.state === "failed") {
    badge = <StatusBadge kind="system_error" />;
    why = <p>{`${t.technical.why} ${technicalReason(run.code)}`.trim()}</p>;
    what = (
      <>
        <p>{t.technical.what}</p>
        {retry}
      </>
    );
  } else {
    const o = run.outcome;
    if (o.kind === "verification") {
      badge = <StatusBadge kind={o.status} />;
      why = explainResult(o).map((line) => <p key={line}>{line}</p>);
      what = (
        <>
          <p>{t.whatToDo[o.status]}</p>
          {canOfferAlternative(o) ? <AlternativeWordingPanel runId={run.runId} claimId={o.claim_id} onAdopt={onAdopt} /> : null}
        </>
      );
      after = <EvidenceSection outcome={o} />;
    } else if (o.kind === "required_source_unavailable") {
      badge = <StatusBadge kind="required_source_unavailable" />;
      why = <p>{t.unavailable.why(o.unavailable_sources.map((s) => SOURCE_NAMES[s] ?? s).join("، "))}</p>;
      what = <p>{t.unavailable.what}</p>;
    } else if (o.kind === "out_of_scope") {
      badge = <StatusBadge kind="out_of_scope" />;
      why = <p>{t.outOfScope.why}</p>;
      what = <p>{t.outOfScope.what}</p>;
    } else {
      badge = <StatusBadge kind="system_error" />;
      why = <p>{`${t.technical.why} ${technicalReason(o.error.code)}`.trim()}</p>;
      what = (
        <>
          <p>{t.technical.what}</p>
          {o.error.retryable ? retry : null}
        </>
      );
    }
  }

  return (
    <li className="space-y-5 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm sm:p-6" data-run-state={run.state}>
      <header className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          {badge}
          {showIndex ? (
            <span className="text-sm text-[var(--color-muted)]">
              {t.claimLabel} {formatNumber(index + 1)}
            </span>
          ) : null}
        </div>
        <p dir="auto" className="border-s-4 border-[var(--color-border-strong)] ps-3 text-lg leading-8">
          {run.claim.confirmed_claim_text}
        </p>
      </header>
      {run.state === "done" && run.adopted ? <Notice tone="success" role="status" title={t.alternative.adopted} /> : null}
      {why ? <Section title={t.whyTitle}>{why}</Section> : null}
      {what ? <Section title={t.whatTitle}>{what}</Section> : null}
      {after}
    </li>
  );
}
