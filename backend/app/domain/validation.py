"""Final Validation Gate models (spec §10).

No Final Result Without Final Validation. Retry improves verification, never
forces a verdict. Abstain is internal and maps to an existing status.
The retry limit is configuration (Settings.verification_max_retries), not domain logic.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import RetryReason, ValidationCheck, ValidationOutcome, VerificationStatus


class ValidationCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    check: ValidationCheck
    passed: bool
    detail: str | None = None


class FinalValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str
    outcome: ValidationOutcome
    checks: list[ValidationCheckResult] = Field(default_factory=list)
    #: Number of retries already performed for this claim.
    retry_count: int = Field(default=0, ge=0)
    retry_reason: RetryReason | None = None
    #: For outcome=abstain: the existing status the result is mapped to.
    abstained_to: VerificationStatus | None = None

    @model_validator(mode="after")
    def _outcome_consistency(self) -> FinalValidationResult:
        if self.outcome == ValidationOutcome.PASS:
            performed = {c.check for c in self.checks}
            missing = set(ValidationCheck) - performed
            if missing:
                raise ValueError(
                    f"pass requires all checks; missing {sorted(m.value for m in missing)}"
                )
            if not all(c.passed for c in self.checks):
                raise ValueError("pass requires every check to pass")
        if self.outcome == ValidationOutcome.RETRY and self.retry_reason is None:
            raise ValueError("retry requires a retry_reason")
        if self.outcome != ValidationOutcome.RETRY and self.retry_reason is not None:
            raise ValueError("retry_reason is only valid for retry")
        if (self.outcome == ValidationOutcome.ABSTAIN) != (self.abstained_to is not None):
            raise ValueError("abstained_to is required for, and only for, abstain")
        return self
