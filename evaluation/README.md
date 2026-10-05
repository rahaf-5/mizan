# Mizan final evaluation

Report: [`docs/EVALUATION_REPORT.md`](../docs/EVALUATION_REPORT.md).

- `dataset.json` — 49 text-only cases with ground truth type, expected claim types/sources/references/statuses and notes.
- `stability.json` — repeat counts for the stability check.
- `run_eval.mjs` — calls the real API (`/claims/extract` → `/claims/confirm` → `/verify`) like the frontend. Node 18+: `node evaluation/run_eval.mjs http://localhost:8000 > evaluation/results/raw.json` (backend running). Uses Gemini quota (~70 calls).
- `score_eval.py` — offline scoring: `cd backend && python ../evaluation/score_eval.py ../evaluation/results/raw.json` → `results/results.json`, `results/results.csv`, `results/metrics.json`.
- `results/rerun_after_fix.json` — tafsir/asbab re-run after the fix; `results/reruns_probe.json` — targeted probes.
