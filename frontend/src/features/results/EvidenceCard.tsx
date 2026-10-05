import { getDictionary } from "@/i18n";
import { evidenceIndicators, explainAssessment } from "@/lib/verify/presentation";
import type { ClaimComponent, Evidence, EvidenceAssessment } from "@/lib/verify/types";
import { IndicatorList } from "./IndicatorList";

const t = getDictionary();
const e = t.results.evidence;

/**
 * One evidence item (spec §13). The SOURCE TEXT (verbatim from the provider) is visually and
 * semantically separate from MIZAN'S EXPLANATION. References and links come only from the
 * evidence record returned by the backend.
 */
export function EvidenceCard({
  evidence,
  assessments,
  components,
}: {
  evidence: Evidence;
  assessments: EvidenceAssessment[];
  components: ClaimComponent[];
}) {
  const md = evidence.metadata;
  const isPassage = evidence.source_type === "tafsir" || evidence.source_type === "asbab_nuzul";
  return (
    <article className="space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4" data-evidence-id={evidence.evidence_id}>
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-bold">{evidence.source_name}</h4>
        <span className="rounded-full border border-[var(--color-border-strong)] px-2.5 py-0.5 text-xs">
          {e.sourceType[evidence.source_type]}
        </span>
      </header>

      <section aria-label={e.sourceText} className="space-y-1.5">
        <p className="text-sm font-bold text-[var(--color-muted)]">{e.sourceText}</p>
        <blockquote dir="rtl" className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl border-s-4 border-[var(--color-brand)] bg-[var(--color-surface)] p-3 leading-8">
          {evidence.text}
        </blockquote>
      </section>

      {assessments.map((a, i) => (
        <section key={`${a.component_id}-${i}`} className="space-y-2 rounded-xl border border-dashed border-[var(--color-border-strong)] p-3">
          <div className="rounded-lg bg-[var(--color-brand-soft)] p-2.5">
            <p className="text-sm font-bold">{e.mizanExplanation}</p>
            <p className="text-sm leading-7">{explainAssessment(a, evidence, components)}</p>
          </div>
          {/* Only verbatim source text is ever presented as a quote from the source. A
              normalised matching key (e.g. for an ayah match) is not shown here — the
              full source text is displayed above. */}
          {a.evidence_span && evidence.text.includes(a.evidence_span) ? (
            <div className="space-y-1">
              <p className="text-sm font-bold text-[var(--color-muted)]">{e.citedSpan}</p>
              <blockquote dir="rtl" className="rounded-lg bg-[var(--color-surface)] p-2 leading-7">
                «{a.evidence_span}»
              </blockquote>
            </div>
          ) : null}
          {a.supported_part ? <p className="text-sm">{e.supportedPart} {a.supported_part}</p> : null}
          {a.unsupported_part ? <p className="text-sm">{e.unsupportedPart} {a.unsupported_part}</p> : null}
          {evidenceIndicators(a).length ? (
            <div className="space-y-1 text-sm">
              <p className="font-bold">{e.indicatorsTitle}</p>
              <IndicatorList items={evidenceIndicators(a)} />
            </div>
          ) : null}
        </section>
      ))}

      <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
        <dt className="font-bold">{e.reference}</dt>
        <dd>{evidence.reference}</dd>
        <dt className="font-bold">{e.provider}</dt>
        <dd>{evidence.provider === "quranpedia" ? "Quranpedia" : evidence.provider}</dd>
        {isPassage ? (
          <>
            <dt className="font-bold">{e.author}</dt>
            <dd>{md.provider_author ?? e.authorMissing}</dd>
          </>
        ) : null}
        {evidence.source_type === "asbab_nuzul" ? (
          <>
            <dt className="font-bold">{e.relationType}</dt>
            <dd>{md.relation_type === "unspecified" || !md.relation_type ? e.relationUnspecified : md.relation_type}</dd>
          </>
        ) : null}
        <dt className="font-bold">{e.record}</dt>
        <dd className="break-all" dir="ltr">
          {evidence.source_url ? (
            <a href={evidence.source_url} target="_blank" rel="noopener noreferrer" className="text-[var(--color-brand)] underline underline-offset-4">
              {evidence.source_address}
            </a>
          ) : (
            evidence.source_address
          )}
        </dd>
      </dl>
    </article>
  );
}
