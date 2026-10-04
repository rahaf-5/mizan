"""Claim Classification (Task 5a).

LLM-assisted (Gemini via the provider-neutral abstraction): suggests the claim type(s)
and ayah RETRIEVAL HINTS. Deterministic rules then:
  * add `hadith` when the claim explicitly attributes words to the Prophet ﷺ or cites a
    hadith (conservative: a hadith-requiring claim must never be verified without Hadith
    evidence — it abstains while Dorar is unavailable);
  * add `hadith` when the user's content quotes a hadith as its evidence;
  * map "no supported type" to Out of Scope (unsupported_claim_category).
Hints are passed on unvalidated; retrieval validates each against the official Quran.
"""

from __future__ import annotations

from app.core_logging import get_logger
from app.domain.claim import AyahRetrievalHint, ClassifiedClaim, ConfirmedClaim
from app.domain.enums import ClaimType, OutOfScopeReason, ProvidedEvidenceType
from app.domain.results import OutOfScopeOutcome
from app.llm.base import LLMProvider, LLMRequest
from app.llm.prompts.classification import build_prompt
from app.llm.schemas import ClassificationSuggestion, LLMTask
from app.pipeline.arabic_text import normalize_for_matching

log = get_logger("pipeline.classification")

#: Explicit hadith-attribution markers (normalised). Deliberately narrow: narrations of a
#: revelation event ("نزلت في ...") do NOT trigger it.
_HADITH_MARKERS = tuple(
    normalize_for_matching(m)
    for m in (
        "قال رسول الله",
        "قال النبي",
        "يقول رسول الله",
        "يقول النبي",
        "عن النبي صلى الله عليه وسلم قال",
        "عن رسول الله صلى الله عليه وسلم قال",
        "صلى الله عليه وسلم قال",
        "صلى الله عليه وسلم يقول",
        "في الحديث",
        "حديث صحيح",
        "حديث ضعيف",
        "حديث موضوع",
        "رواه البخاري",
        "رواه مسلم",
        "متفق عليه",
    )
)


def hadith_signal(text: str) -> bool:
    norm = f" {normalize_for_matching(text)} "
    return any(f"{lead}{m} " in norm for m in _HADITH_MARKERS for lead in (" ", " و", " ف"))


class LlmClaimClassifier:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def classify(self, claim: ConfirmedClaim) -> ClassifiedClaim | OutOfScopeOutcome:
        pe = claim.provided_evidence
        system, user = build_prompt(
            claim.confirmed_claim_text,
            quoted_text=pe.provided_evidence_text if pe else None,
            user_reference=claim.provided_reference,
        )
        suggestion = await self._provider.generate_structured(
            LLMRequest(
                task=LLMTask.CLASSIFICATION_ASSISTANCE, system_prompt=system, user_content=user
            ),
            ClassificationSuggestion,
        )
        types: list[ClaimType] = []
        for t in [suggestion.suggested_claim_type, *suggestion.additional_claim_types]:
            if t is not None and t not in types:
                types.append(t)
        signals: list[str] = []
        if hadith_signal(claim.confirmed_claim_text):
            signals.append("hadith_attribution_marker")
        if pe and pe.provided_evidence_type == ProvidedEvidenceType.HADITH:
            signals.append("user_cited_hadith")
        if signals and ClaimType.HADITH not in types:
            types.append(ClaimType.HADITH)
        if not types:
            return OutOfScopeOutcome(
                claim_id=claim.claim_id,
                reason=OutOfScopeReason.UNSUPPORTED_CLAIM_CATEGORY,
                detail="claim is not about Quran text, tafsir, asbab al-nuzul or hadith",
            )
        hints = [
            AyahRetrievalHint(
                surah_number=h.surah_number, ayah_start=h.ayah_start, ayah_end=h.ayah_end
            )
            for h in suggestion.ayah_hints[:10]
        ]
        log.info(
            "classified claim types=%s hints=%d signals=%s",
            [t.value for t in types],
            len(hints),
            signals,
        )
        return ClassifiedClaim(
            claim_id=claim.claim_id,
            confirmed_claim_text=claim.confirmed_claim_text,
            user_confirmation_status=claim.user_confirmation_status,
            provided_evidence=claim.provided_evidence,
            provided_reference=claim.provided_reference,
            claim_type=types[0],
            additional_claim_types=types[1:],
            retrieval_hints=hints,
            classification_signals=signals,
        )


__all__ = ["LlmClaimClassifier", "hadith_signal"]
