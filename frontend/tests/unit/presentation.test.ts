import { describe, expect, it } from "vitest";
import { evidencePreview, evidenceQuote } from "@/lib/verify/presentation";
import type { VerificationOutcome } from "@/lib/verify/types";
import { IBN_KATHIR_EVIDENCE, QURAN_EVIDENCE, TAFSIR_EVIDENCE, conflicting, contradicted, noEvidence } from "../fixtures/outcomes";

describe("evidence preview and details come only from the evidence records", () => {
  it("preview = source — place, place taken from the record's own reference, no duplicates", () => {
    const o: VerificationOutcome = { ...conflicting, evidence: [QURAN_EVIDENCE, TAFSIR_EVIDENCE, IBN_KATHIR_EVIDENCE, TAFSIR_EVIDENCE] };
    expect(evidencePreview(o).map((p) => `${p.source} — ${p.place}`)).toEqual([
      "القرآن الكريم — سورة البقرة، الآية 158",
      "التفسير الميسر — سورة البقرة، الآية 255",
      "تفسير ابن كثير — سورة البقرة، الآية 255",
    ]);
    expect(evidencePreview(noEvidence)).toEqual([]);
  });

  it("quote = the verbatim cited passage when it occurs in the record, else the record's text", () => {
    expect(evidenceQuote(TAFSIR_EVIDENCE, conflicting.analysis.assessments)).toEqual({ text: "لا تأخذه سِنَة أي: نعاس.", cited: true });
    // A normalised matching key is not verbatim → the ayah text itself is shown.
    expect(evidenceQuote(QURAN_EVIDENCE, contradicted().analysis.assessments)).toEqual({ text: QURAN_EVIDENCE.text, cited: false });
  });
});
