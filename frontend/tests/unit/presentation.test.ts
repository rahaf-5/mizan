import { describe, expect, it } from "vitest";
import { evidenceIndicators, evidenceSummary, explainAssessment, verificationIndicators } from "@/lib/verify/presentation";
import type { VerificationOutcome } from "@/lib/verify/types";
import { IBN_KATHIR_EVIDENCE, QURAN_EVIDENCE, TAFSIR_EVIDENCE, conflicting, contradicted, noEvidence } from "../fixtures/outcomes";

/** Supported tafsir claim shaped like the real backend result (anchor ayah + two tafsir sources). */
const supportedTafsir: VerificationOutcome = {
  ...conflicting,
  status: "supported",
  result_group: "verified",
  limitations: [],
  evidence: [{ ...QURAN_EVIDENCE, reference: "سورة البقرة، الآية 255" }, TAFSIR_EVIDENCE, IBN_KATHIR_EVIDENCE],
  analysis: {
    components: [
      { component_id: "q1", text: "لا تأخذه سنة ولا نوم", kind: "quran_quote", role: "anchor", claim_type: "quran", outcome: "supported", evidence_ids: [QURAN_EVIDENCE.evidence_id], verified_location: [], detail: null },
      { component_id: "s1", text: "أن الله لا يأخذه نعاس ولا نوم", kind: "statement", role: "substantive", claim_type: "tafsir", outcome: "supported", evidence_ids: [], verified_location: [], detail: null },
    ],
    assessments: [
      { evidence_id: QURAN_EVIDENCE.evidence_id, relationship: "supports", claim_component: null, component_id: "q1", evidence_span: null, supported_part: null, unsupported_part: null, rationale: "x", assessed_by: "deterministic", strength: { observations: [{ signal: "traceability", basis: "b" }] } },
      { evidence_id: TAFSIR_EVIDENCE.evidence_id, relationship: "supports", claim_component: null, component_id: "s1", evidence_span: "لا تأخذه سِنَة أي: نعاس.", supported_part: null, unsupported_part: null, rationale: "The passage explains that it means slumber.", assessed_by: "llm_analysis", strength: { observations: [{ signal: "source_suitability", basis: "b" }, { signal: "directness", basis: "b" }, { signal: "traceability", basis: "b" }] } },
      { evidence_id: IBN_KATHIR_EVIDENCE.evidence_id, relationship: "supports", claim_component: null, component_id: "s1", evidence_span: "لا يغلبه نعاس ولا نوم", supported_part: null, unsupported_part: null, rationale: "English rationale", assessed_by: "llm_analysis", strength: { observations: [] } },
    ],
    related_unverified_addresses: [],
    evidence_conflicts: [],
  },
};

describe("result wording is plain Arabic built only from the actual result", () => {
  it("supported tafsir: evidence lines and indicators match the real relationships", () => {
    const lines = evidenceSummary(supportedTafsir);
    expect(lines.map((l) => l.source)).toEqual(["القرآن الكريم (سورة البقرة، الآية 255)", "التفسير الميسر", "تفسير ابن كثير"]);
    expect(lines[0].text).toBe("نص الآية موثّق في المصحف: سورة البقرة، الآية 255.");
    expect(lines[1].text).toBe("يؤيد «أن الله لا يأخذه نعاس ولا نوم».");
    const ind = verificationIndicators(supportedTafsir).map((i) => i.text);
    expect(ind).toContain("نص الآية موثّق في المصحف.");
    expect(ind).toContain("المعنى مؤيد في أكثر من مصدر من مصادر التفسير: التفسير الميسر، تفسير ابن كثير.");
    expect(ind).toContain("لم يظهر في المصادر التي فُحصت ما يخالف الادعاء.");
    // The LLM rationale never reaches the user.
    expect(JSON.stringify([lines, ind])).not.toMatch(/passage|English|rationale/i);
  });

  it("contradicted Quran location: states the documented location, no invented support", () => {
    const o = contradicted();
    const ind = verificationIndicators(o);
    expect(ind).toContainEqual({ ok: true, text: "نص الآية موثّق في المصحف." });
    expect(ind).toContainEqual({ ok: false, text: "الموضع المذكور لا يطابق المصحف؛ الموضع الموثّق: سورة البقرة، الآية 158." });
    expect(ind.map((i) => i.text)).not.toContain("لم يظهر في المصادر التي فُحصت ما يخالف الادعاء.");
  });

  it("conflicting: both sides are named from the actual evidence", () => {
    const ind = verificationIndicators(conflicting).map((i) => i.text);
    expect(ind).toContain("المعنى مؤيد في التفسير الميسر.");
    expect(ind).toContain("يوجد في تفسير ابن كثير ما يخالف ذلك.");
  });

  it("no evidence: nothing is claimed", () => {
    expect(verificationIndicators(noEvidence)).toEqual([]);
    expect(evidenceSummary(noEvidence)).toEqual([]);
  });

  it("per-evidence indicators come only from signals the backend recorded", () => {
    const [, tafsirA, ikA] = supportedTafsir.analysis.assessments;
    expect(evidenceIndicators(tafsirA).map((i) => i.text)).toEqual([
      "المصدر معتمد ومختص بهذا النوع من الادعاءات.",
      "النص يتناول هذا الجزء من الادعاء مباشرة.",
      "النص منقول كما هو من سجل المصدر الرسمي.",
    ]);
    expect(evidenceIndicators(ikA)).toEqual([]);
    expect(explainAssessment({ ...tafsirA, relationship: "insufficient" }, TAFSIR_EVIDENCE, supportedTafsir.analysis.components)).toBe(
      "نص التفسير الميسر ذو صلة بـ«أن الله لا يأخذه نعاس ولا نوم»، لكنه لا يكفي لإثباته.",
    );
  });
});
