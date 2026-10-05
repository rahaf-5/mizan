import { describe, expect, it } from "vitest";
import { partialBreakdown } from "@/lib/verify/presentation";
import type { Evidence, VerificationOutcome } from "@/lib/verify/types";
import { QURAN_EVIDENCE, contradicted, supported } from "../fixtures/outcomes";

const WAHIDI: Evidence = {
  ...QURAN_EVIDENCE,
  evidence_id: "mizan-ev:asbab:2:158",
  source_type: "asbab_nuzul",
  source_name: "أسباب النزول للواحدي",
  trusted_source_id: "asbab_al_nuzul_al_wahidi",
  reference: "أسباب نزول القرآن - الواحدي، الجزء 1، الصفحة 47 — سورة البقرة، الآية 158",
  text: "نزلت في الأنصار، كانوا يحجون لمناة",
};

// Shapes and texts from REAL /verify results on 2026-10-05 (live Gemini + Quranpedia).
const ASBAB = "نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في الأنصار، وكان ذلك في السنة الأولى من الهجرة";
const asbab: VerificationOutcome = {
  ...contradicted("p1", ASBAB),
  status: "partially_supported",
  result_group: "needs_revision",
  verified_reference: null,
  evidence: [QURAN_EVIDENCE, WAHIDI],
  analysis: {
    components: [
      { component_id: "q1", text: "إن الصفا والمروة من شعائر الله", kind: "quran_quote", role: "anchor", claim_type: "quran", outcome: "supported", evidence_ids: [QURAN_EVIDENCE.evidence_id], verified_location: [], detail: null },
      { component_id: "s1", text: "نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في الأنصار،", kind: "statement", role: "substantive", claim_type: "asbab_nuzul", outcome: "supported", evidence_ids: [WAHIDI.evidence_id], verified_location: [], detail: null },
      { component_id: "s2", text: "وكان ذلك في السنة الأولى من الهجرة", kind: "statement", role: "substantive", claim_type: "asbab_nuzul", outcome: "insufficient", evidence_ids: [WAHIDI.evidence_id], verified_location: [], detail: null },
    ],
    assessments: [
      { evidence_id: QURAN_EVIDENCE.evidence_id, relationship: "supports", claim_component: null, component_id: "q1", evidence_span: "x", supported_part: null, unsupported_part: null, rationale: "", assessed_by: "deterministic", strength: { observations: [] } },
      { evidence_id: WAHIDI.evidence_id, relationship: "supports", claim_component: null, component_id: "s1", evidence_span: "نزلت في الأنصار", supported_part: null, unsupported_part: null, rationale: "", assessed_by: "llm_analysis", strength: { observations: [] } },
      { evidence_id: WAHIDI.evidence_id, relationship: "insufficient", claim_component: null, component_id: "s2", evidence_span: null, supported_part: null, unsupported_part: null, rationale: "", assessed_by: "llm_analysis", strength: { observations: [] } },
    ],
    related_unverified_addresses: [],
    evidence_conflicts: [],
  },
};

const QUOTE = "قال تعالى: «إن الله مع الصابرين والمتقين والمحسنين»";
const quote = (sup: string, unsup: string): VerificationOutcome => ({
  ...contradicted("p2", QUOTE),
  status: "partially_supported",
  verified_reference: null,
  analysis: {
    components: [{ component_id: "q1", text: "إن الله مع الصابرين والمتقين والمحسنين", kind: "quran_quote", role: "substantive", claim_type: "quran", outcome: "partially_supported", evidence_ids: [QURAN_EVIDENCE.evidence_id], verified_location: [], detail: null }],
    assessments: [{ evidence_id: QURAN_EVIDENCE.evidence_id, relationship: "partially_supports", claim_component: null, component_id: "q1", evidence_span: "x", supported_part: sup, unsupported_part: unsup, rationale: "", assessed_by: "deterministic", strength: { observations: [] } }],
    related_unverified_addresses: [],
    evidence_conflicts: [],
  },
});

describe("partially supported: the two parts come only from the verification result", () => {
  it("component split (real asbab result): supported component vs. component not established", () => {
    expect(partialBreakdown(asbab)).toEqual({
      supported: ["نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في الأنصار"],
      unproven: ["وكان ذلك في السنة الأولى من الهجرة"],
      sources: ["أسباب النزول للواحدي (عند سورة البقرة، الآية 158)"],
    });
  });

  it("partial quote: uses the backend's supported/unsupported parts (verbatim from the claim)", () => {
    expect(partialBreakdown(quote("إن الله مع الصابرين", "والمتقين والمحسنين"))).toEqual({
      supported: ["إن الله مع الصابرين"],
      unproven: ["والمتقين والمحسنين"],
      sources: ["المصحف (سورة البقرة، الآية 158)"],
    });
  });

  it("never shows parts that are not the user's exact words (e.g. a normalised key) — falls back", () => {
    expect(partialBreakdown(quote("ان الله مع الصابرين", "والمتقين والمحسنين"))).toBeNull();
    expect(partialBreakdown(quote("الله مع الذين صبروا", "والمحسنين"))).toBeNull();
  });

  it("only for partially_supported", () => {
    expect(partialBreakdown(supported("s", "أ"))).toBeNull();
    expect(partialBreakdown(contradicted())).toBeNull();
  });
});
