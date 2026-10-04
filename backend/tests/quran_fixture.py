"""Small Mushaf-shaped fixture for tests (structure of the official /v1/mushafs/{id} dump).

A handful of real ayah texts (public) plus synthetic filler so locations exist.
Used ONLY to exercise matching code — never as evidence.
"""

from __future__ import annotations

from app.sources.quran_index import QuranIndex

FATIHA = [
    "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
    "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ",
    "الرَّحْمَٰنِ الرَّحِيمِ",
    "مَالِكِ يَوْمِ الدِّينِ",
    "إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ",
    "اهْدِنَا الصِّرَاطَ الْمُسْتَقِيمَ",
    "صِرَاطَ الَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ الْمَغْضُوبِ عَلَيْهِمْ وَلَا الضَّالِّينَ",
]
BAQARAH = {
    158: "إِنَّ الصَّفَا وَالْمَرْوَةَ مِنْ شَعَائِرِ اللَّهِ ۖ فَمَنْ حَجَّ الْبَيْتَ أَوِ اعْتَمَرَ فَلَا جُنَاحَ عَلَيْهِ أَنْ يَطَّوَّفَ بِهِمَا",
    255: "﻿اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ ۚ لَا تَأْخُذُهُ سِنَةٌ وَلَا نَوْمٌ ۚ لَهُ مَا فِي السَّمَاوَاتِ وَمَا فِي الْأَرْضِ",
}
NUM_WORDS = ["صفر", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة"]


def _filler(s: int, n: int) -> str:
    digits = " ".join(NUM_WORDS[int(d)] for d in str(n))
    return f"نص اختبار سوره {NUM_WORDS[s]} موضع {digits}"


def mushaf_payload(*, extra_surah_ayahs: int = 0) -> dict:
    surahs = []
    gid = 0
    ayahs = []
    for n, text in enumerate(FATIHA, start=1):
        gid += 1
        ayahs.append({"id": gid, "number": n, "surah": "1", "page_number": 1, "text": "﻿" + text})
    surahs.append({"id": 1, "name": "سورة الفاتحة", "coded_name": "x", "ayahs": ayahs})
    ayahs = []
    for n in range(1, 256):
        gid += 1
        ayahs.append(
            {
                "id": gid,
                "number": n,
                "surah": "2",
                "page_number": 2,
                "text": BAQARAH.get(n, _filler(2, n)),
            }
        )
    surahs.append({"id": 2, "name": "سورة البقرة", "coded_name": "x", "ayahs": ayahs})
    ayahs = []
    for n in range(1, 6 + extra_surah_ayahs):
        gid += 1
        ayahs.append(
            {"id": gid, "number": n, "surah": "3", "page_number": 50, "text": _filler(3, n)}
        )
    surahs.append({"id": 3, "name": "سورة آل عمران", "coded_name": "x", "ayahs": ayahs})
    return {"license": {"version": "2026-10-02"}, "id": 1, "name": "مصحف حفص", "surahs": surahs}


def make_index() -> QuranIndex:
    return QuranIndex.from_payload(mushaf_payload(), version="2026-10-02", expected_total=None)


#: Quranpedia (mushaf-wide) ids in this fixture: Fatiha 1..7, al-Baqarah n -> 7 + n.
def gid(surah: int, ayah: int) -> int:
    return ayah if surah == 1 else 7 + ayah if surah == 2 else 262 + ayah
