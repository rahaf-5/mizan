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

echo "== Frontend bundle must not reference OCR provider credentials =="
if grep -rqE "GOOGLE_VISION|googleapis|x-goog-api-key" .next/static; then
  echo "Provider credentials/endpoints found in the frontend bundle" >&2
  exit 1
fi

echo "All checks passed."
