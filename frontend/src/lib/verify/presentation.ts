/**
 * User-facing wording for a verification result, built ONLY from the backend's validated
 * result: relationships, components, evidence records. Deterministic, Arabic, no new facts.
 * The raw analysis rationale (which an LLM may have written, possibly not in Arabic) is never
 * shown; every sentence here is traceable to a relationship or record in the outcome.
 */
import type { ClaimComponent, Evidence, EvidenceAssessment, VerificationOutcome } from "./types";

type Relationship = EvidenceAssessment["relationship"];

const RANK: Record<Relationship, number> = { contradicts: 3, supports: 2, partially_supports: 1, insufficient: 0 };

const quote = (text: string) => `«${text}»`;

function componentText(a: EvidenceAssessment, components: ClaimComponent[]): string | null {
  return components.find((c) => c.component_id === a.component_id)?.text ?? a.claim_component ?? null;
}

/** One plain-Arabic sentence for one assessment (shown under «شرح ميزان»). */
export function explainAssessment(
  a: EvidenceAssessment,
  evidence: Evidence,
  components: ClaimComponent[],
  { namedSource = true }: { namedSource?: boolean } = {},
): string {
  const part = componentText(a, components);
  const target = part ? quote(part) : "الادعاء";
  const comp = components.find((c) => c.component_id === a.component_id);
  if (evidence.source_type === "quran") {
    if (a.relationship === "supports") {
      return comp?.kind === "quran_location" || comp?.kind === "quran_reference_assertion"
        ? `الموضع المذكور يطابق ما في المصحف: ${evidence.reference}.`
        : `نص الآية موثّق في المصحف: ${evidence.reference}.`;
    }
    if (a.relationship === "contradicts") return `${target} لا يطابق المصحف؛ الموضع الموثّق للنص: ${evidence.reference}.`;
    if (a.relationship === "partially_supports") return `جزء من ${target} يطابق نص المصحف (${evidence.reference}).`;
    return `نص المصحف (${evidence.reference}) ذو صلة، لكنه لا يكفي لإثبات ${target}.`;
  }
  const subject = namedSource ? `نص ${evidence.source_name} ` : "";
  if (a.relationship === "supports") return `${subject}يؤيد ${target}.`;
  if (a.relationship === "partially_supports") return `${subject}يؤيد جزءًا من ${target} فقط.`;
  if (a.relationship === "contradicts") return `${subject}يخالف ${target}.`;
  return `${subject}ذو صلة بـ${target}، لكنه لا يكفي لإثباته.`;
}

/** Strongest relationship of one evidence item (contradicts > supports > partial > insufficient). */
export function mainRelationship(evidence: Evidence, assessments: EvidenceAssessment[]): Relationship | null {
  const rels = assessments.filter((a) => a.evidence_id === evidence.evidence_id).map((a) => a.relationship);
  return rels.length ? rels.reduce((x, y) => (RANK[y] > RANK[x] ? y : x)) : null;
}

/** «الأدلة التي اعتمد عليها ميزان»: one line per evidence item that was actually assessed. */
export function evidenceSummary(outcome: VerificationOutcome): { evidenceId: string; source: string; text: string }[] {
  const { assessments, components } = outcome.analysis;
  return outcome.evidence.flatMap((ev) => {
    const rel = mainRelationship(ev, assessments);
    if (!rel) return [];
    const a = assessments.find((x) => x.evidence_id === ev.evidence_id && x.relationship === rel)!;
    const source = ev.source_type === "quran" ? `${ev.source_name} (${ev.reference})` : ev.source_name;
    return [{ evidenceId: ev.evidence_id, source, text: explainAssessment(a, ev, components, { namedSource: false }) }];
  });
}

export type Indicator = { ok: boolean | null; text: string };

const TYPE_WORD: Record<string, string> = { tafsir: "التفسير", asbab_nuzul: "أسباب النزول" };

/** «مؤشرات التحقق»: checks Mizan actually performed for this claim, stated as facts. */
export function verificationIndicators(outcome: VerificationOutcome): Indicator[] {
  const { components, assessments } = outcome.analysis;
  const out: Indicator[] = [];
  const quoteC = components.filter((c) => c.kind === "quran_quote");
  if (quoteC.some((c) => c.outcome === "supported")) out.push({ ok: true, text: "نص الآية موثّق في المصحف." });
  else if (quoteC.some((c) => c.outcome === "not_established"))
    out.push({ ok: false, text: "لم يُعثر على النص المقتبس في المصحف." });
  const locC = components.filter((c) => c.kind === "quran_location" || c.kind === "quran_reference_assertion");
  if (locC.some((c) => c.outcome === "contradicted"))
    out.push({ ok: false, text: outcome.verified_reference ? `الموضع المذكور لا يطابق المصحف؛ الموضع الموثّق: ${outcome.verified_reference}.` : "الموضع المذكور لا يطابق المصحف." });
  else if (locC.some((c) => c.outcome === "supported")) out.push({ ok: true, text: "موضع الآية المذكور صحيح." });

  const byEv = new Map(outcome.evidence.map((e) => [e.evidence_id, e]));
  for (const type of ["tafsir", "asbab_nuzul"] as const) {
    const supporting = new Set<string>();
    const opposing = new Set<string>();
    for (const a of assessments) {
      const ev = byEv.get(a.evidence_id);
      if (!ev || ev.source_type !== type) continue;
      if (a.relationship === "supports") supporting.add(ev.source_name);
      if (a.relationship === "contradicts") opposing.add(ev.source_name);
    }
    if (supporting.size > 1) out.push({ ok: true, text: `المعنى مؤيد في أكثر من مصدر من مصادر ${TYPE_WORD[type]}: ${[...supporting].join("، ")}.` });
    else if (supporting.size === 1) out.push({ ok: true, text: `المعنى مؤيد في ${[...supporting][0]}.` });
    if (opposing.size) out.push({ ok: false, text: `يوجد في ${[...opposing].join("، ")} ما يخالف ذلك.` });
  }

  if (outcome.evidence.length) {
    if (!assessments.some((a) => a.relationship === "contradicts"))
      out.push({ ok: true, text: "لم يظهر في المصادر التي فُحصت ما يخالف الادعاء." });
    if (components.some((c) => c.role === "substantive" && (c.outcome === "partially_supported" || c.outcome === "insufficient" || c.outcome === "not_established")))
      out.push({ ok: null, text: "جزء من الادعاء لم تثبته الأدلة." });
    if (outcome.evidence.every((e) => e.source_url || e.source_address))
      out.push({ ok: true, text: "لكل دليل سجل أصلي لدى المصدر يمكن الرجوع إليه." });
  }
  return out;
}

/** Per-evidence checks (replaces raw strength observations): only signals the backend recorded. */
export function evidenceIndicators(a: EvidenceAssessment): Indicator[] {
  const signals = new Set(a.strength.observations.map((o) => o.signal));
  const out: Indicator[] = [];
  if (signals.has("source_suitability")) out.push({ ok: true, text: "المصدر معتمد ومختص بهذا النوع من الادعاءات." });
  if (signals.has("directness"))
    out.push(
      a.relationship === "insufficient"
        ? { ok: null, text: "النص ذو صلة، لكنه لا يتناول هذا الجزء مباشرة." }
        : a.relationship === "partially_supports"
          ? { ok: null, text: "النص يتناول جزءًا من هذا الادعاء فقط." }
          : { ok: true, text: "النص يتناول هذا الجزء من الادعاء مباشرة." },
    );
  if (signals.has("completeness")) out.push({ ok: null, text: "لا يغطي الادعاء كاملًا." });
  if (signals.has("traceability")) out.push({ ok: true, text: "النص منقول كما هو من سجل المصدر الرسمي." });
  return out;
}
