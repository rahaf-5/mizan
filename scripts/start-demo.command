#!/bin/bash
# Start Mizan locally for a demo: backend (FastAPI :8000) + frontend (Next.js production :3000).
# Double-click in Finder, or run ./scripts/start-demo.command. Close this window (or Ctrl+C) to stop.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGS="${TMPDIR:-/tmp}/mizan-demo"
mkdir -p "$LOGS"
export NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
export CORS_ORIGINS="http://localhost:3000"

for port in 8000 3000; do
  pids=$(lsof -ti tcp:$port 2>/dev/null || true)
  [ -n "$pids" ] && echo "Stopping old process on :$port" && kill $pids 2>/dev/null
done
sleep 1

echo "== Backend (http://localhost:8000)"
cd "$ROOT/backend"
PY="$ROOT/backend/.venv/bin/python"
if ! "$PY" -c "import uvicorn, fastapi" 2>/dev/null; then
  echo "backend/.venv is not usable on this Mac. See README → Setup." ; read -r -p "Press Enter to close"; exit 1
fi
"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$LOGS/backend.log" 2>&1 &
BACK=$!

echo "== Frontend build (one-time, ~1 min)"
cd "$ROOT/frontend"
if ! npm run build > "$LOGS/frontend-build.log" 2>&1; then
  echo "Frontend build failed — see $LOGS/frontend-build.log"; kill $BACK; read -r -p "Press Enter to close"; exit 1
fi
npm run start -- -p 3000 -H 127.0.0.1 > "$LOGS/frontend.log" 2>&1 &
FRONT=$!
trap 'echo; echo "Stopping Mizan…"; kill $BACK $FRONT 2>/dev/null; exit 0' INT TERM HUP

ok_back=no; ok_front=no
for _ in $(seq 1 60); do
  curl -sf http://localhost:8000/api/v1/health/live >/dev/null && ok_back=yes
  curl -sf http://localhost:3000/ >/dev/null && ok_front=yes
  [ "$ok_back" = yes ] && [ "$ok_front" = yes ] && break
  sleep 1
done
echo
echo "Backend : $ok_back  (log: $LOGS/backend.log)"
echo "Frontend: $ok_front (log: $LOGS/frontend.log)"
curl -s http://localhost:8000/api/v1/health | head -c 600; echo
if [ "$ok_back" = yes ] && [ "$ok_front" = yes ]; then
  echo; echo "Mizan is running → http://localhost:3000"; open http://localhost:3000
else
  echo "Something did not start — check the logs above."
fi
echo "Keep this window open during the demo. Close it or press Ctrl+C to stop."
wait
