/**
 * Arabic UI strings (default locale). All user-facing copy lives in locale
 * dictionaries so English/localization can be added later (spec §19.16).
 * Copy marked "spec" is taken verbatim from MIZAN_PRODUCT_SPEC.md.
 */
export const ar = {
  meta: {
    title: "ميزان — تحقّق قبل أن تنشر",
    description: "أداة مساعدة للتحقق من الادعاءات الدينية من مصادر معتمدة قابلة للتتبع.",
  },
  brand: {
    name: "ميزان", // spec
    tagline: "تحقّق قبل أن تنشر", // spec
    logoLabel: "ميزان — الصفحة الرئيسية",
  },
  a11y: {
    skipToContent: "تخطَّ إلى المحتوى الرئيسي",
    mainNav: "التنقل الرئيسي",
    breadcrumb: "مسار التنقل",
  },
  nav: {
    home: "الرئيسية",
    quickCheck: "فحص سريع",
    fullContent: "فحص محتوى كامل",
    status: "حالة النظام",
  },
  home: {
    description:
      "يساعدك ميزان على التحقق من الادعاءات الدينية، ومراجعة أدلتها ومصادرها المعتمدة، قبل أن تنشرها.",
    pathsLabel: "اختر طريقة الفحص",
    quickCheckTitle: "فحص سريع", // spec
    quickCheckDescription: "ادعاء ديني واحد", // spec
    fullContentTitle: "فحص محتوى كامل", // spec
    fullContentDescription: "نص أو صورة، ثم مراجعة الادعاءات قبل التحقق", // spec
    start: "ابدأ",
  },
  common: {
    edit: "تعديل",
    charCount: (n: string) => `عدد الأحرف: ${n}`,
    nextStepPending:
      "لم يبدأ أي تحقق بعد. ستتوفر الخطوة التالية في مرحلة قادمة من تطوير ميزان.",
  },
  quickCheck: {
    title: "فحص سريع", // spec
    subtitle: "تحقّق من ادعاء ديني واحد", // spec
    fieldLabel: "الادعاء", // spec
    placeholder: "قراءة سورة الكهف يوم الجمعة سبب في حصول نور بين الجمعتين.",
    hint: "اكتب ادعاءً دينيًا واحدًا كما تنوي نشره. يمكنك تعديله قبل التحقق.",
    submit: "تحقق من الادعاء", // spec
    errorEmpty: "يرجى كتابة الادعاء الذي تريد التحقق منه.",
    multiTitle: "يبدو أن النص يحتوي على أكثر من ادعاء",
    multiBody:
      "الفحص السريع مخصص لادعاء ديني واحد. لفحص فقرة أو عدة ادعاءات، استخدم «فحص محتوى كامل» ليستخرج ميزان الادعاءات وتراجعها قبل التحقق.",
    multiGoFull: "الانتقال إلى فحص محتوى كامل",
    multiContinue: "المتابعة كادعاء واحد",
    preparedTitle: "تم تجهيز الادعاء للمراجعة والتأكيد",
    preparedClaimLabel: "الادعاء كما أدخلته",
  },
  fullContent: {
    title: "فحص محتوى كامل", // spec
    subtitle: "أدخل نصًا أو صورة، ثم راجع الادعاءات المستخرجة قبل التحقق.",
    modeLabel: "نوع المحتوى",
    modeText: "نص", // spec
    modeImage: "صورة", // spec
    textLabel: "النص",
    textPlaceholder: "الصق النص الديني أو اكتبه هنا…",
    textHint: "سيستخرج ميزان الادعاءات القابلة للتحقق من النص، ثم تراجعها وتؤكدها قبل التحقق.",
    textSubmit: "استخراج الادعاءات", // spec
    textErrorEmpty: "يرجى إدخال النص الذي تريد فحصه.",
    textPreparedTitle: "تم تجهيز النص لاستخراج الادعاءات",
    imageLabel: "الصورة",
    imageDropTitle: "اختر صورة أو اسحبها إلى هنا",
    imageChoose: "اختيار صورة",
    imageFormats: "الصيغ المقبولة: JPG أو PNG",
    imageHint:
      "بعد رفع الصورة يُستخرج النص منها، ثم تراجعه وتصحّحه قبل استخراج الادعاءات.",
    imageSubmit: "رفع واستخراج النص", // spec
    imageErrorMissing: "يرجى اختيار صورة أولًا.",
    imageErrorType: "يُقبل فقط ملفات الصور بصيغة JPG أو PNG.",
    imageErrorEmpty: "الملف المختار فارغ. يرجى اختيار صورة أخرى.",
    imageErrorCorrupt: "تعذّرت قراءة الملف كصورة JPG أو PNG. يرجى اختيار صورة أخرى.",
    imageSelected: "الصورة المختارة",
    imagePreviewAlt: "معاينة الصورة المختارة",
    imageRemove: "إزالة الصورة",
    imageReplace: "تغيير الصورة",
    imagePreparedTitle: "تم تجهيز الصورة لاستخراج النص",
    imagePreparedNext:
      "الخطوة التالية: استخراج النص من الصورة، ثم مراجعته وتصحيحه قبل استخراج الادعاءات.",
    sizeKB: (n: string) => `${n} كيلوبايت`,
    sizeMB: (n: string) => `${n} ميغابايت`,
  },
  placeholder: {
    comingSoon: "هذه الصفحة قيد الإنشاء وستتوفر في مرحلة لاحقة من التطوير.",
    backHome: "العودة إلى الرئيسية",
  },
  disclaimer:
    "ميزان أداة مساعدة للتحقق من المحتوى، ولا يُعد بديلًا عن الرجوع لأهل العلم عند الحاجة.", // spec
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
