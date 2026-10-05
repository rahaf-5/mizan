"""Alternative wording (Task 8, spec §15).

Offered only for `partially_supported` / `contradicted` results that have verified excerpts.
Gemini proposes ONE wording grounded in the verified findings; Mizan then runs it through the
FULL pipeline as a new claim. It is "verified" only if that re-verification ends `supported`.
No loops: one proposal per request.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.claim import ConfirmedClaim
from app.domain.enums import ComponentRole, EvidenceRelationship, UserConfirmationStatus
from app.domain.enums import VerificationStatus as S
from app.domain.inputs import MAX_CLAIM_CHARS
from app.domain.results import ClaimOutcome, VerificationOutcome
from app.llm.base import LLMProvider, LLMRequest
from app.llm.prompts.alternative_wording import build_prompt
from app.llm.schemas import AlternativeWordingDraft, LLMTask
from app.pipeline.arabic_text import normalize_for_matching
from app.pipeline.orchestrator import VerificationPipeline

ELIGIBLE = {S.PARTIALLY_SUPPORTED, S.CONTRADICTED}
_OUTCOME_AR = {
    "supported": "مثبت",
    "partially_supported": "مثبت جزئيًا",
    "contradicted": "مخالف للدليل",
    "conflicting": "الأدلة فيه متعارضة",
    "insufficient": "الأدلة غير كافية",
    "not_established": "غير مثبت",
}


def is_eligible(outcome: ClaimOutcome) -> bool:
    if not isinstance(outcome, VerificationOutcome) or outcome.status not in ELIGIBLE:
        return False
    return any(
        a.evidence_span and a.relationship != EvidenceRelationship.INSUFFICIENT
        for a in outcome.analysis.assessments
    )


@dataclass(frozen=True)
class AlternativeResult:
    proposed_text: str | None
    verified: bool
    outcome: ClaimOutcome | None


class AlternativeWordingService:
    def __init__(self, provider: LLMProvider, pipeline: VerificationPipeline) -> None:
        self._provider = provider
        self._pipeline = pipeline

    async def propose(
        self, claim: ConfirmedClaim, outcome: VerificationOutcome
    ) -> AlternativeResult:
        findings = []
        for c in outcome.analysis.components:
            role = " (سياق)" if c.role == ComponentRole.ANCHOR else ""
            line = f"«{c.text}»{role}: {_OUTCOME_AR.get(c.outcome.value if c.outcome else '', '-')}"
            if c.detail:
                line += f" — {c.detail}"
            findings.append(line)
        by_id = {e.evidence_id: e for e in outcome.evidence}
        excerpts = []
        for a in outcome.analysis.assessments:
            ev = by_id.get(a.evidence_id)
            if ev and a.evidence_span and a.relationship != EvidenceRelationship.INSUFFICIENT:
                excerpts.append(f"{ev.source_name} ({ev.reference}): «{a.evidence_span}»")
        system, user = build_prompt(claim.confirmed_claim_text, findings, excerpts)
        draft = await self._provider.generate_structured(
            LLMRequest(task=LLMTask.ALTERNATIVE_WORDING, system_prompt=system, user_content=user),
            AlternativeWordingDraft,
        )
        text = " ".join(draft.proposed_claim_text.split())
        if (
            not text
            or len(text) > MAX_CLAIM_CHARS
            or normalize_for_matching(text) == normalize_for_matching(claim.confirmed_claim_text)
        ):
            return AlternativeResult(proposed_text=None, verified=False, outcome=None)
        candidate = ConfirmedClaim(
            claim_id=f"{claim.claim_id}:alt",
            confirmed_claim_text=text,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED,
        )
        [result] = (await self._pipeline.run_confirmed([candidate])).outcomes
        verified = isinstance(result, VerificationOutcome) and result.status == S.SUPPORTED
        return AlternativeResult(proposed_text=text, verified=verified, outcome=result)
