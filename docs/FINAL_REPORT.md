# Mizan | ميزان — Final MVP Report

**Date:** 2026-10-05 · **Spec:** `MIZAN_PRODUCT_SPEC.md` (approved MVP) · **Principle:** Claim First. Evidence Second. Judgment Last.

## 1. What was built

An Arabic-first RTL web app that verifies religious claims only against trusted, traceable
sources and explains each result.

| Spec task | Status | Where |
|---|---|---|
| 1 Foundation (models, enums, contracts, RTL shell) | ✅ | `backend/app/domain`, `contracts/`, `frontend/src/app` |
| 2 Core input UI (Home, Quick Check, Full Content text) | ✅ | `frontend/src/features/{quick-check,full-content}` |
| 3 OCR | ❌ removed from MVP scope (product decision 2026-10-04) | Git history only |
| 4 Claim extraction & review + confirmation gate | ✅ real smoke 4/4 | `pipeline/claim_extraction.py`, `api/v1/claims.py`, `features/claim-review` |
| 5a Trusted-source retrieval (Quranpedia) | ✅ real smoke 9/9, Dorar 0 | `sources/quranpedia.py`, `sources/quran_index.py`, `pipeline/retrieval.py` |
| 5b/6 Verification engine + Final Validation Gate | ✅ implemented; real rerun pending (see §4) | `pipeline/verification.py`, `quran_checks.py`, `passage_analysis.py`, `analysis.py`, `gate.py` |
| 7 Results & explainability | ✅ | `pipeline/explanation.py`, `result_builder.py`, `features/results/*` |
| 8 Alternative wording (re-verified) | ✅ | `pipeline/alternative_wording.py`, `/api/v1/alternative-wording`, `AlternativeWordingPanel` |
| 9 Error handling & end-to-end integration | ✅ | `api/v1/verify.py`, `lib/verify`, `useVerificationRuns`, Quick Check + `/full-content/results` |
| 10 Testing | ✅ automated (342 BE + 85 FE); 16 sensitive cases mapped | `docs/TESTING.md` |

Sources: Quran — Quranpedia Mushaf 1 (official dump, SHA-256); Tafsir al-Muyassar (book 2012),
Ibn Kathir (136), Asbab al-Wahidi (2919), Al-Muharrar (460) — official live API. Hadith/Dorar:
unavailable by policy → `required_source_unavailable` (never called, no gradings).

## 2. How the locked rules are enforced

- **Flows:** Quick Check = input → confirm gate → verify → result. Full Content = input →
  extract → review → confirm → verify → report. `/verify` only accepts gate-produced confirmed
  claims; edited text is verified; deleted/deselected claims are never sent; manual claims are verified.
- **Statuses:** six evidence statuses + separate `out_of_scope`, `required_source_unavailable`,
  `system_error(verification_incomplete)`; technical failures never map to evidence statuses
  (backend gate + UI mapping, both tested).
- **Traceability:** Evidence → source → provider → official address/record → reference/URL;
  displayed text is the provider's text with a SHA-256; cited spans are exact substrings
  (numbered-segment citation, retry once, then fail closed).
- **No LLM knowledge as evidence:** LLM types cannot carry evidence/references/URLs/gradings;
  explanations are deterministic; no web search; no confidence scores.
- **Anchors** never raise a status; a contradicted anchor makes the claim contradicted.
- **Alternative wording** is generated only from the server-stored result and is re-run through
  the full pipeline; shown/adoptable only if `supported`.
- **Security:** injected instructions are wrapped as untrusted data (random boundary); key never
  logged/returned; test fakes are excluded from app code (enforced by `scripts/check.sh`).

## 3. Verification results (real, not simulated)

- Automated: backend **342 passed**, ruff + format clean, contract snapshot up to date; frontend
  **85 passed**, typecheck + lint clean, production build OK (fresh build), bundle hygiene OK.
- Real smoke history: Task 4 4/4; Task 5a 9/9 (Dorar 0); Task 5b first run 11/13 (both failures
  fixed in `7379966` with regression tests). See `docs/TESTING.md`.

## 4. Genuine blockers / open items

1. **Real smoke rerun required on the developer machine.** The development cloud and the local
   sandbox VM cannot reach `api.quranpedia.net` or `generativelanguage.googleapis.com` (egress
   policy). Run `python -m app.cli.smoke_verification` → expected `15/15`, `Dorar calls: 0`.
   Results screenshots must be captured during that run (`docs/DEMO.md`).
2. **Hadith verification is unavailable** until Dorar provides official per-hadith ids/URLs,
   single-record retrieval and written display/caching permission (`docs/SOURCE_VALIDATION.md`).
3. **Before a public launch (not MVP blockers):** Gemini Free Tier data-use terms (paid tier or a
   user notice); in-memory result store (alternative wording needs the same server process,
   max 500 results); Ibn Kathir 136 lacks content for 179 ayahs.

## 5. Final submission checklist

| # | Deliverable | File / path | Status | Blocker |
|---|---|---|---|---|
| 1 | Product specification (source of truth) | Project: `MIZAN_PRODUCT_SPEC.md` | complete | — |
| 2 | Source code — backend | `backend/` | complete | — |
| 3 | Source code — frontend | `frontend/` | complete | — |
| 4 | Shared contracts | `contracts/domain-contracts.json` | complete | — |
| 5 | README (overview, setup, run, try it) | `README.md` | complete | — |
| 6 | Architecture / pipeline doc | `docs/ARCHITECTURE.md` | complete | — |
| 7 | User flows, screens & UX states | `docs/USER_FLOWS.md` | complete | — |
| 8 | Source validation & approved source decisions | `docs/SOURCE_VALIDATION.md`, `docs/dumps-validation-2026-10-04.txt` | complete | — |
| 9 | Integration requirements record | `docs/INTEGRATION_TODO.md` | complete | — |
| 10 | Testing strategy, 16-case matrix, results | `docs/TESTING.md` | complete | — |
| 11 | Automated test suites | `backend/tests/`, `frontend/tests/` | complete (342 + 85 passing) | — |
| 12 | One-command check script | `scripts/check.sh` | complete | — |
| 13 | Real smoke CLIs | `backend/app/cli/smoke_*.py` | complete | — |
| 14 | Real smoke rerun (15 cases) | output of `smoke_verification` | **incomplete** | needs the developer machine (network) |
| 15 | Demo script | `docs/DEMO.md` | complete | — |
| 16 | Screenshots — input, guidance, error & empty states | `docs/screenshots/` (16 PNG) | complete | — |
| 17 | Screenshots — verification results | `docs/screenshots/` | **incomplete** | needs live backend (same as #14) |
| 18 | Final report & checklist | `docs/FINAL_REPORT.md` | complete | — |
| 19 | Task status | Project: `claude/TASK_STATUS.md` | complete | — |
| 20 | Hadith (Dorar) integration | `backend/app/sources/dorar.py` | not in scope until unblocked | Dorar terms/ids (external) |
