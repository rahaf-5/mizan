"""Final Validation Gate (Task 5b) — deterministic; creates no evidence.

Runs the seven spec checks. Approved rule (2026-10-04): an INTEGRITY failure (traceability,
fingerprint, unapproved/unqualified source, invalid span, status recomputation mismatch,
corrupted evidence association, ...) is never mapped to an evidentiary status. The gate
returns RETRY(integrity_failure / technical_failure); when the bounded retries are exhausted the
orchestrator ends the claim as system_error(verification_incomplete) — fail closed.

ABSTAIN is used only for a correctly completed verification whose limitation is evidentiary
(weak retrieval: no qualified candidate) — mapped to the SAME evidentiary status.
"""

from __future__ import annotations

from app.domain.claim import ClassifiedClaim
from app.domain.enums import (
    ClaimType,
    ComponentKind,
    RetrievalMatchBasis,
    RetryReason,
    ValidationOutcome,
)
from app.domain.enums import EvidenceRelationship as R
from app.domain.enums import ValidationCheck as V
from app.domain.enums import VerificationStatus as S
from app.domain.evidence import text_fingerprint
from app.domain.retrieval import RetrievalResult
from app.domain.trusted_sources import get_trusted_source
from app.domain.validation import FinalValidationResult, ValidationCheckResult
from app.domain.verification import AnalysisResult, StatusDetermination
from app.pipeline.analysis import component_outcome, status_from_outcomes
from app.pipeline.passage_analysis import is_claim_span, occurs_in

_STRONG = {
    RetrievalMatchBasis.QUOTED_TEXT,
    RetrievalMatchBasis.EXPLICIT_REFERENCE,
    RetrievalMatchBasis.RETRIEVAL_HINT,
}


class TrustedValidationGate:
    async def validate(
        self,
        claim: ClassifiedClaim,
        retrieval: RetrievalResult,
        analysis: AnalysisResult,
        determination: StatusDetermination,
        *,
        retry_count: int,
        retries_remaining: int,
    ) -> FinalValidationResult:
        if retrieval.has_failed_attempts:
            return FinalValidationResult(
                claim_id=claim.claim_id,
                outcome=ValidationOutcome.RETRY,
                retry_count=retry_count,
                retry_reason=RetryReason.TECHNICAL_FAILURE,
            )
        problems = {c: [] for c in V}
        cands = {c.evidence.evidence_id: c for c in retrieval.candidates}
        comps = {c.component_id: c for c in analysis.components}
        provided = (
            claim.provided_evidence.provided_evidence_text.strip()
            if claim.provided_evidence
            else None
        )

        # 1. confirmed claim text
        if analysis.claim_id != claim.claim_id or determination.claim_id != claim.claim_id:
            problems[V.USES_CONFIRMED_CLAIM_TEXT].append("analysis belongs to another claim")
        for c in analysis.components:
            if not (is_claim_span(c.text, claim.confirmed_claim_text) or c.text == provided):
                problems[V.USES_CONFIRMED_CLAIM_TEXT].append(f"{c.component_id} not in claim")

        for a in analysis.assessments:
            comp = comps.get(a.component_id or "")
            cand = cands.get(a.evidence_id)
            # 2. relates to the claim (known component, retrieved evidence)
            if comp is None or cand is None:
                problems[V.EVIDENCE_RELATES_TO_CLAIM].append(
                    f"{a.evidence_id}: unknown association"
                )
                continue
            ev = cand.evidence
            # 3. approved, available, qualified (Source Boundary), qualified retrieval basis
            src = get_trusted_source(ev.trusted_source_id)
            if not src.is_available or comp.claim_type not in src.qualified_for:
                problems[V.SOURCE_APPROVED_AND_QUALIFIED].append(f"{a.evidence_id}: not qualified")
            if cand.retrieval.match_basis not in _STRONG:
                problems[V.SOURCE_APPROVED_AND_QUALIFIED].append(f"{a.evidence_id}: keyword-only")
            # 4. traceable
            if not ev.source_address or ev.text_sha256 != text_fingerprint(ev.text):
                problems[V.EVIDENCE_TRACEABLE].append(f"{a.evidence_id}: traceability broken")
            # 5. references from verified metadata + verbatim spans
            if not ev.reference.strip():
                problems[V.REFERENCES_FROM_VERIFIED_METADATA].append(f"{a.evidence_id}: no ref")
            min_words = 3 if a.assessed_by == "llm_analysis" else 1
            if a.relationship != R.INSUFFICIENT or a.evidence_span:
                if not a.evidence_span or not occurs_in(
                    a.evidence_span, ev.text, min_words=min_words
                ):
                    problems[V.REFERENCES_FROM_VERIFIED_METADATA].append(
                        f"{a.evidence_id}/{a.component_id}: span not in evidence text"
                    )
            # 7a. who may judge what
            llm_on_quran = a.assessed_by == "llm_analysis" and comp.claim_type == ClaimType.QURAN
            rule_on_text = a.assessed_by == "deterministic" and comp.kind == ComponentKind.STATEMENT
            if llm_on_quran or rule_on_text:
                problems[V.WORDING_NOT_STRONGER_THAN_EVIDENCE].append(
                    f"{a.component_id}: wrong judge"
                )
        for c in analysis.components:
            for e in c.evidence_ids:
                if e not in cands:
                    problems[V.EVIDENCE_RELATES_TO_CLAIM].append(f"{c.component_id}: unknown {e}")

        # 6. status recomputation
        for c in analysis.components:
            mine = [a for a in analysis.assessments if a.component_id == c.component_id]
            if c.outcome != component_outcome(mine):
                problems[V.STATUS_MATCHES_EVIDENCE].append(f"{c.component_id}: outcome mismatch")
        expected = status_from_outcomes([c.outcome for c in analysis.components if c.outcome])
        if expected != determination.status:
            problems[V.STATUS_MATCHES_EVIDENCE].append(
                f"status {determination.status.value} != recomputed {expected.value}"
            )

        # 7b. wording not stronger than the evidence
        status = determination.status
        if status == S.SUPPORTED:
            for c in analysis.components:
                rels = [
                    a
                    for a in analysis.assessments
                    if a.component_id == c.component_id and a.relationship == R.SUPPORTS
                ]
                if not rels:
                    problems[V.WORDING_NOT_STRONGER_THAN_EVIDENCE].append(
                        f"{c.component_id}: supported without a supporting span"
                    )
        if status == S.CONTRADICTED and not any(
            a.relationship == R.CONTRADICTS and a.evidence_span for a in analysis.assessments
        ):
            problems[V.WORDING_NOT_STRONGER_THAN_EVIDENCE].append("contradicted without evidence")

        checks = [
            ValidationCheckResult(
                check=c, passed=not problems[c], detail="; ".join(problems[c][:5]) or None
            )
            for c in V
        ]
        if any(not r.passed for r in checks):
            return FinalValidationResult(
                claim_id=claim.claim_id,
                outcome=ValidationOutcome.RETRY,
                checks=checks,
                retry_count=retry_count,
                retry_reason=RetryReason.INTEGRITY_FAILURE,
            )
        if retrieval.insufficient_retrieval and status in (
            S.NO_EVIDENCE_FOUND,
            S.INSUFFICIENT_EVIDENCE,
        ):
            return FinalValidationResult(
                claim_id=claim.claim_id,
                outcome=ValidationOutcome.ABSTAIN,
                checks=checks,
                retry_count=retry_count,
                abstained_to=status,
            )
        return FinalValidationResult(
            claim_id=claim.claim_id,
            outcome=ValidationOutcome.PASS,
            checks=checks,
            retry_count=retry_count,
        )
