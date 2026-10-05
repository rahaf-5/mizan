"""Claim Classification (Task 5a).

LLM-assisted (Gemini via the provider-neutral abstraction): suggests the claim type(s)
and ayah RETRIEVAL HINTS. Deterministic rules then:
  * add `hadith` when the claim explicitly attributes words to the Prophet ﷺ or cites a
    hadith (conservative: a hadith-requiring claim must never be verified without Hadith
    evidence — it abstains while Dorar is unavailable);
  * add `hadith` when the user's content quotes a hadith as its evidence;
  * source boundary: text quoted under an explicit Quran attribution ("قال تعالى: «…»",
    "﴿…﴾") is the claimed ayah wording, not a hadith. It is excluded from hadith detection,
    and an LLM-suggested `hadith` type is dropped ONLY when nothing outside those quotes
    mentions the Prophet ﷺ, a hadith or a hadith collection (genuine and composite hadith
    claims keep their hadith requirement and still abstain while Dorar is unavailable);
  * map "no supported type" to Out of Scope (unsupported_claim_category).
Hints are passed on unvalidated; retrieval validates each against the official Quran.
"""

from __future__ import annotations

import re

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


#: Explicit attribution of quoted words to Allah / the Quran (normalised).
_QURAN_ATTRIBUTIONS = tuple(
    normalize_for_matching(m)
    for m in (
        "قال تعالى",
        "قال الله",
        "قال سبحانه",
        "قال عز وجل",
        "يقول تعالى",
        "يقول الله",
        "يقول سبحانه",
        "قوله تعالى",
        "قوله سبحانه",
        "قول الله",
        "قال ربنا",
        "في كتابه",
        "في القران",
        "في القرآن",
        "الآية الكريمة",
    )
)

#: Words that mention the Prophet ﷺ, a hadith or a hadith collection (normalised; ﷺ is
#: expanded by NFKC). Used only on text OUTSIDE Quran-attributed quotes, and only to decide
#: whether an LLM-suggested hadith type is incidental — never to drop a marker-based signal.
_HADITH_MENTIONS = tuple(
    normalize_for_matching(m)
    for m in (
        "النبي",
        "نبينا",
        "الرسول",
        "رسول الله",
        "المصطفى",
        "صلى الله عليه وسلم",
        "عليه الصلاة والسلام",
        "حديث",
        "الحديث",
        "احاديث",
        "السنة النبوية",
        "رواه",
        "البخاري",
        "صحيح مسلم",
        "سنن",
        "مسند",
    )
)

_QUOTE = re.compile(r"«[^»]*»|﴿[^﴾]*﴾|“[^”]*”|\"[^\"]*\"")
_SENTENCE_END = re.compile(r"[.!؟?\n]")
_ATTRIBUTION_WINDOW = 80  # characters before a quote searched for its attribution


def _contains(norm_text: str, phrases: tuple[str, ...]) -> bool:
    padded = f" {norm_text} "
    return any(f" {p} " in padded or f" و{p} " in padded for p in phrases)


def split_quran_attributed_quotes(text: str) -> tuple[list[str], str]:
    """Return (Quran-attributed quotes, the rest of the text with those quotes removed).

    A quote is Quran-attributed when it uses ayah brackets ﴿…﴾ or when an explicit
    attribution ("قال تعالى", "قوله تعالى", …) precedes it in the same sentence, after the
    previous quote. Pure text analysis: the quoted words themselves are not trusted to
    influence routing.
    """
    quotes: list[str] = []
    rest: list[str] = []
    pos = 0
    for m in _QUOTE.finditer(text):
        before = text[pos : m.start()]
        window = before[-_ATTRIBUTION_WINDOW:]
        ends = list(_SENTENCE_END.finditer(window))
        if ends:
            window = window[ends[-1].end() :]
        attributed = m.group().startswith("﴿") or _contains(
            normalize_for_matching(window), _QURAN_ATTRIBUTIONS
        )
        rest.append(before)
        if attributed:
            quotes.append(m.group())
            rest.append(" ")
        else:
            rest.append(m.group())
        pos = m.end()
    rest.append(text[pos:])
    return quotes, "".join(rest)


def mentions_hadith(text: str) -> bool:
    return _contains(normalize_for_matching(text), _HADITH_MENTIONS)


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
        quran_quotes, outside_quran_quotes = split_quran_attributed_quotes(
            claim.confirmed_claim_text
        )
        if hadith_signal(outside_quran_quotes):
            signals.append("hadith_attribution_marker")
        if pe and pe.provided_evidence_type == ProvidedEvidenceType.HADITH:
            signals.append("user_cited_hadith")
        if signals and ClaimType.HADITH not in types:
            types.append(ClaimType.HADITH)
        elif (
            quran_quotes
            and ClaimType.HADITH in types
            and not signals
            and not mentions_hadith(outside_quran_quotes)
        ):
            # Explicit Quran attribution takes precedence over incidental words inside the
            # quoted ayah wording (e.g. «النبي»): the quote is a Quran claim, not a hadith.
            types = [t for t in types if t != ClaimType.HADITH] or [ClaimType.QURAN]
            signals.append("explicit_quran_attribution")
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


__all__ = [
    "LlmClaimClassifier",
    "hadith_signal",
    "mentions_hadith",
    "split_quran_attributed_quotes",
]
