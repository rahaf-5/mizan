/**
 * Arabic UI strings (default locale). All user-facing copy lives in locale
 * dictionaries so English/localization can be added later (spec §19.16).
 * Copy below is taken from MIZAN_PRODUCT_SPEC.md where the spec defines it.
 */
export const ar = {
  meta: {
    title: "ميزان — تحقّق قبل أن تنشر",
    description: "أداة مساعدة للتحقق من الادعاءات الدينية من مصادر معتمدة قابلة للتتبع.",
  },
  brand: {
    name: "ميزان",
    tagline: "تحقّق قبل أن تنشر",
  },
  a11y: {
    skipToContent: "تخطَّ إلى المحتوى الرئيسي",
    mainNav: "التنقل الرئيسي",
  },
  nav: {
    home: "الرئيسية",
    quickCheck: "فحص سريع",
    fullContent: "فحص محتوى كامل",
    status: "حالة النظام",
  },
  home: {
    quickCheckTitle: "فحص سريع",
    quickCheckDescription: "ادعاء ديني واحد",
    fullContentTitle: "فحص محتوى كامل",
    fullContentDescription: "نص أو صورة، ثم مراجعة الادعاءات قبل التحقق",
    principle: "الادعاء أولًا، الدليل ثانيًا، والنتيجة أخيرًا.",
  },
  placeholder: {
    comingSoon: "هذه الصفحة قيد الإنشاء وستتوفر في مرحلة لاحقة من التطوير.",
    backHome: "العودة إلى الرئيسية",
  },
  disclaimer:
    "ميزان أداة مساعدة للتحقق من المحتوى، ولا يُعد بديلًا عن الرجوع لأهل العلم عند الحاجة.",
  status: {
    title: "حالة النظام",
    description: "فحص تقني لاتصال الواجهة بالخادم وتحميل الإعدادات.",
    checking: "جارٍ الفحص…",
    backendReachable: "الخادم متصل",
    backendUnreachable: "تعذّر الاتصال بالخادم",
    configLoaded: "تم تحميل الإعدادات",
    overallOk: "سليم",
    overallDegraded: "يعمل جزئيًا",
    database: "قاعدة البيانات",
    llmProvider: "مزوّد النموذج اللغوي",
    ocr: "خدمة التعرّف على النص (OCR)",
    trustedSources: "المصادر المعتمدة",
    retry: "إعادة الفحص",
    note: "هذه حالة تقنية للنظام فقط، وليست نتيجة تحقق من أي ادعاء.",
  },
  notFound: {
    title: "الصفحة غير موجودة",
  },
} as const;

export type Dictionary = typeof ar;
