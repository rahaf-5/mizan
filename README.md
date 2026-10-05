# ميزان | Mizan — تحقّق قبل أن تنشر

**Live demo:** _LIVE_URL_ (see [Deployment](docs/DEPLOYMENT.md)) · **Evaluation:** [`submission/EVALUATION_SUMMARY.md`](submission/EVALUATION_SUMMARY.md) · **Submission pack:** [`submission/`](submission/)

> **Mizan is not an assistant that answers; it is a checker that refuses to judge without evidence.**
> ميزان ليس مساعدًا يجيب؛ بل مدقق يرفض الحكم دون دليل.

## What problem it solves

Religious posts are shared every day with an ayah attributed to the wrong surah, words added to
an ayah, or a tafsir / reason-of-revelation that the sources do not say. The person sharing it
has no quick way to check **before publishing**. Search returns pages, not a judgment; a general
chatbot answers from its own memory, with no record you can open and check.

Mizan takes a claim or a whole text, splits it into checkable claims (you review and confirm
them), checks each one **only** against an allowlist of trusted sources, and tells you in plain
Arabic: the status, why, what to do before publishing, and the exact evidence with its source record.

## Scope of this version

| Mizan verifies | How |
|---|---|
| Quran text and location (surah / ayah) | Deterministically against the official Quranpedia Mushaf 1 dump (6,236 ayahs, SHA-256 verified) — no LLM |
| Tafsir claims about a specific ayah | Tafsir al-Muyassar, Tafsir Ibn Kathir (official Quranpedia API) |
| Asbab al-nuzul claims about a specific ayah | al-Wahidi, al-Muharrar (official Quranpedia API) |

| Mizan says so explicitly — by design, not as a bug | Outcome |
|---|---|
| Part of the claim supported, part not | `partially_supported` (shows which part) |
| Evidence exists but does not establish the claim / nothing found | `insufficient_evidence` / `no_evidence_found` |
| Hadith (needs a hadith source; Dorar has no per-hadith record id/URL usable here) | `required_source_unavailable` — no verdict, no grading |
| Fiqh rulings / fatwa, general or historical statements | `out_of_scope` |
| Provider / technical failure | `system_error` — never turned into a verdict |

Not in this MVP: image/OCR input, semantic (meaning-only) search, accounts/database. Details:
[`submission/SCOPE.md`](submission/SCOPE.md).

## How it works — where AI is used and where it is not allowed to decide

```
text ─► LLM: extract claims ─► YOU review & confirm ─► LLM: classify claim type ─► route to allowed sources
     ─► retrieve records from the allowlist (Quranpedia)            ─► deterministic Quran checks (text, location)
     ─► LLM: relate tafsir/asbab passages to parts of the claim, citing numbered segments;
        Mizan copies the cited text from the source itself and checks it occurs verbatim
     ─► deterministic status rules ─► Final Validation Gate (7 checks) ─► result + evidence
```

- **The LLM (Gemini, server-side) understands, splits and relates.** It never supplies evidence,
  references, URLs or gradings — its output types cannot carry them.
- **Trusted sources supply the evidence.** Each evidence item carries source, provider, official
  record address, reference, URL and a SHA-256 of the exact text shown.
- **Deterministic checks** decide everything that can be checked mechanically (ayah text and location,
  verbatim spans, record integrity).
- **The Final Validation Gate** blocks any result that is not backed by traceable evidence.
- **Safe stop:** no source → `required_source_unavailable`; technical failure → `system_error`
  after bounded retries; weak evidence → `insufficient_evidence`. Never a guess.

More: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Evaluation (real numbers, with their context)

49 text cases written by the team, run through the **real API** on 2026-10-05
([report](docs/EVALUATION_REPORT.md) · [summary](submission/EVALUATION_SUMMARY.md)):

- Status: **36 / 37** verify cases correct (97.3 %). One case hit Gemini's rate limit (HTTP 429)
  and is reported separately as a provider failure. The one miss stopped safely as a system error;
  **no wrong verdict** in the main run.
- Citations: 88 / 88 evidence items traceable (allowlisted source, record URL, SHA-256);
  43 / 43 Quran items identical to the Mushaf; 87 / 87 cited spans verbatim; 0 invented citations.
- Retrieval: expected source 25 / 25, expected ayah 12 / 12. Extraction: 6 / 7 expected claims.
- Repeated runs found one real bug (A03: an unproven detail came back `supported`); it was fixed,
  covered by regression tests and re-run live.
- Context: the dataset is team-built and small; tafsir/asbab expectations follow the source texts,
  some accept more than one honest status; **no expert religious review has taken place yet.**

### Verify our evaluation results without an API key

The scorer is offline and deterministic; it recomputes every number from the recorded API
responses. The Mushaf download is public (no key).

```bash
git clone <this repo> mizan && cd mizan/backend
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
python -m app.cli.sync_quran_dump                              # official Mushaf 1, SHA-256 checked
python ../evaluation/score_eval.py ../evaluation/results/raw.json
git -C .. diff --stat evaluation/results                       # empty = identical to our results
```

## Repository layout

```
mizan/
├── backend/            FastAPI + Pydantic v2 (Python ≥ 3.10)
│   ├── app/
│   │   ├── domain/     Typed domain models, approved enums, Trusted Sources policy
│   │   ├── pipeline/   Classification → routing → retrieval → verification → analysis →
│   │   │               status → Final Validation Gate → result builder; alternative wording
│   │   ├── sources/    Quranpedia adapter + Mushaf 1 index; Dorar adapter (not connected)
│   │   ├── llm/        Provider abstraction + Gemini adapter + prompts (assistive only — never evidence)
│   │   ├── api/v1/     health · claims/extract · claims/confirm · verify · alternative-wording
│   │   └── cli/        sync_quran_dump · smoke_* (real end-to-end checks) · validate_sources
│   └── tests/          pytest (support/ holds test-only fakes and stubs)
├── frontend/           Next.js 16 (App Router) + React 19 + TypeScript + Tailwind 4, Arabic RTL
│   ├── src/app/        / · /quick-check · /full-content · /full-content/claims · /full-content/results · /status
│   ├── src/features/   quick-check/ · full-content/ · claim-review/ · results/
│   ├── src/lib/        input/ · claims/ · verify/ (typed API clients and contracts)
│   └── tests/          unit/ · components/ (jsdom) · fixtures/ (test-only) · integration/
├── contracts/          domain-contracts.json — shared enum snapshot (generated, checked)
├── docs/               ARCHITECTURE · USER_FLOWS · TESTING · FINAL_REPORT · EVALUATION_REPORT · DEPLOYMENT · DEMO · SOURCE_VALIDATION
├── evaluation/         Final evaluation: dataset, real-API runner, offline scorer, results
├── submission/         Judge-facing pack: checklist, scope, sources, tools/licenses, evaluation, demo, presentation
├── render.yaml         Public demo deployment (Render Blueprint)
└── scripts/            check.sh (all automated checks) · smoke-all.sh (real end-to-end) · start-demo.command
```

## Prerequisites

Python 3.10+ · Node.js 20.9+ (22 LTS recommended) · a Gemini Developer API key ·
internet access to `api.quranpedia.net` and `generativelanguage.googleapis.com`.
Docker/PostgreSQL is optional (only the health check reports it; no feature needs the DB).

## Setup & run

```bash
# 1) Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # then set the three LLM lines below in backend/.env
python -m app.cli.sync_quran_dump   # once: official Mushaf 1 dump, SHA-256 verified (git-ignored)
uvicorn app.main:app --reload --port 8000

# 2) Frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local    # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev                   # http://localhost:3000
```

`backend/.env` (never commit it; the key is never logged or returned by the API):

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=<your key>
GEMINI_MODEL=gemini-3.5-flash-lite
```

Optional local database for the health page: `cp .env.example .env && docker compose up -d db`
at the repo root, and set `DATABASE_URL` in `backend/.env`.

## Try it

Quick start for a demo on macOS: double-click `scripts/start-demo.command` (starts the backend
on :8000 and a production frontend on :3000, then opens http://localhost:3000; close the window to stop).

1. Open http://localhost:3000 → **فحص سريع** → type
   `قال تعالى في سورة آل عمران: «إن الصفا والمروة من شعائر الله»` → **تحقق من الادعاء**.
   Expected: **يخالف الدليل** — the quote exists, but in سورة البقرة 158; open
   «عرض الأدلة والمصادر» to see the verbatim ayah, reference and the Quranpedia record link, then
   try **اقترح صياغة بديلة** (shown only if the new wording itself verifies).
2. **فحص محتوى كامل** → paste a paragraph with several claims → **استخراج الادعاءات** → edit,
   delete, deselect or add claims → **تحقّق من الادعاءات المحددة** → the report verifies only
   the confirmed claims, one by one, with real progress.
3. A hadith claim (e.g. `قال رسول الله ﷺ: «إنما الأعمال بالنيات»`) ends as
   **المصدر المطلوب غير متاح حاليًا** — no verdict and no grading.

More scenarios: [`docs/DEMO.md`](docs/DEMO.md).

## Real end-to-end smoke tests (need the internet + the Gemini key)

```bash
./scripts/smoke-all.sh                     # all of the below, in order (last result on 8fdc4e4: 15/15, Dorar 0)

cd backend && source .venv/bin/activate
python -m app.cli.smoke_claim_extraction   # Task 4: extraction only
python -m app.cli.smoke_retrieval          # Task 5a: retrieval/traceability (no verdicts)
python -m app.cli.smoke_verification       # Task 5b+: 15 fixed claims through the full pipeline;
                                           # must end "15/15" with "Dorar calls: 0"
python -m app.cli.diagnose_gemini          # only if Gemini rejects requests
```

## Automated checks

```bash
./scripts/check.sh      # backend pytest + ruff + format + contract snapshot; frontend tests,
                        # typecheck, lint, build; bundle and test-code hygiene checks
cd frontend && npm run test:integration   # frontend → running backend connectivity
```

ESLint stays on v9 because `eslint-config-next` 16's bundled plugins do not yet support ESLint 10.
If an approved enum changes (requires product approval): `cd backend && python -m app.domain.contracts_export`.

## Formally deferred (not in this MVP)

Six detailed loading stages (per-claim progress is shown instead), semantic search, extra
evidence-strength signals, a database, hadith verification (Dorar unavailable), image/OCR.
Reasons: `docs/FINAL_REPORT.md` §4.

## Non-negotiables enforced in code

- No verification before confirmation: `/verify` accepts only `ConfirmedClaim`s produced by the
  confirmation gate; the edited text is what is verified; deleted/deselected claims are never sent.
- Trusted sources only (allowlist); no web search; LLM knowledge is never evidence; LLM output
  types cannot carry evidence, references, URLs, citations or gradings.
- Every evidence item: Evidence → Source → Provider → official address/record → reference/URL,
  with a SHA-256 of the exact displayed text.
- Six evidence statuses + structurally separate `out_of_scope`, `required_source_unavailable`
  and `system_error` outcomes — technical failures never become evidentiary statuses.
- Final Validation Gate (7 checks); integrity/technical failures fail closed after bounded
  retries; abstain maps to an existing status; results never stronger than the evidence.
- Alternative wording is re-verified through the full pipeline and offered only if verified.
- No confidence scores; evidence strength is shown as signals only.

## Licenses and third-party services

No open-source license has been chosen for Mizan's own code yet (all rights reserved until one is
added). Third-party libraries, fonts, services and their terms: [`submission/TOOLS_AND_LICENSES.md`](submission/TOOLS_AND_LICENSES.md).
Sources and how each is used: [`submission/SOURCES_AND_CONTENT.md`](submission/SOURCES_AND_CONTENT.md).
