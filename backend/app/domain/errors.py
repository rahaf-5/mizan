"""System/technical errors — structurally separate from evidence statuses.

system_error != insufficient_evidence (spec §17). Nothing in this module can
be turned into a VerificationStatus.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import PipelineStage, SystemErrorCode


class SystemErrorInfo(BaseModel):
    """Serializable description of a technical failure."""

    model_config = ConfigDict(frozen=True)

    code: SystemErrorCode
    stage: PipelineStage | None = None
    message: str = Field(min_length=1)
    retryable: bool = True


class MizanError(Exception):
    """Base class for Mizan exceptions that carry a SystemErrorInfo."""

    code: SystemErrorCode = SystemErrorCode.INTERNAL_ERROR
    retryable: bool = True

    def __init__(self, message: str, *, stage: PipelineStage | None = None) -> None:
        super().__init__(message)
        self.stage = stage

    def to_info(self) -> SystemErrorInfo:
        return SystemErrorInfo(
            code=self.code, stage=self.stage, message=str(self), retryable=self.retryable
        )


class StageNotImplementedError(MizanError):
    """A pipeline stage that is still a placeholder (to be implemented in a later task)."""

    code = SystemErrorCode.STAGE_NOT_IMPLEMENTED
    retryable = False


class SourceNotConnectedError(MizanError):
    """A trusted-source adapter whose real integration is not yet connected."""

    code = SystemErrorCode.SOURCE_NOT_CONNECTED
    retryable = False


class SourceUnavailableError(MizanError):
    code = SystemErrorCode.SOURCE_UNAVAILABLE


class LLMProviderError(MizanError):
    code = SystemErrorCode.LLM_PROVIDER_ERROR


# --- Policy violations (programming errors, not user-facing outcomes) -------


class ClaimNotConfirmedError(ValueError):
    """Raised when something tries to verify a claim that is not user-confirmed.

    Enforces: No Verification Before Claim Confirmation (spec §2, §21).
    """


class UntrustedSourceError(ValueError):
    """Raised when a source outside the Trusted Sources Allowlist is used (spec §5)."""
