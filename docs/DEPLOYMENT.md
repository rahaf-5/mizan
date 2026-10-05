# Deployment — public demo (Render, free plan)

Two services from `render.yaml` (Render Blueprint), no architecture change:

| Service | What | Secrets |
|---|---|---|
| `mizan-api` (Python web service) | FastAPI backend. At start it downloads and SHA-256-verifies the official Mushaf 1 dump, then serves the API. Calls Gemini and the official Quranpedia API server-side. Dorar stays blocked. | `GEMINI_API_KEY` (entered in the Render dashboard only) |
| `mizan-web` (static site) | Static export of the Next.js frontend (`MIZAN_STATIC_EXPORT=1`). The browser calls `mizan-api` directly. | none — `NEXT_PUBLIC_*` values are public by design |

## Steps

1. Push the repository to GitHub.
2. Render → **New → Blueprint** → select the repository → Render reads `render.yaml`.
3. When asked for the `sync: false` values:
   - `GEMINI_API_KEY` → your key (backend only).
   - `CORS_ORIGINS` → `https://mizan-web.onrender.com` (the web service URL).
   - `NEXT_PUBLIC_API_BASE_URL` → `https://mizan-api.onrender.com` (the API service URL).
   If Render gives a service a different URL (name already taken), put the real URLs in these two
   variables and redeploy both services (`NEXT_PUBLIC_API_BASE_URL` is read at build time).
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
