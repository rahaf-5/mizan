import { ar, type Dictionary } from "./ar";

export type Locale = "ar";

export const defaultLocale: Locale = "ar";

export const localeConfig: Record<Locale, { dir: "rtl" | "ltr"; lang: string }> = {
  ar: { dir: "rtl", lang: "ar" },
};

const dictionaries: Record<Locale, Dictionary> = { ar };

export function getDictionary(locale: Locale = defaultLocale): Dictionary {
  return dictionaries[locale];
}
