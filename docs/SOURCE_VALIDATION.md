# Source Integration Validation (pre-Task 5) — 2026-10-04

Research only. No retrieval, classification, verification, scoring or verdicts were
implemented. The Trusted Sources Policy is unchanged.

## How the live data was obtained (read this first)

- The Cowork sandboxes cannot open direct HTTP connections to `api.quranpedia.net` or
  `dorar.net` (egress proxy rejects the CONNECT). No unofficial mirror/wrapper was used instead.
- Live requests were made to the **official endpoints** through the WebFetch tool. That tool
  relays the body through a summarizing model: **field names and structure are reliable, but
  values are not byte-exact** (in one response it translated `about`/`full_name` to English).
- Byte-exact confirmation: run `python -m app.cli.validate_sources` on the Mac (fixed public
  requests only, no credentials, prints structure + traceability checks).

## A. Quranpedia — official API

Docs: https://quranpedia.net/api-docs · Base: `https://api.quranpedia.net/v1` · JSON · GET only.

| Endpoint (tested live) | Purpose | Observed top-level fields |
|---|---|---|
| `GET /ayah/{surah}/{ayah}/options` | ayah + available services | `id, number, surah, page_number, text, marker, options[]` |
| `GET /mushafs` | Quran editions | `id, name, short_name, description, font_file, rawi{}, qiraa{}` |
| `GET /mushafs/{mushaf_id}/{surah}/{ayah}` | ayah text in a mushaf | `id, number, surah, page_number, text, marker, options[], number_in_hafs[]` |
| `GET /surah/information/{surah}` | surah metadata | `introduction, surah_number, surah_type, words_count, descent, grace, prophet, revelation` (each `{title, value}`) |
| `GET /surah/tafsirs/{surah}` | surah-level tafsir books | `[{id, name, short_name, author}]` (only surah-specific works; `[]` for 2) |
| `GET /categories/books` | category tree | `[{id, name, children[{id,name,parent_id,count}], count}]` |
| `GET /category/11/books` | books in "أسباب النزول" | `[{id, name, author}]` |
| `GET /search/{query}/books` | full-text search in book contents | `items[{book_info{…}, highlighted_text}]`, `currentPage, perPage, total, lastPage` (seen top-level and under `pagination`) |
| `GET /book/{book_id}` | book metadata | `id, name, short_name, type, language{}, category{}, parts, publish_year, edition, nasher, has_image, about, author{id, ar_name, full_name}, mohaqeq, introducer, reviewer, translator, contents_url, book_attachments[], relative_ayah_service` |
| `GET /ayah/{surah}/{ayah}/book/{book_id}` | book content linked to an ayah | `book{…}`, `content[{text, part, page, ayahs, image?}]` |

Docs also list `GET /changes?since=YYYY-MM-DD` (corrections per content type incl.
`ayah_book_contents`, `since` within the last year) — not called yet.

### B. Source IDs (verified via `GET /book/{id}` and `GET /ayah/…/book/{id}`)

| Mizan source | Quranpedia book id(s) | Evidence | Notes |
|---|---|---|---|
| Quran | mushaf `1` ("مصحف حفص", مجمع الملك فهد) | `/mushafs/1/2/255` → 200 | ayah `id` = global ayah number (2:255 → 262) |
| Tafsir al-Muyassar | **2012** (author: مجمع الملك فهد لطباعة المصحف الشريف; listed in the official tafsir fragment) and **32** (author "مجموعة من المؤلفين", publisher مجمع الملك فهد, 2nd ed. 1430, page images) | both `type=tafsir`, `relative_ayah_service=tafsir`, content for 2:255 | **choose one** |
| Tafsir Ibn Kathir | **136** (دار طيبة, ed. 2, 1420, 8 parts, محقق: سامي سلامة) and **331** (دار الكتب العلمية, 1419, محقق: محمد حسين شمس الدين) | both `relative_ayah_service=tafsir`, content for 2:255 | **choose one**; 14745/14776/14778/14779 exist but return no ayah content |
| Asbab al-Nuzul — al-Wahidi | **2919** ("أسباب نزول القرآن - الواحدي") | `type=asbab`, content for 2:158 | **`author: null`, edition/publisher empty**; 235/242/821/1473/2447 are Wahidi editions WITH author metadata but return **no ayah content** (235 checked) |
| Al-Muharrar fi Asbab al-Nuzul | **460** (خالد بن سليمان المزيني, دار ابن الجوزي, ط1 1427) | `type=asbab`, 6 content items for 2:158; `[]` for 2:255 | complete metadata |

The official dumps page states asbab al-nuzul = "2 books" — consistent with 2919 + 460.

### Quran text form
- `text` is a single field, prefixed with U+FEFF (BOM; sometimes twice) — must be stripped.
- Contains full tashkeel, dagger alef (U+0670) and Quranic waqf marks (U+06D6–06DC), but in the
  observed sample it is written **without** alef wasla (ٱ U+0671) and with standard spelling
  (e.g. `السَّمَاوَاتِ`, not `ٱلسَّمَٰوَٰتِ`). It is a **diacritized text, not confirmed to be
  Uthmani rasm** (to be byte-confirmed by the local script; mushaf 2 is also checked there).
- **No normalized/search text field** is returned; Mizan would derive it locally.
- Surah **name** was not returned by the endpoints tested (`surah` is a number string).

## C. Dorar al-Sunniyah — official API

Official page: https://dorar.net/article/389 — `https://dorar.net/dorar_api.json?skey=<text>`
(+ optional `callback=` for JSONP). No other parameters, pagination, limits or terms documented.

Live request: `skey=إنما الأعمال بالنيات` (also `من حسن إسلام المرء`).

- Response: JSON `{"ahadith": {"result": "<HTML string>"}}` (JSONP only if `callback` given).
- The HTML contains 15 result blocks:
  `<div class="hadith">N - …text with <span class="search-keys">…</span>…</div>` then
  `<div class="hadith-info">` with `<span class="info-subtitle">LABEL:</span> value` for
  `الراوي`, `المحدث`, `المصدر`, `الصفحة أو الرقم`, `خلاصة حكم المحدث` (ruling in an inner `<span>`).
- HTML is **malformed** (stray `</span>` after the narrator) and includes a `<head><link
  rel="canonical" href="https://dorar.net/dorar_api.json">`.
- **No per-hadith id, no data-* attributes, no per-hadith URL.** The only link is
  `https://dorar.net/hadith/search?q=<query>` ("المزيد").
- Some texts are **abbreviated** with `. . .` (e.g. result 1 and 2 above).
- Narrator sometimes in brackets (`[عمر بن الخطاب]`) — must be kept verbatim.
- The ruling is free text (e.g. `صحيح غريب`, `رجاله ثقات`, `خطأ [يعني في إسناده] …`,
  `هذا أصح بانقطاعه …`) — it is the muhaddith's wording, **not a normalized grade**.

Safe parsing (if approved): `json.loads` (never `eval` JSONP; never send `callback`), tolerant
HTML parser (stdlib `html.parser`), extract text only, require all five labels per block or
drop the block, never render the raw HTML.

## D. Mapping to Mizan's Evidence schema

### Common `Evidence` fields

| Mizan field | Quranpedia | Dorar |
|---|---|---|
| `text` | `text` / `content[].text` (strip BOM; strip HTML) | `div.hadith` text (strip numbering + spans) |
| `source_name` | `book.name` / `short_name`; Quran: fixed | `المصدر` (book), Dorar as provider |
| `provider` | quranpedia | dorar_al_sunniyah |
| `reference` | constructible: surah:ayah + book + `part`/`page` | constructible: `المحدث` + `المصدر` + `الصفحة أو الرقم` |
| `source_url` (optional) | no documented per-record URL; `https://quranpedia.net/book/{id}` seen in fragments; documented embed `https://quranpedia.net/embed?surah=&ayah=&type=` | only search URL `https://dorar.net/hadith/search?q=` (not a record) |
| `source_record_id` (required) | Quran: ayah `id` ✔. Tafsir/asbab content items: **no id** ✘ | **none** ✘ |

### Per-type metadata

| Mizan field | Source field | Status | Transformation |
|---|---|---|---|
| Quran `surah_number` | `surah` | ✔ | str→int |
| Quran `surah_name_ar` | — | ✘ not in tested endpoints | gap (not to be invented) |
| Quran `ayah_number` | `number` | ✔ | — |
| Quran `ayah_text_uthmani` | `text` | ⚠ available, rasm unconfirmed | strip BOM |
| Quran `ayah_text_normalized` | — | derived | Mizan `normalize_for_matching` |
| Tafsir `tafsir_name` | `book.name`/`short_name` | ✔ | — |
| Tafsir `author` | `book.author.ar_name` | ✔ (2012, 32, 136, 331) | — |
| Tafsir `surah_number` | request param | ⚠ not echoed | from request |
| Tafsir `surah_name_ar` | — | ✘ | gap |
| Tafsir `ayah_start/end` | `content[].ayahs` (global ayah id as string) | ⚠ single value seen; range format unknown | global→surah:ayah |
| Tafsir `chunk_id` | — | ✘ | gap |
| Asbab `asbab_source_name` | `book.name` | ✔ | — |
| Asbab `author` | `book.author.ar_name` | ✔ 460 · **✘ 2919 (null)** | gap for Wahidi |
| Asbab `chunk_id` | — | ✘ | gap |
| Asbab `relation_type` | — | ✘ not provided | gap (must not be guessed) |
| Hadith `hadith_text` | block text | ✔ (may be abbreviated) | strip markup |
| Hadith `hadith_text_normalized` | — | derived | local |
| Hadith `narrator` | `الراوي` | ✔ | verbatim |
| Hadith `muhaddith` | `المحدث` | ✔ | verbatim |
| Hadith `hadith_source` | `المصدر` | ✔ | verbatim |
| Hadith `source_reference` | `الصفحة أو الرقم` | ✔ | verbatim |
| Hadith `grading` | `خلاصة حكم المحدث` | ✔ attributed to `المحدث` in the same block | verbatim, never normalized |
| Hadith `grading_details` | — | ✘ separate details not returned | null |
| Hadith `dorar_result_id` | — | ✘ | gap |

### Traceability chain (Evidence → Scientific Source → Provider → Original Record → Reference/URL)

- **Quran:** complete (ayah `id` is a stable record id; reference from surah/ayah). URL: only
  the documented embed URL.
- **Tafsir / Asbab:** broken at *Original Record/Chunk* — content items have no id; `(part,
  page, ayahs)` is **not unique** (two Ibn Kathir items share page 673 for 2:255).
- **Hadith:** broken at *Original Record* and *URL* — the scholarly reference (muhaddith, book,
  page/number) is present, but no Dorar record id or record URL.

## E. Operational rules (official text only)

Quranpedia (https://quranpedia.net/api-docs#usage-policy, https://quranpedia.net/dumps?lang=en):
- No authentication. "Requests are limited per IP to `120/minute` and `10,000/day`"; 429 body
  links the usage policy.
- "This API is *not* a download service." Bulk mirroring discouraged; use the official versioned
  dumps (gzipped JSON, SHA-256, current version 2026-10-03) instead of scraping.
- Attribution "is required only when publishing the data itself … as a downloadable database
  or dataset"; live apps "do *not* have to credit us". Dumps license: https://quranpedia.net/dumps/LICENSE.md (not yet read).
- "build on the API live and credit Quranpedia — don't freeze a copy of a text that is still
  being corrected"; use `/changes?since=` to resync.
- Caching of live responses: **not explicitly addressed → unresolved.**

Dorar (https://dorar.net/article/389, https://dorar.net/article/111):
- No authentication, no documented rate limits, pagination or caching rules.
- The API is described as a service for site owners "عرض نتائج البحث في الموسوعة الحديثية".
- Rights page: "المواد غير القابلة للتنزيل وإنما هي للبحث والتصفح كالموسوعة الحديثية لا يسمح
  بنسخها وجعلها للاستخدام من خارج الموقع سواء على جهاز خاص أوأقراص (سي دي) ولا بأس بنسخ نتيجة
  بحث ونشرها للفائدة." → storing/caching/indexing Dorar results is **not permitted as written /
  unresolved without written permission** from Dorar. Contact listed on the API page.

## Viability summary

| Source | Status |
|---|---|
| Quran | Viable (pending decisions: rasm form, surah name source) |
| Tafsir al-Muyassar | Retrievable; **chunk-id gap**; id choice 2012 vs 32 |
| Tafsir Ibn Kathir | Retrievable; **chunk-id gap**; id choice 136 vs 331 |
| Asbab — al-Wahidi | Retrievable (2919); **chunk-id gap + author missing in API** |
| Al-Muharrar | Retrievable (460); **chunk-id gap** |
| Hadith via Dorar | **Not viable for the current schema**: no record id/URL; storage terms restrictive |

---

# Blocker resolution round (2026-10-04, later) — research only, Task 5 NOT started

## 1. Quranpedia record identity — NOT RESOLVED
- Official dumps (https://quranpedia.net/dumps?lang=en, manifest https://quranpedia.net/dumps/manifest.json,
  version 2026-10-02) include `tafsir-book-{32,2012,136,331}.json.gz` and
  `asbab-book-{2919,460}.json.gz`, each with SHA-256. The dumps page documents tafsir/asbab book
  files as having the **same schema as `/v1/ayah/{s}/{a}/book/{id}`**, i.e. the live content items
  (`text, part, page, ayahs`) that carry **no passage id**.
- The files are gzip; they could not be opened from the Cowork sandbox. Confirm locally:
  `python -m app.cli.validate_sources --dumps` (checks SHA-256 vs manifest, lists record keys,
  id-like keys, (part,page,ayahs) uniqueness, `ayahs` format, and `/changes` → `ayah_book_contents` rows).
- `/v1/changes` exposes `ayah_book_contents` as a change type with `refetch` paths (rows observed for
  `ayahs`: `{mushaf, surah, ayah, changed_at, refetch}`); the row shape for book contents was not
  observable via WebFetch — included in the local check.
- Traceability via dumps: Evidence → Source (book id + manifest version + sha256) → Provider
  (Quranpedia) → **Original Record: still no official passage id** → Reference (book/part/page,
  ayah) — chain still broken at the record step unless the local check finds an id.
- Dumps license (manifest `license` block / https://quranpedia.net/dumps/LICENSE.md): use inside apps
  needs no attribution; republishing as a dataset requires credit + link + version; content is
  continuously corrected — state the version and re-sync via `/changes`. No explicit caching clause
  beyond this. Third-party components (morphology GPL, syntax MIT) are not used by Mizan.
  Contact: quranpedia.help@gmail.com (manifest).

## 2. Editions (official metadata)
| | 2012 | 32 |
|---|---|---|
| author | مجمع الملك فهد لطباعة المصحف الشريف | مجموعة من المؤلفين |
| edition / year / publisher | — / — / — | الثانية / 1430 / مجمع الملك فهد |
| page numbers | `page` = global ayah no. (not a print page) | printed page (2:255 → p. 42) + page image + PDFs |
| dump | 630 KB | 610 KB |
**Recommend 32** — complete edition metadata and real printed-page references (verifiable against the page image).

| | 136 | 331 |
|---|---|---|
| edition | دار طيبة, ط2, 1420, 8 parts, محقق: سامي سلامة | دار الكتب العلمية, ط1 1419, محقق: محمد حسين شمس الدين |
| short_name | تفسير ابن كثير | تفسير ابن كثير ط العلمية |
| print reference | part/page (2:255 → 1/672) | part "1"/page 512 though edition is multi-volume (`parts`=1) |
**Recommend 136** — complete edition metadata incl. muhaqqiq and volume/page structure consistent with an 8-volume print.

## 3. Remaining Quranpedia gaps
- Wahidi 2919 author: still `null` (API `/book/2919`, dumps manifest has title only) — NOT resolved; local `--dumps` also checks `books.json.gz`.
- Surah names: **RESOLVED** — `GET /v1/mushafs/{id}` → `surahs[].name` (e.g. "سورة الفاتحة").
- Quran text form: mushaf **1** = Hafs, "موافق لطبعة مجمع الملك فهد" but text is diacritized standard orthography (no ٱ);
  mushaf **2** = "بالخط العثماني … غير موافق للمطبوع" and its text IS Uthmani rasm (ٱ, ٰ, small high marks). Ayah ids
  differ per mushaf (2:255 → 262 in mushaf 1, 62512 in mushaf 2). Decision needed.
- Multi-ayah ranges: not exposed — each content item has a single `ayahs` value (Ibn Kathir 2:1 → "8"); NOT resolved.
- Asbab relation/context: no official field — NOT resolved.

## 4. Dorar — NOT RESOLVED
- Only official API remains `https://dorar.net/dorar_api.json?skey=` (https://dorar.net/article/389); no newer endpoint found on dorar.net.
- The website itself has permanent per-hadith URLs `https://dorar.net/h/{code}` (seen as link structure on the
  official search page), but the **API does not return them**; obtaining them would require scraping — not done.
- No documented single-record retrieval. Contact: email on the API page (obfuscated) and https://dorar.net/feedback.
- Storage/caching: previous finding stands (https://dorar.net/article/111).
