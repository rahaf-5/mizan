#!/usr/bin/env bash
# Run all Mizan foundation checks. Usage: ./scripts/check.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Backend =="
cd "$ROOT/backend"
python -m pytest -q
python -m ruff check .
python -m app.domain.contracts_export --check

echo "== Frontend =="
cd "$ROOT/frontend"
npm test --silent
npm run --silent typecheck
npm run --silent lint
npm run --silent build

echo "== Frontend bundle must not reference OCR (out of MVP scope) or provider credentials =="
if grep -rqiE "GOOGLE_VISION|googleapis|x-goog-api-key|/api/v1/ocr" .next/static; then
  echo "OCR/provider references found in the frontend bundle" >&2
  exit 1
fi

echo "All checks passed."
