"""Evidence Analysis + Verification Status (Task 5b) — fully deterministic.

Per component (from its validated assessments):
  supports/partial AND contradicts (different evidence) -> conflicting
  contradicts                                         -> contradicted
  supports                                            -> supported
  partially_supports                                  -> partially_supported
  insufficient only                                   -> insufficient
  nothing                                             -> not_established
Claim status — computed from SUBSTANTIVE components only (anchors such as the quoted ayah of a
tafsir/asbab claim never upgrade it; a contradicted anchor makes the claim contradicted).
In this order (approved 2026-10-04):
  any conflicting                      -> conflicting_evidence
  any contradicted                     -> contradicted   (component details are preserved)
  all supported                        -> supported
  any supported / partially supported  -> partially_supported
  any insufficient                     -> insufficient_evidence
  otherwise                            -> no_evidence_found
Evidence Analysis never creates evidence and never uses an LLM.
"""

from __future__ import annotations

from app.domain.claim import ClassifiedClaim
from app.domain.enums import ComponentOutcome as O
from app.domain.enums import ComponentRole
from app.domain.enums import EvidenceRelationship as R
from app.domain.enums import VerificationStatus as S
from app.domain.retrieval import RetrievalResult
from app.domain.verification import (
    AnalysisResult,
    ComponentFinding,
    EvidenceAssessment,
    EvidenceConflict,
    StatusDetermination,
    VerificationFindings,
)


def component_outcome(assessments: list[EvidenceAssessment]) -> O:
    rels = {a.relationship for a in assessments}
    positive = bool(rels & {R.SUPPORTS, R.PARTIALLY_SUPPORTS})
    if positive and R.CONTRADICTS in rels:
        return O.CONFLICTING
    if R.CONTRADICTS in rels:
        return O.CONTRADICTED
    if R.SUPPORTS in rels:
        return O.SUPPORTED
    if R.PARTIALLY_SUPPORTS in rels:
        return O.PARTIALLY_SUPPORTED
    if R.INSUFFICIENT in rels:
        return O.INSUFFICIENT
    return O.NOT_ESTABLISHED


def status_from_outcomes(outcomes: list[O]) -> S:
    if not outcomes or all(o == O.NOT_ESTABLISHED for o in outcomes):
        return S.NO_EVIDENCE_FOUND
    if O.CONFLICTING in outcomes:
        return S.CONFLICTING_EVIDENCE
    if O.CONTRADICTED in outcomes:
        return S.CONTRADICTED
    if all(o == O.SUPPORTED for o in outcomes):
        return S.SUPPORTED
    if any(o in (O.SUPPORTED, O.PARTIALLY_SUPPORTED) for o in outcomes):
        return S.PARTIALLY_SUPPORTED
    if O.INSUFFICIENT in outcomes:
        return S.INSUFFICIENT_EVIDENCE
    return S.NO_EVIDENCE_FOUND


def status_from_components(components) -> S:  # type: ignore[no-untyped-def]
    """Status from SUBSTANTIVE components; anchors never upgrade it.

    A verified anchor (e.g. the quoted ayah of a tafsir claim) is context only. A CONTRADICTED
    anchor is a directly contradicted statement in the claim, so the claim is contradicted.
    """
    substantive = [
        c.outcome for c in components if c.outcome and c.role == ComponentRole.SUBSTANTIVE
    ]
    anchors = [c.outcome for c in components if c.outcome and c.role == ComponentRole.ANCHOR]
    status = status_from_outcomes(substantive)
    if O.CONTRADICTED in anchors and status not in (S.CONFLICTING_EVIDENCE, S.CONTRADICTED):
        return S.CONTRADICTED
    return status


class DeterministicEvidenceAnalyzer:
    async def analyze(
        self, claim: ClassifiedClaim, findings: VerificationFindings
    ) -> AnalysisResult:
        components = []
        supported, unsupported, contradicted, conflicts = [], [], [], []
        for comp in findings.components:
            mine = [a for a in findings.assessments if a.component_id == comp.component_id]
            outcome = component_outcome(mine)
            ids = sorted({a.evidence_id for a in mine})
            components.append(comp.model_copy(update={"outcome": outcome, "evidence_ids": ids}))
            finding = ComponentFinding(component_text=comp.text, evidence_ids=ids)
            if outcome == O.SUPPORTED:
                supported.append(finding)
            elif outcome == O.CONTRADICTED:
                contradicted.append(finding)
            elif outcome == O.CONFLICTING:
                pos = sorted(
                    {
                        a.evidence_id
                        for a in mine
                        if a.relationship in (R.SUPPORTS, R.PARTIALLY_SUPPORTS)
                    }
                )
                neg = sorted({a.evidence_id for a in mine if a.relationship == R.CONTRADICTS})
                conflicts.append(
                    EvidenceConflict(
                        evidence_ids=pos + neg,
                        description=f"أدلة معتمدة متعارضة بشأن: {comp.text}",
                    )
                )
            else:
                unsupported.append(finding)
        return AnalysisResult(
            claim_id=claim.claim_id,
            assessments=list(findings.assessments),
            supported_components=supported,
            unsupported_components=unsupported,
            contradicted_components=contradicted,
            evidence_conflicts=conflicts,
            components=components,
            related_unverified_addresses=list(findings.related_unverified_addresses),
        )


class DeterministicStatusDeterminer:
    async def determine(
        self, claim: ClassifiedClaim, analysis: AnalysisResult, retrieval: RetrievalResult
    ) -> StatusDetermination:
        status = status_from_components(analysis.components)
        basis = sorted(
            {
                e
                for c in analysis.components
                if c.role == ComponentRole.SUBSTANTIVE or c.outcome == O.CONTRADICTED
                for e in c.evidence_ids
            }
        )
        return StatusDetermination(
            claim_id=claim.claim_id,
            status=status,
            basis_evidence_ids=[] if status == S.NO_EVIDENCE_FOUND else basis,
        )
