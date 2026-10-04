# Integration TODO — what must be provided before connecting real services

Nothing below has been assumed or invented. Adapters are placeholders that raise
`SourceNotConnectedError`; they advertise no supported retrieval methods.

## Quranpedia (Task 5) — `backend/app/sources/quranpedia.py`

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

## LLM provider (Task 4+) — `backend/app/llm/`

- [ ] Anthropic is the planned first adapter (`llm/anthropic.py`, not wired). Needs `ANTHROPIC_API_KEY`, model choice.
- [ ] Data-handling review for sending user content to the provider.

## OCR (Task 3) — DECIDED: Google Cloud Vision (`DOCUMENT_TEXT_DETECTION`)

Implemented in `backend/app/ocr/google_vision.py` behind the provider-neutral `OcrProvider`
contract. Calls run only on the backend; the key is sent in the `x-goog-api-key` header and is
never exposed to the frontend, logs or API responses.

To enable the live integration:
- [ ] Google Cloud project with the **Cloud Vision API** enabled and **billing enabled**
      (required by Google even within the monthly free units).
- [ ] Create an API key and **restrict it to the Cloud Vision API** (and, in production, to the
      backend's egress IPs).
- [ ] In `backend/.env`: `OCR_PROVIDER=google_vision` and `GOOGLE_VISION_API_KEY=<key>`.
- [ ] Run one real Arabic image through `/full-content` and confirm the review screen.

Facts from official docs (checked 2026-10-04): Arabic (`ar`) supported; 20 MB image limit and
10 MB JSON request limit (inline base64); 75 MP OCR pixel cap; confidence 0–1 on
page/block/paragraph/word/symbol; first 1,000 units/month free then $1.50 per 1,000; real-time
images processed in memory and not used for training.

Upload limit (LOCKED): **7 MB, JPG/PNG** (`MAX_UPLOAD_BYTES`), so base64 stays under 10 MB.

Approved (Task 3 review):
- [x] Short privacy notice shown before image upload (images go to Google Cloud Vision for OCR only).
- [x] Default global endpoint for the MVP (no EU/US regional endpoint).
- [x] Low-confidence review threshold 0.6 — OCR review signal only; never affects verification
      status or Evidence Strength.
- [ ] One real Arabic OCR test after the API key is configured (required before closing Task 3).

Later:
- [ ] Uthmani/diacritics quality: no provider documents Uthmani support; user review is mandatory.
