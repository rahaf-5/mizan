#!/usr/bin/env bash
# Real end-to-end checks (Gemini + official Quranpedia; Dorar must never be called).
# Needs internet access and backend/.env with the Gemini key. Never prints the key.
# Usage: ./scripts/smoke-all.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"
# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate

echo "== Commit: $(git -C "$ROOT" rev-parse --short HEAD)"
echo "== 1/4 Official Mushaf 1 data (SHA-256 verified)"
python -m app.cli.sync_quran_dump
echo "== 2/4 Claim extraction smoke"
python -m app.cli.smoke_claim_extraction
echo "== 3/4 Retrieval smoke"
python -m app.cli.smoke_retrieval
echo "== 4/4 Verification smoke (expect 15/15, Dorar calls: 0)"
python -m app.cli.smoke_verification
echo "All real smoke tests passed."
