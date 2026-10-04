# Mizan architecture (Task 1 foundation)

## Pipeline (spec §11)

```
User Input → Claim Extraction → User Review & Confirmation → Claim Classification
→ Source Routing → Hybrid Retrieval → Evidence Verification → Evidence Analysis
→ Verification Status → Final Validation Gate → Final User Result
```

| Stage | Contract (`backend/app/pipeline/contracts.py`) | Input → Output | Implemented in |
|---|---|---|---|
| Claim Extraction | `ClaimExtractor` | `ExtractionInput` → `ClaimExtractionResult` | Task 4 |
| User Review & Confirmation | `select_confirmed_claims()` (domain gate) | `Claim[]` → `ConfirmedClaim[]` | gate: Task 1; UI: Task 4 |
| Claim Classification | `ClaimClassifier` | `ConfirmedClaim` → `ClassifiedClaim \| OutOfScopeOutcome` | Task 4 |
| Source Routing | `SourceRouter` | `ClassifiedClaim` → `SourceRoutingPlan \| OutOfScopeOutcome` | Task 5 |
| Hybrid Retrieval | `HybridRetriever` | → `RetrievalResult` (candidates + attempts) | Task 5 |
| Evidence Verification | `EvidenceVerifier` | → `EvidenceAssessment[]` | Task 6 |
| Evidence Analysis | `EvidenceAnalyzer` | → `AnalysisResult` | Task 6 |
| Verification Status | `StatusDeterminer` | → `StatusDetermination` (1 of 6) | Task 6 |
| Final Validation Gate | `FinalValidationGate` | → `FinalValidationResult` (pass/retry/abstain) | Task 6 |
| Final User Result | `ResultBuilder` | → `ClaimOutcome` | Task 7 |

`orchestrator.VerificationPipeline` wires the stages from Classification onwards. Extraction and
confirmation are interactive (the user reviews claims in between), so they are driven by the API/UI.

## Per-claim outcomes

A claim ends in exactly one of three structurally separate outcomes (`domain/results.py`):

- `VerificationOutcome` — one of the six statuses, with analysis, a non-retry validation result, and
  the full traceable evidence records.
- `OutOfScopeOutcome` — outside MVP capabilities/source coverage. Not a status; never False.
- `SystemErrorOutcome` — technical failure. Never `insufficient_evidence`.

## Layering

- `domain/` has no dependency on FastAPI, DB, sources or LLM. The Trusted Sources Allowlist is
  product policy and lives in `domain/trusted_sources.py`.
- `sources/` adapters produce `Evidence` from verified provider metadata; the registry refuses
  sources/providers not on the allowlist.
- `llm/` outputs are suggestions typed as `LLMOutput` subclasses; they cannot contain evidence or
  citations. The owning stage validates them.
- Frontend mirrors domain enums in `src/lib/domain.ts`, checked against `contracts/domain-contracts.json`.

## Configuration

`backend/app/config.py` (env / `backend/.env`). Secrets are `SecretStr` and never returned by the
API. `VERIFICATION_MAX_RETRIES` (default 2) is an implementation default injected into the
orchestrator — not a domain rule.

## Open decisions (need product confirmation)

1. **Retry budget exhausted.** Provisionally: if the gate still returns `retry` after the configured
   limit, the claim ends as `SystemErrorOutcome(code=verification_incomplete)` ("verification could
   not be completed — allow retry", spec §17), not an evidence status. Alternative: the gate must
   abstain on the final attempt.
2. **Out of Scope reasons.** Initial values `unsupported_claim_category`, `outside_source_coverage`.
   The rules that decide Out of Scope vs `no_evidence_found` are not yet defined.
3. **Evidence Strength levels.** Only signals are modelled; no levels/thresholds.
4. **Status → result group mapping** (spec §12) is deferred to Task 7.
