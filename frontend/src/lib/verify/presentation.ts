/**
 * User-facing wording for a verification result, built ONLY from the backend's validated
 * result: relationships, components, evidence records. Deterministic, Arabic, no new facts.
 * The raw analysis rationale (which an LLM may have written, possibly not in Arabic) is never
 * shown; every sentence here is traceable to a relationship or record in the outcome.
 */
import type { ClaimComponent, Evidence, EvidenceAssessment, VerificationOutcome } from "./types";

type Relationship = EvidenceAssessment["relationship"];

// ---------------------------------------------------------------- «لماذا هذه النتيجة؟»

const NO_EVIDENCE =
  "لم يتم العثور على دليل كافٍ للتحقق من الادعاء ضمن المصادر المعتمدة حاليًا في ميزان. عدم العثور على دليل لا يعني أن الادعاء خاطئ."; // spec §5

const squash = (s: string) => s.replace(/[\sً-ْ«»"“”.,،:؛!؟?()\[\]﴿﴾-]/g, "");

/** The ayah part of a passage reference ("… — سورة الضحى، الآية 3"), from the record itself. */
export function ayahOf(ev: Evidence): string | null {
  const i = ev.reference.lastIndexOf(" — ");
  return i >= 0 ? ev.reference.slice(i + 3) : null;
}

/** A source with its location, e.g. «أسباب النزول للواحدي (سورة الضحى، الآية 3)». */
function sourceAt(ev: Evidence): string {
  if (ev.source_type === "quran") return `المصحف (${ev.reference})`;
  const ayah = ayahOf(ev);
  return ayah ? `${ev.source_name} (عند ${ayah})` : ev.source_name;
}

const verbatim = (a: EvidenceAssessment, ev: Evidence | undefined) =>
  a.evidence_span && ev && ev.text.includes(a.evidence_span) ? a.evidence_span : null;

/**
 * Plain-Arabic answer to «لماذا هذه النتيجة؟»: what the claim says, what the checked source
 * says, and how they relate — built ONLY from the validated result (components = verbatim claim
 * spans; relationships; evidence records; verbatim cited spans). Nothing is paraphrased or added.
 */
export function explainResult(outcome: VerificationOutcome): string[] {
  const { components, assessments } = outcome.analysis;
  const byEv = new Map(outcome.evidence.map((e) => [e.evidence_id, e]));
  const claimKey = squash(outcome.confirmed_claim_text);
  // A component that is (almost) the whole claim is referred to as "your claim", not quoted back.
  const ref = (c: ClaimComponent) =>
    squash(c.text).length >= claimKey.length * 0.8 ? "ما ورد في ادعائك" : `«${c.text}»`;
  const of = (c: ClaimComponent, rel: Relationship) =>
    assessments.filter((a) => a.component_id === c.component_id && a.relationship === rel).map((a) => ({ a, ev: byEv.get(a.evidence_id) }));
  const names = (items: { ev?: Evidence }[]) => [...new Set(items.flatMap((x) => (x.ev ? [x.ev.source_name] : [])))].join(" و");

  const out: string[] = [];
  if (outcome.status === "no_evidence_found") return [NO_EVIDENCE];

  const subs = components.filter((c) => c.role === "substantive");
  const anchors = components.filter((c) => c.role === "anchor");
  for (const c of [...subs, ...anchors.filter((x) => x.outcome === "contradicted")]) {
    const isQuran = c.claim_type === "quran";
    if (c.outcome === "supported") {
      const [first] = of(c, "supports").length
        ? of(c, "supports")
        : c.evidence_ids.flatMap((id) => (byEv.get(id) ? [{ a: undefined, ev: byEv.get(id) }] : []));
      if (isQuran && first?.ev)
        out.push(c.kind === "quran_quote" ? `النص الذي ذكرته موجود في المصحف (${first.ev.reference}).` : `الموضع الذي ذكرته صحيح (${first.ev.reference}).`);
      else if (first?.ev) {
        const span = first.a ? verbatim(first.a, first.ev) : null;
        out.push(`وجد ميزان في ${sourceAt(first.ev)} ما يؤيد ${ref(c)}${span ? `، ونصه: «${span}»` : ""}.`);
      }
    } else if (c.outcome === "contradicted") {
      const [first] = of(c, "contradicts");
      if (isQuran && (c.kind === "quran_location" || c.kind === "quran_reference_assertion"))
        out.push(`ورد في ادعائك أن النص في «${c.text}»، لكنه في المصحف في ${outcome.verified_reference ?? first?.ev?.reference ?? "موضع آخر"}.`);
      else if (isQuran) out.push(`النص الذي ذكرته لا يطابق نص المصحف${first?.ev ? ` (${first.ev.reference})` : ""}.`);
      else if (first?.ev) {
        const span = verbatim(first.a, first.ev);
        const src = sourceAt(first.ev);
        const whole = ref(c) === "ما ورد في ادعائك";
        out.push(
          whole
            ? span
              ? `يذكر ${src} خلاف ما ورد في ادعائك: «${span}».`
              : `ما ورد في ادعائك يخالف ما في ${src}.`
            : span
              ? `ورد في ادعائك ${ref(c)}، لكن ${src} يذكر خلاف ذلك: «${span}».`
              : `ورد في ادعائك ${ref(c)}، وهذا يخالف ما في ${src}.`,
        );
      }
    } else if (c.outcome === "partially_supported") {
      const [first] = of(c, "partially_supports");
      if (first?.a.supported_part && first.a.unsupported_part)
        out.push(`يؤيد ${sourceAt(first.ev!)} هذا الجزء: «${first.a.supported_part}»، لكنه لا يُثبت: «${first.a.unsupported_part}».`);
      else if (first?.ev) out.push(`يؤيد ${sourceAt(first.ev)} جزءًا من ${ref(c)} فقط، ولم يُثبت الباقي.`);
    } else if (c.outcome === "conflicting") {
      const pro = names([...of(c, "supports"), ...of(c, "partially_supports")]);
      const con = names(of(c, "contradicts"));
      out.push(`المصادر مختلفة بشأن ${ref(c)}: ${pro ? `يؤيده ${pro}` : ""}${pro && con ? "، و" : ""}${con ? `يخالفه ${con}` : ""}؛ لذلك لم يرجّح ميزان أحدهما.`);
    } else if (c.outcome === "insufficient") {
      const found = of(c, "insufficient");
      const where = found.flatMap((x) => (x.ev ? [sourceAt(x.ev)] : []));
      out.push(`راجع ميزان ما ورد في ${where.length ? [...new Set(where)].join(" و") : "المصادر المعتمدة"}، ولم يجد فيه ما يُثبت ${ref(c)} أو ينفيه.`);
    } else if (c.outcome === "not_established") {
      out.push(isQuran && c.kind === "quran_quote" ? "لم يجد ميزان النص الذي ذكرته في المصحف." : `لم يجد ميزان في المصادر المعتمدة ما يُثبت ${ref(c)}.`);
    }
  }

  const verifiedAnchor = anchors.some((a) => a.outcome === "supported" || a.outcome === "partially_supported");
  if (verifiedAnchor && outcome.status !== "supported") {
    const kind = subs.some((c) => c.claim_type === "asbab_nuzul") ? "سبب النزول المذكور" : "المعنى المذكور";
    out.push(`نص الآية التي ذكرتها صحيح، لكن هذا وحده لا يُثبت ${kind}.`);
  }
  if (outcome.status === "insufficient_evidence") out.push("لذلك لم تكن المصادر التي راجعها ميزان كافية لإثبات الادعاء أو نفيه.");
  return out.length ? [...new Set(out)] : outcome.why ? [outcome.why] : [];
}

// ---------------------------------------------------------------- evidence preview / details

/** «المصدر — الموضع» for the short preview; the place comes from the record's own reference. */
export function evidencePreview(outcome: VerificationOutcome): { key: string; source: string; place: string }[] {
  const seen = new Set<string>();
  return outcome.evidence.flatMap((ev) => {
    const place = ev.source_type === "quran" ? ev.reference : (ayahOf(ev) ?? ev.reference);
    const key = `${ev.source_name} — ${place}`;
    if (seen.has(key)) return [];
    seen.add(key);
    return [{ key, source: ev.source_name, place }];
  });
}

/**
 * The text shown for one evidence item: the verbatim cited passage when the analysis cited
 * one that occurs exactly in the record, otherwise the record's own text (e.g. the ayah).
 */
export function evidenceQuote(ev: Evidence, assessments: EvidenceAssessment[]): { text: string; cited: boolean } {
  for (const a of assessments) {
    if (a.evidence_id === ev.evidence_id && a.relationship !== "insufficient" && verbatim(a, ev))
      return { text: a.evidence_span!, cited: true };
  }
  return { text: ev.text, cited: false };
}
