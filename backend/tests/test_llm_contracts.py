"""The LLM must never be modelled as an evidence source (spec §11, §21)."""

from __future__ import annotations

import typing

import pytest
from pydantic import BaseModel, ValidationError

from app.domain.enums import ClaimType
from app.domain.evidence import Evidence
from app.domain.retrieval import CandidateEvidence
from app.llm import schemas
from app.llm.base import LLMRequest
from app.llm.schemas import TASK_OUTPUT_SCHEMAS, ClassificationSuggestion, LLMOutput, LLMTask
from tests.support.fake_llm import FakeLLMProvider

FORBIDDEN_TYPES = {Evidence, CandidateEvidence}
FORBIDDEN_FIELD_NAMES = {
    "reference",
    "verified_reference",
    "source_url",
    "citation",
    "citations",
    "grading",
    "grading_details",
    "muhaddith",
    "source_record_id",
    "evidence",
}


def _all_output_types() -> list[type[LLMOutput]]:
    return [
        obj
        for obj in vars(schemas).values()
        if isinstance(obj, type) and issubclass(obj, LLMOutput)
    ]


def _walk(tp, seen):
    for arg in typing.get_args(tp):
        yield from _walk(arg, seen)
    if isinstance(tp, type) and issubclass(tp, BaseModel) and tp not in seen:
        seen.add(tp)
        yield tp
        for f in tp.model_fields.values():
            yield from _walk(f.annotation, seen)


def test_every_task_has_an_output_schema():
    assert set(TASK_OUTPUT_SCHEMAS) == set(LLMTask)


@pytest.mark.parametrize("output_type", _all_output_types())
def test_llm_outputs_cannot_carry_evidence_or_citations(output_type):
    for model in _walk(output_type, set()):
        assert model not in FORBIDDEN_TYPES, f"{output_type.__name__} contains {model.__name__}"
        assert FORBIDDEN_FIELD_NAMES.isdisjoint(model.model_fields), (
            f"{model.__name__} has a forbidden field"
        )


def test_llm_outputs_forbid_extra_fields():
    with pytest.raises(ValidationError):
        ClassificationSuggestion(rationale="r", reference="invented")  # type: ignore[call-arg]


async def test_fake_provider_and_schema_enforcement():
    p = FakeLLMProvider(
        [ClassificationSuggestion(suggested_claim_type=ClaimType.QURAN, rationale="r")]
    )
    req = LLMRequest(task=LLMTask.CLASSIFICATION_ASSISTANCE, system_prompt="s", user_content="u")
    out = await p.generate_structured(req, ClassificationSuggestion)
    assert out.suggested_claim_type == ClaimType.QURAN
    with pytest.raises(TypeError):
        await p.generate_structured(
            LLMRequest(task=LLMTask.EXPLANATION_GENERATION, system_prompt="s", user_content="u"),
            ClassificationSuggestion,
        )
