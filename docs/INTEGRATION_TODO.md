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

## OCR — REMOVED FROM MVP SCOPE (2026-10-04)

Image input and OCR are not part of the MVP (product-scope decision: OCR provider billing/account
constraints for the Saudi-based MVP setup; no lower-confidence provider for sensitive religious
content). Nothing needs to be configured. `GOOGLE_VISION_API_KEY` / `OCR_*` settings are not
read by the application. The Google Cloud Vision implementation is preserved only in Git history
(commits `0eea5da` → `f08cf42`) for a possible future version.
