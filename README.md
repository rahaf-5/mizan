# ميزان | Mizan — تحقّق قبل أن تنشر

Arabic-first assistant for verifying **religious claims** against trusted, traceable evidence.
The approved product specification (`MIZAN_PRODUCT_SPEC.md`, in the Mizan project) is the source of truth.

> **Claim First. Evidence Second. Judgment Last.** — الادعاء أولًا، الدليل ثانيًا، والنتيجة أخيرًا.

**Status:** Task 2 — Home, Quick Check and Full Content input screens. Inputs are validated and
*prepared* for later stages (claim review, extraction, OCR); no OCR, extraction or verification runs
yet. Pipeline stages, trusted-source adapters and the LLM provider remain typed contracts/placeholders.

## Repository layout

```
mizan/
├── backend/            FastAPI + Pydantic (Python ≥ 3.10)
│   ├── app/
│   │   ├── domain/     Typed domain models & approved enums (source of truth)
│   │   ├── pipeline/   Stage contracts, stubs, orchestrator skeleton
│   │   ├── sources/    Trusted-source adapter contract, allowlist registry, placeholders
│   │   ├── llm/        Provider abstraction (assistive only — never evidence)
│   │   ├── api/v1/     HTTP API (health only, for now)
│   │   ├── db/         SQLAlchemy engine/session (no tables yet)
│   │   └── config.py   Environment configuration
│   ├── migrations/     Alembic (no revisions yet)
│   └── tests/
├── frontend/           Next.js (App Router) + TypeScript + Tailwind, Arabic RTL
│   ├── src/app/        routes: / · /quick-check · /full-content · /status
│   ├── src/features/   quick-check/, full-content/ (input screens)
│   ├── src/lib/input/  typed input contracts, validation, in-memory input session
│   ├── src/i18n/       centralized UI strings (ar)
│   └── tests/          unit/, components/ (jsdom), integration/
├── contracts/          domain-contracts.json — shared enum snapshot (generated)
├── docs/               ARCHITECTURE.md, INTEGRATION_TODO.md
├── scripts/check.sh    Run all checks
└── docker-compose.yml  Local PostgreSQL (pgvector-capable image)
```

## Prerequisites

- Python 3.10+ · Node.js 20.9+ (22 LTS recommended) · Docker (for local PostgreSQL)

`backend/.venv`, `frontend/node_modules` and `.next` are not committed; create them on your
machine with the steps below (they are platform-specific).

## Setup

```bash
# 1) Database
cp .env.example .env               # choose a local password
docker compose up -d db

# 2) Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env               # set DATABASE_URL to match the root .env
uvicorn app.main:app --reload --port 8000

# 3) Frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev                        # http://localhost:3000
```

## Health checks

| Check | How |
|---|---|
| Backend starts | `curl http://localhost:8000/api/v1/health/live` → `{"status":"ok"}` |
| Config loads / DB reachable | `curl http://localhost:8000/api/v1/health` → `config_loaded: true`, `database.status` |
| Frontend starts | open http://localhost:3000 |
| Frontend → backend | open http://localhost:3000/status, or `cd frontend && npm run test:integration` (backend must be running) |

`/api/v1/health` reports `degraded` until the database is reachable. Trusted sources report
`disabled`/`not_connected`, and LLM/OCR report `not_configured` — expected in Task 1.
Health status is technical only and is never a verification result.

## Tests & checks

```bash
./scripts/check.sh          # everything below
# backend
cd backend && pytest && ruff check . && python -m app.domain.contracts_export --check
# frontend
cd frontend && npm test && npm run typecheck && npm run lint && npm run build
# frontend -> backend connectivity (backend running)
cd frontend && npm run test:integration
```

Note: ESLint stays on v9 because `eslint-config-next` 16's bundled plugins do not yet support ESLint 10.

If you intentionally change an approved enum (requires product approval), regenerate the shared
snapshot: `cd backend && python -m app.domain.contracts_export`.

## Non-negotiables enforced in code

- Verification accepts only `ConfirmedClaim` (confirmed/edited, non-empty `confirmed_claim_text`, selected).
- Six `VerificationStatus` values; `no_evidence_found` is not an `EvidenceRelationship`.
- Out of Scope and system errors are separate outcome kinds — never verification statuses.
- `Evidence` must be allowlisted, provider-consistent and traceable; hadith gradings must be attributed.
- Evidence Analysis cannot reference evidence that was not assessed.
- No final result from a `retry` gate outcome; abstain maps to an existing status.
- LLM output types cannot carry Evidence, references, URLs, citations or gradings.
- Unreviewed OCR text cannot enter Claim Extraction.

## Open decisions

See the Task 1 report / `docs/ARCHITECTURE.md` → "Open decisions".
