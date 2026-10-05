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

// ---------------------------------------------------------------- «لماذا هذه النتيجة؟»

const NO_EVIDENCE =
  "لم يتم العثور على دليل كافٍ للتحقق من الادعاء ضمن المصادر المعتمدة حاليًا في ميزان. عدم العثور على دليل لا يعني أن الادعاء خاطئ."; // spec §5

const squash = (s: string) => s.replace(/[\sً-ْ«»"“”.,،:؛!؟?()\[\]﴿﴾-]/g, "");

/** The ayah part of a passage reference ("… — سورة الضحى، الآية 3"), from the record itself. */
function ayahOf(ev: Evidence): string | null {
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
