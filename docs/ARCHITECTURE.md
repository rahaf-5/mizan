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

## Input (MVP: text only)

Quick Check and Full Content Check accept text only. `ExtractionInput` (`app/domain/inputs.py`)
has `input_type = text` and forbids extra fields. Image input / OCR was removed from the MVP on
2026-10-04 (product-scope decision, not a technical failure). No OCR code, endpoint, dependency
or setting is part of the MVP; the previous implementation is preserved only in Git history
(commits `0eea5da` → `f08cf42`).

## Claim Extraction & Claim Review (Task 4)

```
Full Content text ─▶ POST /api/v1/claims/extract ─▶ LlmClaimExtractor ─▶ LLMProvider (Gemini adapter)
   ◀─ pending claims (grounded, validated) ─ Claim Review UI (edit / delete / (de)select / add)
   ─▶ explicit click ─▶ POST /api/v1/claims/confirm ─▶ domain gate select_confirmed_claims()
   ─▶ ConfirmedClaim[] (next_stage = claim_classification; verification_started = false)
```

- `app/pipeline/claim_extraction.py` implements the `ClaimExtractor` contract with ANY
  `LLMProvider`. It wraps the content as untrusted data (random per-request boundary), strictly
  validates `ClaimExtractionDraft`, drops claims whose `source_excerpt` is not found in the content
  (Arabic-normalised match, matching only), de-duplicates, and returns claims in `pending` status.
- `app/llm/gemini.py` is the only Gemini-specific code (REST `generateContent`, header auth,
  `generationConfig.responseMimeType = "application/json"` + `responseJsonSchema`,
  `thinkingConfig.thinkingLevel` as enum name e.g. `LOW`). Our own Pydantic validation of the
  returned JSON remains the final gate regardless of Google's schema enforcement. Nothing outside `app/llm`
  imports it; selection happens in `app/llm/factory.py` from settings.
- LLM output types (`app/llm/schemas.py`) cannot carry evidence, citations, references (other than
  text the user wrote), gradings or verdicts (tests in `test_llm_contracts.py`).
- Failures (`llm_not_configured`, `llm_auth_failed`, `llm_rate_limited`, `llm_timeout`,
  `llm_invalid_response`, `llm_content_blocked`, `llm_provider_error`) are system errors — never
  "no claims found". A successful extraction with zero claims is a separate, explicit result.
- Confirmation: the edited text (not the extracted text) becomes `confirmed_claim_text`
  (`edited` status); deselected/deleted claims are excluded; manual claims use the same gate.

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

## Locked decisions

1. **Retry exhaustion.** Technical failure != weak or missing evidence.
   - Technical/system failure preventing reliable verification after retries are exhausted →
     `SystemErrorOutcome(code=verification_incomplete)`.
   - System operated correctly and the remaining limitation is evidentiary → the gate abstains
     internally and maps to an approved status (e.g. `insufficient_evidence`, `no_evidence_found`).
   - The gate receives `retries_remaining` so it can abstain instead of requesting a retry it
     cannot get. Retry is never automatically converted into Abstain.
2. **Out of Scope** (separate processing outcome, never a seventh status):
   - unsupported claim category → `out_of_scope` (`unsupported_claim_category`)
   - requires sources outside the Trusted Sources Policy → `out_of_scope` (`outside_source_coverage`)
   - supported type, qualified sources searched successfully, no suitable evidence → `no_evidence_found`
   - relevant evidence found but not sufficient → `insufficient_evidence`
   - extensible with further explicit reasons (with approval).
3. **Quranpedia / Dorar** remain unresolved integration requirements until addressed before
   Task 5 (no invented APIs, endpoints, keys, scraping, caching or indexing rights).

4. **Image input / OCR removed from MVP scope (2026-10-04).** Full Content Check is text only.
   Task 3 closed as "removed from MVP scope". If OCR returns in a future version, OCR output must
   be reviewed by the user before Claim Extraction (spec §16) and OCR confidence must never affect
   verification status or Evidence Strength.

5. **LLM provider (2026-10-04).** Gemini Developer API is the current MVP adapter
   (`gemini-3.5-flash-lite`); the provider abstraction remains authoritative. Anthropic is not
   wired. LLM extraction is not religious verification; user confirmation is mandatory.

## Open decisions

1. **Evidence Strength levels.** Only signals are modelled; no levels/thresholds.
2. **Status → result group mapping** (spec §12) is deferred to Task 7.
