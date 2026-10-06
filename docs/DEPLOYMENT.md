# Deployment — public demo (Render, free plan)

Two services from `render.yaml` (Render Blueprint), no architecture change:

| Service | What | Secrets |
|---|---|---|
| `mizan-api` (Python web service) | FastAPI backend. At start it downloads and SHA-256-verifies the official Mushaf 1 dump, then serves the API. Calls Gemini and the official Quranpedia API server-side. Dorar stays blocked. | `GEMINI_API_KEY` (entered in the Render dashboard only) |
| `mizan-web` (static site) | Static export of the Next.js frontend (`MIZAN_STATIC_EXPORT=1`). The browser calls `mizan-api` directly. | none — `NEXT_PUBLIC_*` values are public by design |

## Steps

1. Push the repository to GitHub.
2. Render → **New → Blueprint** → select the repository → Render reads `render.yaml`.
3. Enter the `sync: false` values using the **exact URLs Render shows** for each service
   (Render adds a suffix such as `-l87e` when a name is taken):
   - `mizan-api` → `GEMINI_API_KEY` = your key (backend only).
   - `mizan-api` → `CORS_ORIGINS` = the mizan-web origin, e.g. `https://mizan-web-xxxx.onrender.com`
     (scheme + host only: no path, no trailing slash, no spaces).
   - `mizan-web` → `NEXT_PUBLIC_API_BASE_URL` = the mizan-api URL, e.g. `https://mizan-api-xxxx.onrender.com`.
     It is baked into the JavaScript **at build time**: after changing it, redeploy mizan-web
     (Manual Deploy → *Clear build cache & deploy*). The build log prints
     `API base URL baked into the build: …` and the build fails if the value is not a clean https URL.
4. Check: `https://<api>/api/v1/health` → `llm_provider: configured`, `quranpedia: configured`,
   `dorar_al_sunniyah: unavailable`. (`database: not_configured` is expected — no feature uses a DB.)

## Operating notes

- **Free plan sleeps** the API after ~15 minutes without traffic; the first request then waits
  about a minute while it wakes and re-downloads the Mushaf dump. Before a demo or judging window,
  open `https://<api>/api/v1/health/live` once, or keep it awake with an external uptime ping every
  10 minutes. A paid instance removes the sleep.
- **Gemini quota** is the key owner's quota; a free key can return HTTP 429 under load. Mizan shows
  this as a system error (retryable), never as a verdict.
- Quranpedia allows 120 requests/minute and 10,000/day per IP.
- Results live in the browser session; alternative wording needs the same API instance (in-memory).

## Troubleshooting: "تعذّر تأكيد الادعاء بسبب مشكلة تقنية"

- **No request at all in the mizan-api logs** → the browser is not calling mizan-api: the web build
  contains a different or invalid `NEXT_PUBLIC_API_BASE_URL` (unset → `http://localhost:8000`, old
  value, missing `https://`, trailing space). Check the mizan-web build log line above, fix the value,
  *Clear build cache & deploy* mizan-web, then hard-reload the page.
- **`OPTIONS … 400` in the mizan-api logs** → `CORS_ORIGINS` does not equal the mizan-web origin exactly.
  Fix it on mizan-api (it redeploys on save).
- **Request reaches mizan-api but takes ~1 minute / times out** → the free instance was asleep;
  open `/api/v1/health/live` first and retry.
