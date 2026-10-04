"""Local, read-only index of the official Quranpedia Mushaf 1 dump (approved 2026-10-04).

* Data: `mushafs-1.json.gz` from https://quranpedia.net/dumps (checksum-verified, versioned)
  plus corrections from `GET /v1/changes` — obtained ONLY via `python -m app.cli.sync_quran_dump`.
  Stored git-ignored under `backend/data/quranpedia/` (never committed).
* Mushaf 1 text is diacritized and matches the printed King Fahd mushaf; it is NOT Uthmani rasm.
* Matching uses `normalize_for_matching` only; displayed/stored text is the provider text
  with the BOM removed.

The index RESOLVES ayahs (quotes, explicit references, validated hints, keywords). It never
decides whether a claim is true.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.claim import AyahRetrievalHint
from app.domain.enums import PipelineStage
from app.domain.errors import SourceUnavailableError
from app.domain.evidence import AyahRef
from app.pipeline.arabic_text import normalize_for_matching

MUSHAF_ID = 1
TOTAL_AYAHS = 6236
TOTAL_SURAHS = 114
DUMP_FILE = "mushafs-1.json.gz"
META_FILE = "mushafs-1.meta.json"
PATCH_FILE = "mushafs-1.patches.json"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "quranpedia"

#: Minimum consecutive (normalised) words for a quote match.
MIN_QUOTE_WORDS = 4
#: Maximum ayahs a single hint / reference range may expand to.
MAX_RANGE_AYAHS = 10

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_PREFIXES = ("وبال", "وال", "بال", "فال", "كال", "لل", "ال", "و", "ف")
_STOPWORDS = frozenset(
    normalize_for_matching(w)
    for w in (
        "في من على الى إلى عن أن إن ان كان كانت هذا هذه ذلك تلك التي الذي الذين ما لا لم لن "
        "قد ثم أو او بل كل هو هي هم انه أنه إنه قال قوله تعالى الله سبحانه وتعالى عز وجل "
        "آية الآية سورة رقم يعني أي اي أيها مع عند بعد قبل حتى إذا اذا معنى نزلت نزل"
    ).split()
)
_REF_WORDS = frozenset({"الايه", "ايه", "الايات", "ايات", "رقم", ":", "من", "في"})


class QuranDataMissingError(SourceUnavailableError):
    """The official Mushaf 1 data is not synced/valid (configuration, never evidence)."""

    retryable = False


@dataclass(frozen=True)
class QuranAyah:
    quranpedia_ayah_id: int
    surah_number: int
    ayah_number: int
    surah_name_ar: str
    #: Provider text with the BOM removed (display / evidence text).
    text: str
    normalized: str
    page_number: int | None

    @property
    def ref(self) -> AyahRef:
        return AyahRef(
            surah_number=self.surah_number,
            ayah_number=self.ayah_number,
            quranpedia_ayah_id=self.quranpedia_ayah_id,
        )


@dataclass(frozen=True)
class QuoteMatch:
    ayahs: tuple[QuranAyah, ...]
    matched_words: int


def clean_ayah_text(text: str) -> str:
    return text.replace("﻿", "").strip()


def _strip_prefix(token: str) -> str:
    for p in _PREFIXES:
        if token.startswith(p) and len(token) - len(p) >= 3:
            return token[len(p) :]
    return token


def keyword_tokens(text: str) -> list[str]:
    out: list[str] = []
    for tok in normalize_for_matching(text.translate(_ARABIC_DIGITS)).split():
        if tok in _STOPWORDS or tok.isdigit():
            continue
        tok = _strip_prefix(tok)
        if len(tok) >= 3 and tok not in _STOPWORDS:
            out.append(tok)
    return out


def _find_mushaf(node: Any) -> dict | None:
    if isinstance(node, dict):
        if isinstance(node.get("surahs"), list):
            return node
        for v in node.values():
            found = _find_mushaf(v)
            if found:
                return found
    return None


class QuranIndex:
    def __init__(
        self,
        ayahs: list[QuranAyah],
        *,
        version: str,
        mushaf_id: int = MUSHAF_ID,
        expected_total: int | None = TOTAL_AYAHS,
    ) -> None:
        if expected_total is not None and len(ayahs) != expected_total:
            raise ValueError(
                f"Mushaf {mushaf_id} must contain {expected_total} ayahs, got {len(ayahs)}"
            )
        ids = [a.quranpedia_ayah_id for a in ayahs]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate Quranpedia ayah ids in Mushaf data")
        if not version:
            raise ValueError("a data version is required")
        self.version = version
        self.mushaf_id = mushaf_id
        self._by_id = {a.quranpedia_ayah_id: a for a in ayahs}
        self._by_loc = {(a.surah_number, a.ayah_number): a for a in ayahs}
        self._surah_counts: dict[int, int] = defaultdict(int)
        self._surah_names: dict[int, str] = {}
        for a in ayahs:
            self._surah_counts[a.surah_number] = max(
                self._surah_counts[a.surah_number], a.ayah_number
            )
            self._surah_names[a.surah_number] = a.surah_name_ar
        # Word stream per surah (quote matching may span consecutive ayahs).
        self._words: dict[int, list[str]] = {}
        self._word_ayah: dict[int, list[int]] = {}
        self._ngrams: dict[tuple[str, ...], list[tuple[int, int]]] = defaultdict(list)
        for s in sorted(self._surah_counts):
            words: list[str] = []
            owners: list[int] = []
            for n in range(1, self._surah_counts[s] + 1):
                a = self._by_loc.get((s, n))
                if a is None:
                    continue
                for w in a.normalized.split():
                    words.append(w)
                    owners.append(a.quranpedia_ayah_id)
            self._words[s] = words
            self._word_ayah[s] = owners
            for i in range(len(words) - MIN_QUOTE_WORDS + 1):
                self._ngrams[tuple(words[i : i + MIN_QUOTE_WORDS])].append((s, i))
        # Keyword index.
        self._postings: dict[str, set[int]] = defaultdict(set)
        for a in ayahs:
            for tok in set(keyword_tokens(a.text)):
                self._postings[tok].add(a.quranpedia_ayah_id)
        self._n = max(len(ayahs), 1)
        # Surah names for reference parsing ("سورة البقرة" -> "البقره" and "بقره").
        self._name_lookup: dict[str, int] = {}
        for s, name in self._surah_names.items():
            norm = re.sub(r"^سوره\s+", "", normalize_for_matching(name))
            if not norm:
                continue
            self._name_lookup[norm] = s
            if norm.startswith("ال") and len(norm) > 4:
                self._name_lookup.setdefault(norm[2:], s)

    # ------------------------------------------------------------ construction

    @classmethod
    def from_payload(
        cls,
        payload: Any,
        *,
        version: str,
        patches: list[dict] | None = None,
        expected_total: int | None = TOTAL_AYAHS,
    ) -> QuranIndex:
        mushaf = _find_mushaf(payload)
        if mushaf is None:
            raise ValueError("no 'surahs' list found in Mushaf data")
        patch_text = {(int(p["surah"]), int(p["ayah"])): str(p["text"]) for p in (patches or [])}
        ayahs: list[QuranAyah] = []
        for surah in mushaf["surahs"]:
            s = int(surah["id"])
            name = str(surah.get("name") or "").strip()
            if not (1 <= s <= TOTAL_SURAHS) or not name:
                raise ValueError(f"invalid surah record: {s!r}")
            for a in surah.get("ayahs") or []:
                n = int(a["number"])
                text = clean_ayah_text(str(patch_text.get((s, n), a.get("text")) or ""))
                if not text:
                    raise ValueError(f"empty ayah text at {s}:{n}")
                page = a.get("page_number")
                ayahs.append(
                    QuranAyah(
                        quranpedia_ayah_id=int(a["id"]),
                        surah_number=s,
                        ayah_number=n,
                        surah_name_ar=name,
                        text=text,
                        normalized=normalize_for_matching(text),
                        page_number=int(page) if page is not None else None,
                    )
                )
        return cls(ayahs, version=version, expected_total=expected_total)

    @classmethod
    def load(cls, data_dir: Path | None = None) -> QuranIndex:
        d = Path(data_dir or DEFAULT_DATA_DIR)
        dump, meta_path = d / DUMP_FILE, d / META_FILE
        if not dump.exists() or not meta_path.exists():
            raise QuranDataMissingError(
                "Official Quran data (Quranpedia Mushaf 1) is not synced. "
                "Run: python -m app.cli.sync_quran_dump",
                stage=PipelineStage.HYBRID_RETRIEVAL,
            )
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        raw = dump.read_bytes()
        if hashlib.sha256(raw).hexdigest() != meta.get("sha256"):
            raise QuranDataMissingError(
                "Local Mushaf 1 dump does not match its recorded checksum; re-run the sync.",
                stage=PipelineStage.HYBRID_RETRIEVAL,
            )
        patches_path = d / PATCH_FILE
        patches = (
            json.loads(patches_path.read_text(encoding="utf-8")) if patches_path.exists() else []
        )
        payload = json.loads(gzip.decompress(raw))
        return cls.from_payload(payload, version=str(meta["source_version"]), patches=patches)

    # ------------------------------------------------------------ lookups

    def get(self, surah: int, ayah: int) -> QuranAyah | None:
        return self._by_loc.get((surah, ayah))

    def by_id(self, quranpedia_ayah_id: int) -> QuranAyah | None:
        return self._by_id.get(quranpedia_ayah_id)

    def surah_ayah_count(self, surah: int) -> int:
        return self._surah_counts.get(surah, 0)

    def surah_name(self, surah: int) -> str | None:
        return self._surah_names.get(surah)

    def ayah_range(self, surah: int, start: int, end: int | None = None) -> list[QuranAyah] | None:
        """Ayahs surah:start..end, or None if any part does not exist / range too large."""
        end = start if end is None else end
        count = self.surah_ayah_count(surah)
        if count == 0 or start < 1 or end < start or end > count:
            return None
        if end - start + 1 > MAX_RANGE_AYAHS:
            return None
        return [self._by_loc[(surah, n)] for n in range(start, end + 1)]

    # ------------------------------------------------------------ resolution

    def validate_hint(self, hint: AyahRetrievalHint) -> list[QuranAyah] | None:
        """Validate an LLM retrieval hint against the official source. None => discard."""
        return self.ayah_range(hint.surah_number, hint.ayah_start, hint.ayah_end)

    def find_quotes(self, text: str, *, limit: int = 10) -> list[QuoteMatch]:
        """Maximal runs of >= MIN_QUOTE_WORDS consecutive words shared with the Quran text."""
        words = normalize_for_matching(text).split()
        runs: dict[tuple[int, int], int] = {}
        for i in range(len(words) - MIN_QUOTE_WORDS + 1):
            for s, pos in self._ngrams.get(tuple(words[i : i + MIN_QUOTE_WORDS]), []):
                if pos > 0 and i > 0 and runs.get((s, pos - 1)) is not None:
                    # continuation of a run that started earlier: skip (maximal runs only)
                    if self._words[s][pos - 1] == words[i - 1]:
                        continue
                k = MIN_QUOTE_WORDS
                stream = self._words[s]
                while (
                    i + k < len(words) and pos + k < len(stream) and words[i + k] == stream[pos + k]
                ):
                    k += 1
                runs[(s, pos)] = max(runs.get((s, pos), 0), k)
        matches: list[QuoteMatch] = []
        seen: set[tuple[int, ...]] = set()
        for (s, pos), k in sorted(runs.items(), key=lambda kv: (-kv[1], kv[0])):
            ids = tuple(dict.fromkeys(self._word_ayah[s][pos : pos + k]))
            if ids in seen:
                continue
            seen.add(ids)
            matches.append(QuoteMatch(tuple(self._by_id[a] for a in ids), k))
            if len(matches) >= limit:
                break
        return matches

    def parse_references(self, text: str) -> list[QuranAyah]:
        """Explicit surah + ayah references in the text, e.g. «سورة البقرة الآية 255»,
        «[البقرة: 255]», «الآيات 1-5 من سورة العلق». Mentions that do not resolve to existing
        ayahs are ignored (never guessed)."""
        raw = text.translate(_ARABIC_DIGITS)
        raw = re.sub(r"[:：]", " zcolon ", raw)
        raw = re.sub(r"(\d)\s*[-–—]\s*(\d)", r"\1 zdash \2", raw)
        tokens = normalize_for_matching(raw).split()
        out: list[QuranAyah] = []

        def surah_at(idx: int) -> tuple[int, int] | None:
            for width in (3, 2, 1):
                name = " ".join(tokens[idx : idx + width])
                if name in self._name_lookup:
                    return self._name_lookup[name], idx + width
            return None

        def number_at(idx: int) -> tuple[int, int | None, int] | None:
            """(start, end, next_index) for a number (optionally a range) after ref words."""
            j = idx
            for _ in range(4):
                if j >= len(tokens):
                    return None
                tok = tokens[j]
                if tok.isdigit():
                    start, end, nxt = int(tok), None, j + 1
                    if (
                        j + 2 < len(tokens)
                        and tokens[j + 1] in {"zdash", "الي", "حتي"}
                        and tokens[j + 2].isdigit()
                    ):
                        end, nxt = int(tokens[j + 2]), j + 3
                    return start, end, nxt
                if tok not in _REF_WORDS and tok != "zcolon":
                    return None
                j += 1
            return None

        def add(surah: int, start: int, end: int | None) -> None:
            rng = self.ayah_range(surah, start, end)
            if rng:
                out.extend(rng)

        for i, tok in enumerate(tokens):
            if tok == "سوره":  # "سورة X [الآية] N"
                got = surah_at(i + 1)
                if got:
                    num = number_at(got[1])
                    if num:
                        add(got[0], num[0], num[1])
            elif tok == "zcolon" and i + 1 < len(tokens) and tokens[i + 1].isdigit():
                for width in (3, 2, 1):  # "X: N"
                    if i - width >= 0 and " ".join(tokens[i - width : i]) in self._name_lookup:
                        num = number_at(i + 1)
                        if num:
                            add(self._name_lookup[" ".join(tokens[i - width : i])], num[0], num[1])
                        break
            elif tok in {"الايه", "الايات", "ايه"}:  # "الآية N من سورة X"
                num = number_at(i + 1)
                if num:
                    j = num[2]
                    if (
                        j + 1 < len(tokens)
                        and tokens[j] in {"من", "في"}
                        and tokens[j + 1] == "سوره"
                    ):
                        got = surah_at(j + 2)
                        if got:
                            add(got[0], num[0], num[1])
        return list(dict.fromkeys(out))

    def keyword_search(
        self, text: str, *, limit: int = 5, min_tokens: int = 2
    ) -> list[tuple[QuranAyah, float]]:
        """Weakest strategy: idf-weighted distinct-keyword overlap (NOT a truth score)."""
        tokens = list(dict.fromkeys(keyword_tokens(text)))
        scores: dict[int, float] = defaultdict(float)
        counts: dict[int, int] = defaultdict(int)
        for tok in tokens:
            post = self._postings.get(tok)
            if not post:
                continue
            idf = math.log(1 + self._n / len(post))
            for aid in post:
                scores[aid] += idf
                counts[aid] += 1
        ranked = sorted(
            (aid for aid in scores if counts[aid] >= min_tokens),
            key=lambda aid: (-scores[aid], aid),
        )
        return [(self._by_id[aid], round(scores[aid], 4)) for aid in ranked[:limit]]
