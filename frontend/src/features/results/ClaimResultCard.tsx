"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { getDictionary } from "@/i18n";
import { formatNumber } from "@/lib/format";
import { canOfferAlternative } from "@/lib/verify/report";
import type { AlternativeWording, ClaimRun, VerificationOutcome } from "@/lib/verify/types";
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

function VerificationDetails({ outcome }: { outcome: VerificationOutcome }) {
  const [open, setOpen] = useState(false);
  const { components, assessments, related_unverified_addresses: related } = outcome.analysis;
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

      {related.length ? <p className="text-sm text-[var(--color-muted)]">{t.relatedUnverified(formatNumber(related.length))}</p> : null}

      {outcome.evidence.length ? (
        <div className="space-y-3">
          <Button variant="secondary" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            {open ? t.hideEvidence : t.showEvidence(formatNumber(outcome.evidence.length))}
          </Button>
          {open ? (
            <div className="space-y-3">
              {outcome.evidence.map((ev) => (
                <EvidenceCard
                  key={ev.evidence_id}
                  evidence={ev}
                  assessments={assessments.filter((a) => a.evidence_id === ev.evidence_id)}
                  components={components}
                />
              ))}
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
          <Block title={t.whyTitle}>
            <p>{o.why}</p>
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
