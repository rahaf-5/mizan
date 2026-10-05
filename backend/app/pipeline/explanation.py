"""Deterministic, claim-specific explanations (Task 7) — no LLM, traceable to evidence.

`why` names the exact claim components and the approved sources that support / contradict /
fail to establish them; `what_to_do` is the action for the status; `result_group` follows
spec §12 (contradicted -> do not use as written; partially supported -> needs revision;
insufficient / no evidence / conflicting -> needs evidence review). Nothing here is stronger
than the validated analysis it reads.
"""

from __future__ import annotations

from app.domain.enums import ComponentOutcome as O
from app.domain.enums import ComponentRole, EvidenceStrengthSignal, ResultGroup
from app.domain.enums import EvidenceRelationship as R
from app.domain.enums import VerificationStatus as S
from app.domain.evidence import Evidence
from app.domain.trusted_sources import get_trusted_source
from app.domain.verification import (
    AnalysisResult,
    EvidenceAssessment,
    EvidenceStrengthAssessment,
    StrengthSignalObservation,
)

GROUP = {
    S.SUPPORTED: ResultGroup.VERIFIED,
    S.CONTRADICTED: ResultGroup.DO_NOT_USE_AS_WRITTEN,
    S.PARTIALLY_SUPPORTED: ResultGroup.NEEDS_REVISION,
    S.INSUFFICIENT_EVIDENCE: ResultGroup.NEEDS_EVIDENCE_REVIEW,
    S.NO_EVIDENCE_FOUND: ResultGroup.NEEDS_EVIDENCE_REVIEW,
    S.CONFLICTING_EVIDENCE: ResultGroup.NEEDS_EVIDENCE_REVIEW,
}

WHAT_TO_DO = {
    S.SUPPORTED: "يمكنك استخدام الادعاء بصيغته الحالية مع ذكر المصدر والمرجع المعروضين.",
    S.CONTRADICTED: (
        "لا تنشر الادعاء بصيغته الحالية: صحّح الجزء المخالف أو احذفه، ويمكنك طلب صياغة بديلة "
        "يعيد ميزان التحقق منها."
    ),
    S.PARTIALLY_SUPPORTED: (
        "عدّل الجزء غير المثبت أو احذفه قبل النشر، أو اطلب صياغة بديلة يعيد ميزان التحقق منها."
    ),
    S.INSUFFICIENT_EVIDENCE: (
        "لا تنشره على أنه حقيقة مؤكدة؛ راجع النصوص المعروضة أو ارجع إلى أهل العلم قبل النشر."
    ),
    S.NO_EVIDENCE_FOUND: (
        "لا تنشره على أنه حقيقة مؤكدة. تحقّق منه من مصدر علمي موثوق، أو أعد صياغته بدقة "
        "(مثلًا بذكر نص الآية) ثم أعد التحقق."
    ),
    S.CONFLICTING_EVIDENCE: (
        "راجع الأدلة المتعارضة المعروضة وارجع إلى أهل العلم قبل النشر؛ لم يُصدر ميزان حكمًا "
        "قاطعًا لأن المصادر المعتمدة نفسها مختلفة."
    ),
}

NO_EVIDENCE = (
    "لم يتم العثور على دليل كافٍ للتحقق من الادعاء ضمن المصادر المعتمدة حاليًا في ميزان. "
    "عدم العثور على دليل لا يعني أن الادعاء خاطئ."
)


def _names(ids: list[str], evidence: dict[str, Evidence]) -> str:
    names = list(dict.fromkeys(evidence[i].source_name for i in ids if i in evidence))
    return " و".join(names) if names else "المصادر المعتمدة"


def _ids(analysis: AnalysisResult, cid: str, rels: set[R]) -> list[str]:
    return [
        a.evidence_id
        for a in analysis.assessments
        if a.component_id == cid and a.relationship in rels
    ]


def build_why(status: S, analysis: AnalysisResult, evidence: list[Evidence]) -> str:
    ev = {e.evidence_id: e for e in evidence}
    subs = [c for c in analysis.components if c.role == ComponentRole.SUBSTANTIVE]
    anchors = [c for c in analysis.components if c.role == ComponentRole.ANCHOR]
    parts: list[str] = []
    if status == S.NO_EVIDENCE_FOUND:
        parts.append(NO_EVIDENCE)
    for c in subs + [a for a in anchors if a.outcome == O.CONTRADICTED]:
        cid = c.component_id
        if c.outcome == O.SUPPORTED:
            src = _names(_ids(analysis, cid, {R.SUPPORTS}), ev)
            parts.append(f"«{c.text}» يثبته نص صريح في {src}.")
        elif c.outcome == O.PARTIALLY_SUPPORTED:
            src = _names(_ids(analysis, cid, {R.PARTIALLY_SUPPORTS}), ev)
            parts.append(f"«{c.text}» يثبت جزء منه فقط في {src}.")
        elif c.outcome == O.CONTRADICTED:
            src = _names(_ids(analysis, cid, {R.CONTRADICTS}), ev)
            line = f"«{c.text}» يخالفه {src}."
            if c.detail:
                line += f" {c.detail}."
            parts.append(line)
        elif c.outcome == O.CONFLICTING:
            pro = _names(_ids(analysis, cid, {R.SUPPORTS, R.PARTIALLY_SUPPORTS}), ev)
            con = _names(_ids(analysis, cid, {R.CONTRADICTS}), ev)
            parts.append(f"بشأن «{c.text}»: يؤيده {pro} ويخالفه {con}؛ فالأدلة المعتمدة متعارضة.")
        elif c.outcome == O.INSUFFICIENT:
            src = _names(_ids(analysis, cid, {R.INSUFFICIENT}), ev)
            parts.append(f"وُجدت نصوص مرتبطة في {src} لكنها لا تثبت «{c.text}» بصورة مباشرة.")
        elif c.outcome == O.NOT_ESTABLISHED and status != S.NO_EVIDENCE_FOUND:
            parts.append(f"«{c.text}» لم يُعثر على ما يثبته في المصادر المعتمدة.")
    verified_anchor = [a for a in anchors if a.outcome in (O.SUPPORTED, O.PARTIALLY_SUPPORTED)]
    if verified_anchor and status != S.SUPPORTED:
        parts.append(
            "الآية المذكورة في الادعاء موثّقة في المصحف، لكن صحة نصها وحدها لا تثبت ما نُسب إليها."
        )
    return " ".join(dict.fromkeys(p.replace("..", ".") for p in parts)) or NO_EVIDENCE


def strength(
    a: EvidenceAssessment, evidence: Evidence, claim_type_label: str
) -> EvidenceStrengthAssessment:
    """Evidence Strength SIGNALS from pipeline facts only — no score, no LLM confidence."""
    src = get_trusted_source(evidence.trusted_source_id)
    direct = {
        R.SUPPORTS: "النص المستشهد به يذكر مضمون هذا الجزء مباشرة.",
        R.PARTIALLY_SUPPORTS: "النص يثبت جزءًا من هذا الجزء فقط.",
        R.CONTRADICTS: "النص المستشهد به يخالف هذا الجزء مباشرة.",
        R.INSUFFICIENT: "النص مرتبط بالموضوع لكنه لا يثبت هذا الجزء.",
    }[a.relationship]
    obs = [
        StrengthSignalObservation(
            signal=EvidenceStrengthSignal.SOURCE_SUITABILITY,
            basis=f"{src.name_ar}: مصدر معتمد ومؤهل لادعاءات {claim_type_label}.",
        ),
        StrengthSignalObservation(signal=EvidenceStrengthSignal.DIRECTNESS, basis=direct),
        StrengthSignalObservation(
            signal=EvidenceStrengthSignal.TRACEABILITY,
            basis="له عنوان رسمي لدى المزوّد وبصمة تطابق النص المعروض.",
        ),
    ]
    if a.relationship in (R.PARTIALLY_SUPPORTS, R.INSUFFICIENT):
        obs.append(
            StrengthSignalObservation(
                signal=EvidenceStrengthSignal.COMPLETENESS,
                basis="لا يغطي النص كل ما يقوله هذا الجزء من الادعاء.",
            )
        )
    return EvidenceStrengthAssessment(observations=obs)
