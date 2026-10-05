"""Test-only placeholder stages (never used by the application).

Every stub raises StageNotImplementedError naming the task that will
implement it. No verification logic is invented here.
"""

from __future__ import annotations

from app.domain.enums import PipelineStage
from app.domain.errors import StageNotImplementedError


def _todo(stage: PipelineStage, task: str) -> StageNotImplementedError:
    return StageNotImplementedError(f"{stage.value} is not implemented yet ({task})", stage=stage)


class StubClaimExtractor:
    async def extract(self, data):  # type: ignore[no-untyped-def]
        raise _todo(PipelineStage.CLAIM_EXTRACTION, "Task 4")


class StubClaimClassifier:
    async def classify(self, claim):  # type: ignore[no-untyped-def]
        raise _todo(PipelineStage.CLAIM_CLASSIFICATION, "Task 4")


class StubSourceRouter:
    async def route(self, claim):  # type: ignore[no-untyped-def]
        raise _todo(PipelineStage.SOURCE_ROUTING, "Task 5")


class StubHybridRetriever:
    async def retrieve(self, claim, plan, *, attempt=0):  # type: ignore[no-untyped-def]
        raise _todo(PipelineStage.HYBRID_RETRIEVAL, "Task 5")


class StubEvidenceVerifier:
    async def verify(self, claim, candidates):  # type: ignore[no-untyped-def]
        raise _todo(PipelineStage.EVIDENCE_VERIFICATION, "Task 6")


class StubEvidenceAnalyzer:
    async def analyze(self, claim, assessments):  # type: ignore[no-untyped-def]
        raise _todo(PipelineStage.EVIDENCE_ANALYSIS, "Task 6")


class StubStatusDeterminer:
    async def determine(self, claim, analysis, retrieval):  # type: ignore[no-untyped-def]
        raise _todo(PipelineStage.VERIFICATION_STATUS, "Task 6")


class StubFinalValidationGate:
    async def validate(
        self, claim, retrieval, analysis, determination, *, retry_count, retries_remaining
    ):  # type: ignore[no-untyped-def]
        raise _todo(PipelineStage.FINAL_VALIDATION_GATE, "Task 6")


class StubResultBuilder:
    async def build(self, claim, retrieval, analysis, determination, validation):  # type: ignore[no-untyped-def]
        raise _todo(PipelineStage.FINAL_USER_RESULT, "Task 7")


from app.pipeline.orchestrator import PipelineStages, VerificationPipeline  # noqa: E402


def build_stub_pipeline(max_retries: int) -> VerificationPipeline:
    """Pipeline wired with placeholder stages (orchestration tests only)."""
    return VerificationPipeline(
        PipelineStages(
            classifier=StubClaimClassifier(),
            router=StubSourceRouter(),
            retriever=StubHybridRetriever(),
            verifier=StubEvidenceVerifier(),
            analyzer=StubEvidenceAnalyzer(),
            status=StubStatusDeterminer(),
            gate=StubFinalValidationGate(),
            builder=StubResultBuilder(),
        ),
        max_retries=max_retries,
    )
