# ميزان | Mizan — تحقّق قبل أن تنشر

Arabic-first assistant for verifying **religious claims** against trusted, traceable evidence.
The approved product specification (`MIZAN_PRODUCT_SPEC.md`, in the Mizan project) is the source of truth.

> **Claim First. Evidence Second. Judgment Last.** — الادعاء أولًا، الدليل ثانيًا، والنتيجة أخيرًا.

## Status — MVP feature-complete (Tasks 1–10)

| Area | State |
|---|---|
| Quick Check (one claim → confirm → verify → result) | ✅ real backend |
| Full Content Check (text → extract → review → confirm → verify → report) | ✅ real backend |
| Trusted sources: Quran (Mushaf 1), Tafsir al-Muyassar (2012), Ibn Kathir (136), Asbab al-Wahidi (2919), Al-Muharrar (460) — Quranpedia | ✅ connected |
| Hadith (Dorar al-Sunniyah) | ⛔ unavailable by policy → `required_source_unavailable` (never a verdict, never an invented grading) |
| Results & explainability (statuses, why, what to do, verified Quran reference, limitations, evidence cards grouped for conflicts, sources, links) | ✅ |
| Alternative wording (proposed, fully re-verified, adoptable only if verified) | ✅ |
| Image input / OCR | ❌ removed from MVP scope (2026-10-04) |

Full reports: [`docs/FINAL_REPORT.md`](docs/FINAL_REPORT.md) · testing: [`docs/TESTING.md`](docs/TESTING.md) ·
user flows: [`docs/USER_FLOWS.md`](docs/USER_FLOWS.md) · architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) ·
demo script: [`docs/DEMO.md`](docs/DEMO.md).

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
├── docs/               ARCHITECTURE · USER_FLOWS · TESTING · FINAL_REPORT · DEMO · SOURCE_VALIDATION · INTEGRATION_TODO
└── scripts/check.sh    Run every automated check
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
./scripts/smoke-all.sh                     # all of the below, in order (last result: 15/15, Dorar 0)

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
