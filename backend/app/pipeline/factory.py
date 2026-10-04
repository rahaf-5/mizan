"""Build the real verification pipeline (Tasks 5a + 5b)."""

from __future__ import annotations

from app.config import Settings
from app.llm.base import LLMProvider
from app.pipeline.analysis import DeterministicEvidenceAnalyzer, DeterministicStatusDeterminer
from app.pipeline.classification import LlmClaimClassifier
from app.pipeline.gate import TrustedValidationGate
from app.pipeline.orchestrator import PipelineStages, VerificationPipeline
from app.pipeline.result_builder import VerificationResultBuilder
from app.pipeline.retrieval import TrustedSourceRetriever
from app.pipeline.routing import DeterministicSourceRouter
from app.pipeline.verification import TrustedEvidenceVerifier
from app.sources.registry import AdapterRegistry


def build_verification_pipeline(
    settings: Settings, provider: LLMProvider, registry: AdapterRegistry
) -> VerificationPipeline:
    return VerificationPipeline(
        PipelineStages(
            classifier=LlmClaimClassifier(provider),
            router=DeterministicSourceRouter(registry),
            retriever=TrustedSourceRetriever(registry),
            verifier=TrustedEvidenceVerifier(registry, provider),
            analyzer=DeterministicEvidenceAnalyzer(),
            status=DeterministicStatusDeterminer(),
            gate=TrustedValidationGate(),
            builder=VerificationResultBuilder(),
        ),
        max_retries=settings.verification_max_retries,
    )
