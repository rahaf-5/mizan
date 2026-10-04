"""Claim Extraction stage (spec §3, §11) — LLM-assisted, provider-neutral.

Extraction is NOT verification. The stage:
  * sends only the submitted text (wrapped as untrusted data) to the configured LLM provider;
  * strictly validates the structured output (LLMOutput schema);
  * keeps only claims GROUNDED in the content (verbatim excerpt match after normalisation),
    so the model cannot introduce claims that were not present;
  * returns claims in `pending` confirmation status — they cannot reach verification until the
    user explicitly confirms them (domain gate `confirm_for_verification`).
Provider failures propagate as MizanError subclasses; nothing is fabricated.
"""

from __future__ import annotations

from app.core_logging import get_logger
from app.domain.claim import Claim, ProvidedEvidence
from app.domain.enums import PipelineStage, UserConfirmationStatus
from app.domain.errors import MizanError
from app.domain.inputs import ExtractionInput
from app.llm.base import LLMProvider, LLMRequest
from app.llm.prompts.claim_extraction import build_prompt
from app.llm.schemas import ClaimExtractionDraft, ExtractedClaimDraft, LLMTask
from app.pipeline.arabic_text import normalize_for_matching
from app.pipeline.contracts import ClaimExtractionResult

log = get_logger("pipeline.claim_extraction")
MAX_CLAIMS = 50


def _grounded(draft: ExtractedClaimDraft, normalized_content: str) -> bool:
    excerpt = normalize_for_matching(draft.source_excerpt)
    return bool(excerpt) and excerpt in normalized_content


class LlmClaimExtractor:
    """Implements pipeline.contracts.ClaimExtractor using any LLMProvider."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def extract(self, data: ExtractionInput) -> ClaimExtractionResult:
        system_prompt, user_content = build_prompt(data.text)
        request = LLMRequest(
            task=LLMTask.CLAIM_EXTRACTION, system_prompt=system_prompt, user_content=user_content
        )
        try:
            draft = await self._provider.generate_structured(request, ClaimExtractionDraft)
        except MizanError as exc:
            if exc.stage is None:
                exc.stage = PipelineStage.CLAIM_EXTRACTION
            raise

        normalized_content = normalize_for_matching(data.text)
        claims: list[Claim] = []
        seen: set[str] = set()
        ungrounded = duplicates = 0
        for d in draft.claims:
            if not d.extracted_claim_text.strip():
                continue
            if not _grounded(d, normalized_content):
                ungrounded += 1
                continue
            key = normalize_for_matching(d.extracted_claim_text)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            evidence = None
            if (
                d.provided_evidence_type
                and d.provided_evidence_text
                and d.provided_evidence_text.strip()
            ):
                evidence = ProvidedEvidence(
                    provided_evidence_type=d.provided_evidence_type,
                    provided_evidence_text=d.provided_evidence_text,
                )
            claims.append(
                Claim(
                    original_text=d.source_excerpt,
                    extracted_claim_text=d.extracted_claim_text.strip(),
                    extraction_status=d.extraction_status,
                    provided_evidence=evidence,
                    provided_reference=(d.user_written_reference or None),
                    user_confirmation_status=UserConfirmationStatus.PENDING,
                    selected_for_verification=True,
                )
            )
            if len(claims) >= MAX_CLAIMS:
                break

        log.info(
            "claim extraction: provider=%s input_chars=%d returned=%d kept=%d ungrounded=%d dup=%d",
            self._provider.name,
            len(data.text),
            len(draft.claims),
            len(claims),
            ungrounded,
            duplicates,
        )
        return ClaimExtractionResult(
            claims=claims,
            suggest_full_content_check=False,
            discarded_ungrounded_count=ungrounded,
        )


__all__ = ["LlmClaimExtractor"]
