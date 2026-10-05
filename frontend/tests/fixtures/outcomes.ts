/**
 * Response shapes of POST /api/v1/verify (backend contract), for UI tests ONLY.
 * Values are illustrative but structurally identical to what the backend returns.
 */
import type {
  ClaimOutcome,
  Evidence,
  FinalUserResult,
  VerificationOutcome,
} from "@/lib/verify/types";

export const QURAN_EVIDENCE: Evidence = {
  evidence_id: "mizan-ev:quran:1:165",
  source_type: "quran",
  text: "إِنَّ الصَّفَا وَالْمَرْوَةَ مِنْ شَعَائِرِ اللَّهِ",
  source_name: "القرآن الكريم",
  provider: "quranpedia",
  trusted_source_id: "quran",
  reference: "سورة البقرة، الآية 158",
  source_address: "/v1/mushafs/1/2/158",
  source_url: "https://api.quranpedia.net/v1/mushafs/1/2/158",
  source_record_id: "165",
  retrieval_channel: "official_dump",
  source_version: "2026-10-04",
  retrieved_at: "2026-10-05T10:00:00Z",
  text_sha256: "a".repeat(64),
  metadata: {},
};

export const contradicted = (claimId = "c1", text = "قال تعالى في سورة آل عمران: «إن الصفا والمروة من شعائر الله»"): VerificationOutcome => ({
  kind: "verification",
  claim_id: claimId,
  confirmed_claim_text: text,
  status: "contradicted",
  result_group: "do_not_use_as_written",
  why: "«سورة آل عمران» يخالفه القرآن الكريم. الموضع الصحيح الموثّق: سورة البقرة، الآية 158.",
  what_to_do: "لا تنشر الادعاء بصيغته الحالية.",
  evidence: [QURAN_EVIDENCE],
  analysis: {
    components: [
      { component_id: "q1", text: "إن الصفا والمروة من شعائر الله", kind: "quran_quote", role: "substantive", claim_type: "quran", outcome: "supported", evidence_ids: [QURAN_EVIDENCE.evidence_id], verified_location: [], detail: null },
      { component_id: "loc1", text: "سورة آل عمران", kind: "quran_location", role: "substantive", claim_type: "quran", outcome: "contradicted", evidence_ids: [QURAN_EVIDENCE.evidence_id], verified_location: [], detail: "الموضع الصحيح الموثّق: سورة البقرة، الآية 158" },
    ],
    assessments: [
      { evidence_id: QURAN_EVIDENCE.evidence_id, relationship: "contradicts", claim_component: "سورة آل عمران", component_id: "loc1", evidence_span: "ان الصفا والمروه من شعائر الله", supported_part: null, unsupported_part: null, rationale: "النص موجود في سورة البقرة، الآية 158، وليس في الموضع المذكور في الادعاء.", assessed_by: "deterministic", strength: { observations: [{ signal: "traceability", basis: "له عنوان رسمي لدى المزوّد وبصمة تطابق النص المعروض." }] } },
    ],
    related_unverified_addresses: [],
    evidence_conflicts: [],
  },
  validation: { outcome: "pass" },
});

export const supported = (claimId: string, text: string): VerificationOutcome => ({
  ...contradicted(claimId, text),
  status: "supported",
  result_group: "verified",
  why: "«...» يثبته نص صريح في القرآن الكريم.",
  what_to_do: "يمكنك استخدام الادعاء بصيغته الحالية.",
});

export const TAFSIR_EVIDENCE: Evidence = {
  ...QURAN_EVIDENCE,
  evidence_id: "mizan-ev:tafsir:2:255:abc",
  source_type: "tafsir",
  text: "الله الذي لا يستحق الألوهية إلا هو… لا تأخذه سِنَة أي: نعاس.",
  source_name: "التفسير الميسر",
  trusted_source_id: "tafsir_al_muyassar",
  reference: "التفسير الميسر — سورة البقرة، الآية 255",
  source_address: "/v1/ayah/2/255/book/2012",
  source_url: "https://api.quranpedia.net/v1/ayah/2/255/book/2012",
  source_record_id: null,
  retrieval_channel: "live_api",
  source_version: null,
  metadata: { provider_author: "مجمع الملك فهد لطباعة المصحف الشريف", page_kind: "none" },
};

export const conflicting: VerificationOutcome = {
  ...contradicted("c3", "معنى «لا تأخذه سنة» كذا"),
  status: "conflicting_evidence",
  result_group: "needs_evidence_review",
  why: "بشأن «كذا»: يؤيده التفسير الميسر ويخالفه تفسير ابن كثير؛ فالأدلة المعتمدة متعارضة.",
  what_to_do: "راجع الأدلة المتعارضة المعروضة.",
  evidence: [TAFSIR_EVIDENCE],
  analysis: {
    components: [{ component_id: "s1", text: "كذا", kind: "statement", role: "substantive", claim_type: "tafsir", outcome: "conflicting", evidence_ids: [TAFSIR_EVIDENCE.evidence_id], verified_location: [], detail: null }],
    assessments: [
      { evidence_id: TAFSIR_EVIDENCE.evidence_id, relationship: "supports", claim_component: "كذا", component_id: "s1", evidence_span: "لا تأخذه سِنَة أي: نعاس.", supported_part: null, unsupported_part: null, rationale: "المقطع يذكر هذا المعنى صراحة.", assessed_by: "llm_analysis", strength: { observations: [] } },
    ],
    related_unverified_addresses: [],
    evidence_conflicts: [{ evidence_ids: ["x", "y"], description: "أدلة متعارضة" }],
  },
};

export const noEvidence: VerificationOutcome = {
  ...contradicted("c4", "قال تعالى: «وتعاونوا على الخير ففي ذلك الفلاح المبين»"),
  status: "no_evidence_found",
  result_group: "needs_evidence_review",
  why: "لم يتم العثور على دليل كافٍ للتحقق من الادعاء ضمن المصادر المعتمدة حاليًا في ميزان. عدم العثور على دليل لا يعني أن الادعاء خاطئ.",
  what_to_do: "لا تنشره على أنه حقيقة مؤكدة.",
  evidence: [],
  analysis: { components: [], assessments: [], related_unverified_addresses: ["/v1/mushafs/1/5/2"], evidence_conflicts: [] },
  validation: { outcome: "abstain" },
};

export const hadithUnavailable: ClaimOutcome = {
  kind: "required_source_unavailable",
  claim_id: "c5",
  confirmed_claim_text: "قال رسول الله ﷺ: «إنما الأعمال بالنيات»",
  required_claim_types: ["hadith"],
  unavailable_sources: ["dorar_hadith"],
  detail: null,
};

export const outOfScope: ClaimOutcome = { kind: "out_of_scope", claim_id: "c6", reason: "unsupported_claim_category", detail: null };

export const systemError: ClaimOutcome = {
  kind: "system_error",
  claim_id: "c7",
  error: { code: "verification_incomplete", stage: "hybrid_retrieval", message: "Verification could not be completed reliably", retryable: true },
};

export const finalResult = (outcome: ClaimOutcome, runId = "run-1"): FinalUserResult => ({
  run_id: runId,
  created_at: "2026-10-05T10:00:00Z",
  outcomes: [outcome],
  limitations: [],
});
