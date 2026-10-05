# Mizan | ميزان — Final Evaluation Report

**Run date:** 2026-10-05 (main run 18:20:48 → 18:27:12 UTC, 67 runs) · **Code under test:** `ee0e406`, then the fix in this commit (re-run 2026-10-05)
**Environment:** local demo on the developer Mac (`scripts/start-demo.command`): FastAPI backend `127.0.0.1:8000`, LLM `gemini-3.5-flash-lite` (free tier), Quranpedia Mushaf 1 dump + live Quranpedia API for tafsir/asbab, Dorar unavailable by policy, no database.
**Method:** every case goes through the **real HTTP API** exactly like the frontend (`/claims/extract` → `/claims/confirm` → `/verify`), one request at a time with a 2.5 s pause (`evaluation/run_eval.mjs`). Scoring is offline and deterministic (`evaluation/score_eval.py`). Text only — no OCR, no images.

## 1. Files

| What | Where |
|---|---|
| Dataset (49 cases, ground truth + notes) | `evaluation/dataset.json` |
| Repeated-run plan | `evaluation/stability.json` |
| Runner (real API) / scorer | `evaluation/run_eval.mjs`, `evaluation/score_eval.py` |
| Raw machine output (main run) | `evaluation/results/raw.json` |
| Per-case expected vs actual, pass/fail | `evaluation/results/results.json`, `evaluation/results/results.csv` |
| All metrics | `evaluation/results/metrics.json` |
| Re-run after the fix (tafsir/asbab) | `evaluation/results/rerun_after_fix.json` |
| Targeted probes (A06, O01, E02) | `evaluation/results/reruns_probe.json` |

## 2. Dataset and coverage

49 cases: 38 verify (claim typed by the user), 6 extraction (full content), 5 API/contract.

| Ground-truth type | Cases | Meaning |
|---|---|---|
| `deterministic` | 25 | Checked mechanically: every Quran text/location was verified against the Mushaf 1 dump (6,236 ayahs) before the run; API cases have a fixed HTTP contract. |
| `source_grounded` | 13 | Expected status follows from what the allowlisted tafsir/asbab passages say (e.g. Wahidi on 2:158 names the Ansar). Accepts a set of statuses where the spec allows more than one honest answer (e.g. a wrong meaning may be `contradicted` or `insufficient_evidence`, never `supported`). |
| `mvp_behavior` | 10 | Expected behaviour of the approved MVP, not a religious ruling (hadith → `required_source_unavailable`, fiqh/general → `out_of_scope`). |
| `expert_review` | 1 | T06 (overgeneralised tafsir). Scored only as "must not be fully supported". **No expert review took place**; it is flagged for one. |

| Required coverage item | Cases |
|---|---|
| supported | Q01 Q03 Q06 Q07 Q09 Q11 T01 T03 T04 A01 A04 A05 |
| partially_supported | Q04 (partial ayah + invented words), T07, A03 |
| contradicted | Q02 Q08 Q10 Q12 (wrong surah/ayah), I01 |
| insufficient_evidence | Q13 (ayah name), T02/T05/T06/A02/A06 accept it |
| no_evidence_found | Q05 (fabricated quote), I02, I03 |
| conflicting_evidence | **not testable live** — no real conflicting case was found among the allowlisted passages for the dataset ayahs; covered only by the unit test `test_tafsir_evidence_conflict` (synthetic). Not claimed. |
| Quran quote / correct & wrong location / partial ayah | Q01–Q12 |
| Text without tashkeel / with tashkeel | Q01–Q05, Q07–Q12 (plain) · Q06 (full tashkeel) |
| Tafsir | T01–T07 · Asbab al-nuzul | A01–A06 |
| Overgeneralised wording | T06, O04 |
| Hadith → `required_source_unavailable` | H01–H03, H05 · Composite Quran + hadith | H04, E01 |
| Out of scope | O01–O04 · Prompt injection | I01–I03, E06 |
| Citation / traceability | every verification result (section 6) + V05 |
| Input validation / confirmation gate | V01–V04 |
| Source unavailable / technical errors | **not forced live** (would need to break the provider). Covered by unit tests (`test_source_failure_fails_closed_after_bounded_retries_without_analysis`, `test_source_without_text_for_the_ayah_is_surfaced_as_a_limitation`, `test_integrity_failure_after_retries_is_system_error`). Observed live: Al-Muharrar has no text for 93:3 → shown as a limitation (A06); real 429 and invalid-LLM-output failures (section 7). |

## 3. Status accuracy (main run, first run of each case)

External provider failures are excluded from the denominator and reported separately (1 case: O01, HTTP 429 `llm_rate_limited`; its retry returned the expected `out_of_scope`).

| | Correct / evaluated | % |
|---|---|---|
| **All verify cases** | **36 / 37** | **97.3 %** |
| deterministic | 15 / 15 | 100 % |
| source_grounded | 11 / 12 | 91.7 % |
| mvp_behavior | 9 / 9 | 100 % |
| expert_review | 1 / 1 | 100 % (scored only as "not supported") |

By expected status: supported 12/12 · partially_supported 3/3 · contradicted 8/9 · insufficient_evidence 2/2 · no_evidence_found 3/3 · required_source_unavailable 5/5 · out_of_scope 3/3.

The single miss (A06) is **not a wrong verdict**: the claim ended as `system_error` (`verification_incomplete`) — Mizan failed closed instead of guessing. No case in the main run received a wrong evidentiary status. (A wrong verdict *did* appear in a repeated run — see section 7, bug 1.)

**Claim-type classification:** 33 / 34 (97.1 %) — the miss is A06 (no types on a system error).
**API / contract cases:** 5 / 5 (empty claim 422, >1000 chars 413, unconfirmed claim 422, duplicate ids 422, unknown run for alternative wording 404).

## 4. Extraction (Full Content)

| Metric | Result |
|---|---|
| Expected claims found | 6 / 7 (85.7 %) |
| Claim type of found claims | 6 / 6 |
| Final status of found claims | 6 / 6 |
| "No claim" / max-claims rules (advice only, injection) | 2 / 2 |
| Cases fully correct | 5 / 6 |

Miss: E02 — the extractor rewrote «إن الله مع الصابرين» as «الله مع الصابرين» (dropped the quotation marks and «إن»). Three words without quotation marks are below Mizan's 4-word implicit-quote threshold, so the claim became `no_evidence_found`. Probes: 3 more extractions gave «أن الله مع الصابرين», «إن الله مع الصابرين», «قال الله تعالى: إن الله مع الصابرين» (all verifiable). See section 7.

## 5. Retrieval

| Metric | Result |
|---|---|
| Expected trusted source present in the result evidence | 25 / 25 (100 %) |
| Expected reference (surah:ayah) present | 12 / 12 (100 %) |
| Top-K | **Not measurable** — the API returns only the evidence used in the final result, not the ranked candidate list. The architecture was not changed to expose it, and no semantic retrieval was added. |

## 6. Citation and traceability (all main-run results)

| Check | Result |
|---|---|
| Evidence items from an allowlisted source with a Quranpedia address | 88 / 88 |
| `source_url` = `https://api.quranpedia.net` + `source_address` | 88 / 88 |
| `text_sha256` = SHA-256 of the returned text | 88 / 88 |
| Quran evidence: text **and** surah/ayah identical to the Mushaf 1 dump | 43 / 43 |
| Evidence spans that occur verbatim in their evidence text | 87 / 87 |
| Assessments pointing to evidence missing from the result (invented citations) | 0 |
| Results whose Final Validation Gate checks all passed | 47 / 47 |

Re-run after the fix: 50/50 evidence items, 45/45 spans, 17/17 gates.

## 7. Failures found and fixes

**Bug 1 — FIXED: a dropped part of the claim could yield `supported`.**
A03 «نزل قوله تعالى «إن الصفا والمروة من شعائر الله» في الأنصار، وكان ذلك في السنة الأولى من الهجرة». Run 1 was correctly `partially_supported`; run 3 was **`supported`** because the LLM evidence analysis returned only the «في الأنصار» component and silently omitted «وكان ذلك في السنة الأولى من الهجرة». This is the most serious error type for Mizan (an unproven detail presented as supported).
Fix (`backend/app/pipeline/verification.py`, `uncovered_parts`): after the tafsir/asbab analysis, any run of the claim that no component covers and that has ≥ 3 content words (framing words such as «معنى قوله تعالى» and quoted ayah text excluded) becomes its own substantive component with **no evidence** → `not established`. The status rules were not changed. Checked offline against every tafsir/asbab result of the main run: it fires only on A03 run 3 and changes nothing else.
Regression tests: `test_part_of_the_claim_omitted_by_the_analysis_is_not_established_never_supported`, `test_uncovered_parts_ignore_framing_words_and_punctuation`. Live re-run of all 13 tafsir/asbab cases (18 runs): every status within expectations, A03 `partially_supported` 3/3.

**Failure 2 — NOT FIXED (LLM output, fails closed): A06 ended as `system_error`.**
A06 failed in 3 of 7 attempts overall (main run `verification_incomplete`; later `llm_invalid_response` 1/3 and 1/2); the other 4 attempts were `contradicted` ×2 or `insufficient_evidence` ×2, all correct. The model's answer was rejected by strict validation (truncated / invalid JSON / wrong structure — the exact subtype is in the local backend log, not captured here). Mizan behaves as specified: no partial verdict, a retryable system error. Not tuned.

**Failure 3 — NOT FIXED (LLM variance, mitigated by the review step): E02 extraction dropped «إن».**
1 of 4 extractions. The user sees and can edit every extracted claim before confirming it. A prompt change could not be shown to help without many more paid runs, so it was not made (no tuning).

**Provider failures (excluded from accuracy):** 2 × HTTP 429 `llm_rate_limited` in 67 main-run calls (O01, A03 run 2).

**Final real smoke after the fix:** `./scripts/smoke-all.sh` on `8fdc4e4` (developer Mac) — all passed, `smoke_verification` 15/15, Dorar calls 0.

## 8. Stability (repeated runs)

9 cases × 3 runs (stability.json). Status stable in 8 / 9 before the fix (A03 — bug 1); after the fix A03 is 3/3 `partially_supported`. Q02, Q04, T01, T02, A01, H04, I02 and E01 statuses were identical in every usable run. Evidence set varied for T02 (5 / 3 / 2 items, same status and same ayah) because the LLM cites different passages. E01 extraction wording varied (one run reworded both claims) but the claims, their types and statuses were identical.

## 9. LLM-only baseline

**Not run.** A fair baseline would need a separate script calling Gemini directly with the project key outside Mizan (key handling is off-limits in this project) and extra free-tier quota already near its limit; it would also not be comparable on traceability, because an LLM-only answer has no allowlisted record, address or hash to check — the property this evaluation measures in section 6. Documented instead of approximated.

## 10. Limitations of this evaluation

- 49 cases built by the developer; Quran ground truth is mechanical, tafsir/asbab ground truth comes from the allowlisted passages, not from a scholar. T06 needs an expert; no expert review took place.
- Small LLM-dependent sample: one run per case except the 9 stability cases; numbers can move by a case or two between runs.
- `conflicting_evidence`, source outages and Top-K were not measurable live (section 2/5).
- Hadith is never verified (Dorar unavailable by policy) — those cases test correct abstention only.

## 11. ملخص للتسليم

قُيِّم ميزان على 49 حالة نصية عبر واجهة البرمجة الحقيقية (67 تشغيلًا): دقة الحالة 36 من 37 (97.3%) بعد استبعاد حالة واحدة فشلت بسبب حدّ المزوّد (429)، ولم تُعطِ أي حالة في التشغيل الرئيسي حكمًا خاطئًا (الحالة الوحيدة الخاطئة انتهت بخطأ نظام آمن). الاستخراج: 6 من 7 ادعاءات متوقعة. الاسترجاع: المصدر المتوقع 25 من 25 والموضع المتوقع 12 من 12. التوثيق: 88 من 88 دليلًا من مصادر معتمدة بعنوان وبصمة صحيحين، و43 من 43 آية مطابقة للمصحف، و87 من 87 مقتطفًا حرفيًا، و47 من 47 نتيجة اجتازت بوابة التحقق، دون أي استشهاد مختلق. كشف التكرار خللًا واحدًا مهمًا (إسقاط جزء من الادعاء أدى إلى «مدعوم» بدل «مدعوم جزئيًا») وأُصلح باختبار انحدار وإعادة تشغيل حية.
