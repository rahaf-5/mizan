"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/Notice";
import { getDictionary } from "@/i18n";
import { formatNumber } from "@/lib/format";
import { evidenceSummary, explainResult, verificationIndicators } from "@/lib/verify/presentation";
import { canOfferAlternative } from "@/lib/verify/report";
import type { AlternativeWording, ClaimRun, Evidence, VerificationOutcome } from "@/lib/verify/types";
import { AlternativeWordingPanel } from "./AlternativeWordingPanel";
import { EvidenceCard } from "./EvidenceCard";
import { IndicatorList } from "./IndicatorList";
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

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1">
      <h4 className="font-bold">{title}</h4>
      <div className="leading-7">{children}</div>
    </section>
  );
}

type ConflictGroup = keyof typeof t.conflictGroups;

/** For conflicting evidence only: group cards by how each item relates to the claim (spec §13).
 * Presentation only — the status and every relationship come from the backend unchanged. */
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

function VerificationDetails({ outcome }: { outcome: VerificationOutcome }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const { components, assessments, related_unverified_addresses: related } = outcome.analysis;
  const summary = evidenceSummary(outcome);
  const indicators = verificationIndicators(outcome);
  const card = (ev: Evidence) => (
    <EvidenceCard
      key={ev.evidence_id}
      evidence={ev}
      assessments={assessments.filter((a) => a.evidence_id === ev.evidence_id)}
      components={components}
    />
  );
  return (
    <div className="space-y-4">
      {components.length ? (
        <section className="space-y-2">
          <h4 className="font-bold">{t.componentsTitle}</h4>
          <ul className="space-y-2">
            {components.map((c) => (
              <li key={c.component_id} className="rounded-xl border border-[var(--color-border)] p-3 text-sm" data-outcome={c.outcome ?? ""}>
                <p dir="auto">«{c.text}»</p>
                <p className="pt-1 font-bold">
                  {c.outcome ? t.componentOutcome[c.outcome] : "—"}
                  {c.role === "anchor" ? <span className="font-normal text-[var(--color-muted)]"> — {t.anchorNote}</span> : null}
                </p>
                {c.detail ? <p className="pt-1">{c.detail}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {outcome.status === "conflicting_evidence" ? (
        <Block title={t.conflictTitle}>
          <p>{t.conflictBody}</p>
        </Block>
      ) : null}

      {outcome.verified_reference ? (
        <Block title={t.verifiedReferenceTitle}>
          <p>{outcome.verified_reference}</p>
          <p className="text-sm text-[var(--color-muted)]">{t.verifiedReferenceNote}</p>
        </Block>
      ) : null}

      {outcome.limitations.length ? (
        <Block title={t.limitationsTitle}>
          <ul className="list-disc space-y-1 ps-6 text-sm">
            {outcome.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </Block>
      ) : null}

      {summary.length ? (
        <Block title={t.evidenceSummaryTitle}>
          <ul className="list-disc space-y-1 ps-6">
            {summary.map((s) => (
              <li key={s.evidenceId}>
                <span className="font-bold">{s.source}:</span> {s.text}
              </li>
            ))}
          </ul>
        </Block>
      ) : null}

      {indicators.length ? (
        <Block title={t.indicatorsTitle}>
          <IndicatorList items={indicators} />
        </Block>
      ) : null}

      {related.length ? <p className="text-sm text-[var(--color-muted)]">{t.relatedUnverified(formatNumber(related.length))}</p> : null}

      {outcome.evidence.length ? (
        <div className="space-y-3">
          <Button variant="secondary" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((v) => !v)}>
            {open ? t.hideEvidence : t.showEvidence(formatNumber(outcome.evidence.length))}
          </Button>
          {open ? (
            <div id={panelId} className="space-y-3">
              {outcome.status === "conflicting_evidence"
                ? conflictGroups(outcome).map(({ group, items }) => (
                    <section key={group} className="space-y-3" aria-label={t.conflictGroups[group]}>
                      <h5 className="font-bold">
                        {t.conflictGroups[group]} ({formatNumber(items.length)})
                      </h5>
                      {items.map(card)}
                    </section>
                  ))
                : outcome.evidence.map(card)}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="text-sm text-[var(--color-muted)]">{t.noEvidenceShown}</p>
      )}
    </div>
  );
}

/** Claim card (spec §12): claim → status → why → what to do → evidence & sources. */
export function ClaimResultCard({
  run,
  index,
  onRetry,
  onAdopt,
}: {
  run: ClaimRun;
  index: number;
  onRetry: () => void;
  onAdopt: (alt: AlternativeWording) => void;
}) {
  const header = (badge: React.ReactNode) => (
    <header className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-bold text-[var(--color-muted)]">
          {t.claimLabel} {formatNumber(index + 1)}
        </p>
        {badge}
      </div>
      <p dir="auto" className="text-lg leading-8">
        {run.claim.confirmed_claim_text}
      </p>
    </header>
  );

  let body: React.ReactNode = null;
  let badge: React.ReactNode = null;
  if (run.state === "waiting" || run.state === "running") {
    badge = <span className="text-sm text-[var(--color-muted)]">{t.runState[run.state]}</span>;
  } else if (run.state === "failed") {
    badge = <StatusBadge kind="system_error" />;
    body = (
      <>
        <Block title={t.whyTitle}>
          <p>
            {t.technical.why} {technicalReason(run.code)}
          </p>
        </Block>
        <Block title={t.whatTitle}>
          <p>{t.technical.what}</p>
        </Block>
        <Button variant="secondary" onClick={onRetry}>
          {t.technical.retry}
        </Button>
      </>
    );
  } else {
    const o = run.outcome;
    if (o.kind === "verification") {
      badge = <StatusBadge kind={o.status} />;
      body = (
        <>
          {run.adopted ? <Notice tone="success" role="status" title={t.alternative.adopted} /> : null}
          <Block title={t.whyTitle}>
            {explainResult(o).map((line) => (
              <p key={line}>{line}</p>
            ))}
          </Block>
          <Block title={t.whatTitle}>
            <p>{o.what_to_do}</p>
          </Block>
          <VerificationDetails outcome={o} />
          {canOfferAlternative(o) ? (
            <AlternativeWordingPanel runId={run.runId} claimId={o.claim_id} onAdopt={onAdopt} />
          ) : null}
        </>
      );
    } else if (o.kind === "required_source_unavailable") {
      badge = <StatusBadge kind="required_source_unavailable" />;
      const names = o.unavailable_sources.map((s) => SOURCE_NAMES[s] ?? s).join("، ");
      body = (
        <>
          <Block title={t.whyTitle}>
            <p>{t.unavailable.why(names)}</p>
          </Block>
          <Block title={t.whatTitle}>
            <p>{t.unavailable.what}</p>
          </Block>
        </>
      );
    } else if (o.kind === "out_of_scope") {
      badge = <StatusBadge kind="out_of_scope" />;
      body = (
        <>
          <Block title={t.whyTitle}>
            <p>{t.outOfScope.why}</p>
          </Block>
          <Block title={t.whatTitle}>
            <p>{t.outOfScope.what}</p>
          </Block>
        </>
      );
    } else {
      badge = <StatusBadge kind="system_error" />;
      body = (
        <>
          <Block title={t.whyTitle}>
            <p>
              {t.technical.why} {technicalReason(o.error.code)}
            </p>
          </Block>
          <Block title={t.whatTitle}>
            <p>{t.technical.what}</p>
          </Block>
          {o.error.retryable ? (
            <Button variant="secondary" onClick={onRetry}>
              {t.technical.retry}
            </Button>
          ) : null}
        </>
      );
    }
  }

  return (
    <li className="space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm" data-run-state={run.state}>
      {header(badge)}
      {body}
    </li>
  );
}
