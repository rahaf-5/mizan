import { describe, expect, it } from "vitest";
import { readableRecordUrl } from "@/lib/verify/presentation";
import type { Evidence } from "@/lib/verify/types";
import { QURAN_EVIDENCE, TAFSIR_EVIDENCE, IBN_KATHIR_EVIDENCE } from "../fixtures/outcomes";

describe("«فتح السجل الأصلي» opens a human-readable page, never the JSON API", () => {
  it("Quran record → official Quranpedia ayah page for the same surah/ayah", () => {
    expect(readableRecordUrl(QURAN_EVIDENCE)).toBe("https://quranpedia.net/embed?surah=2&ayah=158");
  });

  it("tafsir records → same ayah, tafsir section, same book", () => {
    expect(readableRecordUrl(TAFSIR_EVIDENCE)).toBe("https://quranpedia.net/embed?surah=2&ayah=255&type=tafsir&book=2012");
    expect(readableRecordUrl(IBN_KATHIR_EVIDENCE)).toBe("https://quranpedia.net/embed?surah=2&ayah=255&type=tafsir&book=136");
  });

  it("asbab records → same ayah, asbab section, same book", () => {
    const asbab: Evidence = { ...TAFSIR_EVIDENCE, source_type: "asbab_nuzul", trusted_source_id: "asbab_al_nuzul_al_wahidi", source_address: "/v1/ayah/2/158/book/2919", source_url: "https://api.quranpedia.net/v1/ayah/2/158/book/2919" };
    expect(readableRecordUrl(asbab)).toBe("https://quranpedia.net/embed?surah=2&ayah=158&type=asbab&book=2919");
  });

  it("no guessed link for anything it cannot map safely", () => {
    expect(readableRecordUrl({ ...QURAN_EVIDENCE, source_address: "/v1/something/else" })).toBeNull();
    expect(readableRecordUrl({ ...QURAN_EVIDENCE, provider: "other" })).toBeNull();
    expect(readableRecordUrl({ ...QURAN_EVIDENCE, source_address: "/v1/mushafs/1/115/1" })).toBeNull();
    expect(readableRecordUrl({ ...TAFSIR_EVIDENCE, source_type: "hadith" })).toBeNull();
  });
});
