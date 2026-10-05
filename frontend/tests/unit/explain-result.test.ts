import { describe, expect, it } from "vitest";
import { explainResult } from "@/lib/verify/presentation";
import type { Evidence, VerificationOutcome } from "@/lib/verify/types";
import { QURAN_EVIDENCE, TAFSIR_EVIDENCE, conflicting, contradicted, noEvidence, supported } from "../fixtures/outcomes";

// Shapes and texts taken from a real /verify result (Surat Ad-Duha, 2026-10-05).
const CLAIM = "نزل قوله تعالى «ما ودعك ربك وما قلى» لأن النبي ﷺ خرج في غزوة فتأخر الوحي بسبب ذلك";
const WAHIDI: Evidence = {
  ...TAFSIR_EVIDENCE,
  evidence_id: "mizan-ev:asbab:93:3",
  source_type: "asbab_nuzul",
  source_name: "أسباب النزول للواحدي",
  trusted_source_id: "asbab_al_nuzul_al_wahidi",
  reference: "أسباب نزول القرآن - الواحدي، الجزء 1، الصفحة 432 — سورة الضحى، الآية 3",
  text: "قالت امرأة من قريش للنبي صلى الله عليه وسلم: ما أرى شيطانك إلا قد ودَّعك. فنزل: ﴿وَٱلضُّحَىٰ﴾",
};
const DUHA_AYAH: Evidence = { ...QURAN_EVIDENCE, evidence_id: "mizan-ev:quran:1:6082", reference: "سورة الضحى، الآية 3", text: "مَا وَدَّعَكَ رَبُّكَ وَمَا قَلَىٰ" };

const duha = (rel: "insufficient" | "contradicts", span: string | null, status: VerificationOutcome["status"], outcome: "insufficient" | "contradicted"): VerificationOutcome => ({
  ...contradicted("d1", CLAIM),
  status,
  verified_reference: null,
  evidence: [WAHIDI, DUHA_AYAH],
  analysis: {
    components: [
      { component_id: "q1", text: "ما ودعك ربك وما قلى", kind: "quran_quote", role: "anchor", claim_type: "quran", outcome: "supported", evidence_ids: [DUHA_AYAH.evidence_id], verified_location: [], detail: null },
      { component_id: "s1", text: CLAIM, kind: "statement", role: "substantive", claim_type: "asbab_nuzul", outcome, evidence_ids: [WAHIDI.evidence_id], verified_location: [], detail: null },
    ],
    assessments: [
      { evidence_id: DUHA_AYAH.evidence_id, relationship: "supports", claim_component: null, component_id: "q1", evidence_span: "ما ودعك ربك وما قلي", supported_part: null, unsupported_part: null, rationale: "x", assessed_by: "deterministic", strength: { observations: [] } },
      { evidence_id: WAHIDI.evidence_id, relationship: rel, claim_component: null, component_id: "s1", evidence_span: span, supported_part: null, unsupported_part: null, rationale: "The passage …", assessed_by: "llm_analysis", strength: { observations: [] } },
    ],
    related_unverified_addresses: [],
    evidence_conflicts: [],
  },
});

describe("«لماذا هذه النتيجة؟» — plain wording built only from the result", () => {
  it("insufficient (the real Ad-Duha result): names the source checked and says it neither proves nor disproves", () => {
    const lines = explainResult(duha("insufficient", null, "insufficient_evidence", "insufficient"));
    expect(lines).toEqual([
      "راجع ميزان ما ورد في أسباب النزول للواحدي (عند سورة الضحى، الآية 3)، ولم يجد فيه ما يُثبت ما ورد في ادعائك أو ينفيه.",
      "نص الآية التي ذكرتها صحيح، لكن هذا وحده لا يُثبت سبب النزول المذكور.",
      "لذلك لم تكن المصادر التي راجعها ميزان كافية لإثبات الادعاء أو نفيه.",
    ]);
    expect(lines.join(" ")).not.toContain(CLAIM); // the whole claim is not echoed back
  });

  it("contradicted: what the claim says vs. what the source says, quoting the source verbatim", () => {
    const span = "قالت امرأة من قريش للنبي صلى الله عليه وسلم: ما أرى شيطانك إلا قد ودَّعك";
    const lines = explainResult(duha("contradicts", span, "contradicted", "contradicted"));
    expect(lines[0]).toBe(`يذكر أسباب النزول للواحدي (عند سورة الضحى، الآية 3) خلاف ما ورد في ادعائك: «${span}».`);
    expect(lines).toContain("نص الآية التي ذكرتها صحيح، لكن هذا وحده لا يُثبت سبب النزول المذكور.");
  });

  it("a non-verbatim span is never quoted as the source", () => {
    const lines = explainResult(duha("contradicts", "نص غير موجود في المصدر", "contradicted", "contradicted"));
    expect(lines[0]).toBe("ما ورد في ادعائك يخالف ما في أسباب النزول للواحدي (عند سورة الضحى، الآية 3).");
  });

  it("contradicted Quran location: the stated location vs. the documented one", () => {
    const lines = explainResult(contradicted());
    expect(lines).toEqual([
      "النص الذي ذكرته موجود في المصحف (سورة البقرة، الآية 158).",
      "ورد في ادعائك أن النص في «سورة آل عمران»، لكنه في المصحف في سورة البقرة، الآية 158.",
    ]);
  });

  it("supported: says what the source has that supports the claim", () => {
    const o = supported("s", "قال تعالى في سورة البقرة: «إن الصفا والمروة من شعائر الله»");
    const lines = explainResult({
      ...o,
      analysis: { ...o.analysis, components: o.analysis.components.map((c) => ({ ...c, outcome: "supported" })), assessments: o.analysis.assessments.map((a) => ({ ...a, relationship: "supports" })) },
    });
    expect(lines).toEqual(["النص الذي ذكرته موجود في المصحف (سورة البقرة، الآية 158).", "الموضع الذي ذكرته صحيح (سورة البقرة، الآية 158)."]);
  });

  it("partially supported: which part is supported and which is not", () => {
    const base = duha("insufficient", null, "partially_supported", "insufficient");
    const o: VerificationOutcome = {
      ...base,
      analysis: {
        ...base.analysis,
        components: base.analysis.components.map((c) => (c.component_id === "s1" ? { ...c, outcome: "partially_supported" as const } : c)),
        assessments: base.analysis.assessments.map((a) =>
          a.component_id === "s1" ? { ...a, relationship: "partially_supports" as const, supported_part: "نزول السورة بعد تأخر الوحي", unsupported_part: "خروج النبي ﷺ في غزوة" } : a,
        ),
      },
    };
    expect(explainResult(o)[0]).toBe(
      "يؤيد أسباب النزول للواحدي (عند سورة الضحى، الآية 3) هذا الجزء: «نزول السورة بعد تأخر الوحي»، لكنه لا يُثبت: «خروج النبي ﷺ في غزوة».",
    );
  });

  it("conflicting: names who supports and who opposes", () => {
    expect(explainResult(conflicting)[0]).toBe("المصادر مختلفة بشأن «كذا»: يؤيده التفسير الميسر، ويخالفه تفسير ابن كثير؛ لذلك لم يرجّح ميزان أحدهما.");
  });

  it("no evidence: the spec sentence, never 'false'", () => {
    expect(explainResult(noEvidence)).toEqual([
      "لم يتم العثور على دليل كافٍ للتحقق من الادعاء ضمن المصادر المعتمدة حاليًا في ميزان. عدم العثور على دليل لا يعني أن الادعاء خاطئ.",
    ]);
  });
});
