import { getDictionary } from "@/i18n";
import { evidenceQuote } from "@/lib/verify/presentation";
import type { Evidence, EvidenceAssessment } from "@/lib/verify/types";

const e = getDictionary().results.evidence;

/**
 * One evidence item, shown only inside «عرض الأدلة والتفاصيل» (spec §13): the source, the
 * verbatim passage Mizan relied on (visually separate as source text), the reference and the
 * original record. All values come from the evidence record returned by the backend.
 */
export function EvidenceCard({ evidence, assessments }: { evidence: Evidence; assessments: EvidenceAssessment[] }) {
  const quote = evidenceQuote(evidence, assessments);
  return (
    <article className="space-y-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-sm" data-evidence-id={evidence.evidence_id}>
      <p>
        <span className="text-[var(--color-muted)]">{e.source}: </span>
        <span className="font-semibold">{evidence.source_name}</span>
      </p>
      <section aria-label={quote.cited ? e.citedSpan : e.sourceText} className="space-y-1">
        <p className="text-[var(--color-muted)]">{quote.cited ? e.citedSpan : e.sourceText}</p>
        <blockquote dir="rtl" className="max-h-60 overflow-y-auto whitespace-pre-wrap rounded-lg border-s-4 border-[var(--color-brand)] bg-[var(--color-card)] p-3 text-base leading-8">
          {quote.text}
        </blockquote>
      </section>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        <dt className="text-[var(--color-muted)]">{e.reference}</dt>
        <dd>{evidence.reference}</dd>
        <dt className="text-[var(--color-muted)]">{e.original}</dt>
        <dd className="break-all">
          {evidence.source_url ? (
            <a href={evidence.source_url} target="_blank" rel="noopener noreferrer" className="text-[var(--color-brand)] underline underline-offset-4">
              {e.openRecord}
            </a>
          ) : (
            <span dir="ltr">{evidence.source_address}</span>
          )}
        </dd>
      </dl>
    </article>
  );
}
