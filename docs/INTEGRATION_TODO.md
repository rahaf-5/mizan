# Integration TODO — what must be provided before connecting real services

Nothing below has been assumed or invented. Adapters are placeholders that raise
`SourceNotConnectedError`; they advertise no supported retrieval methods.

## Quranpedia (Task 5) — `backend/app/sources/quranpedia.py`

> **Task 5a (2026-10-04): CONNECTED.** Quran from the official Mushaf 1 dump
> (`python -m app.cli.sync_quran_dump`, stored git-ignored in `backend/data/quranpedia/`);
> tafsir/asbab live from `GET https://api.quranpedia.net/v1/ayah/{s}/{a}/book/{2012|136|2919|460}`.
> No key; 120 req/min, 10,000/day per IP. Real smoke: `python -m app.cli.smoke_retrieval`.

> Live validation results (2026-10-04), confirmed endpoints/IDs and open gaps:
> see `docs/SOURCE_VALIDATION.md`. Byte-exact check: `cd backend && python -m app.cli.validate_sources`.

Serves: Quran · Tafsir al-Muyassar · Tafsir Ibn Kathir · Asbab al-Nuzul (al-Wahidi) · Al-Muharrar fi Asbab al-Nuzul.

Needed:
- [ ] Official API documentation (base URL, endpoints, request/response schemas, pagination, errors)
- [ ] Authentication method and API key/credentials (store in `QURANPEDIA_API_KEY`, never in code)
- [ ] Rate limits, quotas, SLA / availability expectations
- [ ] Which search capabilities exist per source: exact, keyword, semantic?
- [ ] Stable record identifiers for ayat, tafsir chunks and asbab chunks (`source_record_id`, `chunk_id`)
- [ ] Canonical citation/reference format and public record URLs (`reference`, `source_url`)
- [ ] Availability of Uthmani AND normalized Quran text (or the approved normalization method)
- [ ] How asbab material is marked as direct sabab vs contextual (`relation_type`)
- [ ] Terms of use / licensing for displaying source text in Mizan

## Dorar al-Sunniyah (Task 5) — `backend/app/sources/dorar.py`

> **BLOCKED (policy: UNAVAILABLE).** Hadith-requiring claims end as `required_source_unavailable`.
> Unblock = Dorar provides per-hadith id/URL + single-record retrieval + written permission
> (display/caching); then implement this adapter and set the policy availability to AVAILABLE.

> Live validation results (2026-10-04), confirmed endpoints/IDs and open gaps:
> see `docs/SOURCE_VALIDATION.md`. Byte-exact check: `cd backend && python -m app.cli.validate_sources`.

Serves: hadith data and muhaddith rulings.

Needed:
- [ ] Official API documentation or approved access method, and usage terms
- [ ] Authentication / key requirements (`DORAR_API_KEY`)
- [ ] Fields available: hadith text, narrator, muhaddith, source book, reference, grading, grading details, result id
- [ ] How multiple gradings by different muhaddithin are returned (Mizan must preserve each, attributed)
- [ ] Search capabilities (exact / keyword / other) and rate limits
- [ ] Public record URLs for "view original source"

## Caching, indexing & semantic search (decision before Task 5)

- [ ] Are we permitted to cache source responses? For how long?
- [ ] Are we permitted to store/copy source content locally and build an index (e.g. pgvector embeddings)?
- [ ] If not, semantic search is limited to what providers offer — confirm acceptable.
- [ ] Attribution requirements when displaying cached content.

The dev database image supports pgvector, but **no semantic indexing is implemented** and no
permission to copy or index Quranpedia/Dorar content is assumed.

## LLM provider — Gemini Developer API (current MVP adapter, Task 4)

Implemented in `backend/app/llm/gemini.py` behind `LLMProvider`. Backend-only; key in the
`x-goog-api-key` header; never logged, returned, or sent to the frontend.

- Model: `gemini-3.5-flash-lite` (configurable via `GEMINI_MODEL`), `GEMINI_THINKING_LEVEL=low`.
- Structured output request: `generationConfig.responseMimeType="application/json"` +
  `generationConfig.responseJsonSchema` (as the official google-genai SDK sends to the Gemini
  Developer API). `generationConfig.responseFormat.text.mimeType` was rejected live with
  `400 INVALID_ARGUMENT` (first smoke test, 2026-10-04) and is not used.
- Facts from official docs (checked 2026-10-04): listed as a stable model; Free Tier "Free of
  charge" for input/output; structured outputs supported; free-tier rate limits are shown per
  project in Google AI Studio (not published as fixed numbers).
- [ ] **Privacy (must decide before production):** Gemini Free Tier pricing page states content
      sent on the free tier is "used to improve our products"; the paid tier states it is not.
      Only the submitted text is sent (no other app data). Decide whether a paid tier or a user
      notice is required before public launch.
- [x] Live smoke test #2 (after e7113b9): every case generic `400 INVALID_ARGUMENT`. Root cause
      found with `python -m app.cli.diagnose_gemini` (2026-10-04): model lookup, minimal,
      system_instruction, JSON MIME, trivial schema and thinkingLevel=LOW all 200; full Mizan
      schema 400; the same schema **without `maxItems`** 200. **Compatibility decision:** the
      Gemini adapter strips `maxItems` from `responseJsonSchema` only
      (`GEMINI_UNSUPPORTED_SCHEMA_KEYS`); the provider-neutral schema and Pydantic model keep the
      50-claim limit, so a response with more than 50 claims is rejected locally as
      `llm_invalid_response`. All other schema restrictions are still sent.
- [ ] Real-provider smoke test (rerun after the maxItems fix): `cd backend && python -m app.cli.smoke_claim_extraction`
      (the Cowork sandbox cannot reach generativelanguage.googleapis.com).

## OCR — REMOVED FROM MVP SCOPE (2026-10-04)

Image input and OCR are not part of the MVP (product-scope decision: OCR provider billing/account
constraints for the Saudi-based MVP setup; no lower-confidence provider for sensitive religious
content). Nothing needs to be configured. `GOOGLE_VISION_API_KEY` / `OCR_*` settings are not
read by the application. The Google Cloud Vision implementation is preserved only in Git history
(commits `0eea5da` → `f08cf42`) for a possible future version.
