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
    fullContentDescription: "نص ديني، ثم مراجعة الادعاءات قبل التحقق", // spec (text-only MVP)
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
    subtitle: "أدخل النص الديني، ثم راجع الادعاءات المستخرجة قبل التحقق.",
    textLabel: "النص",
    textPlaceholder: "الصق النص الديني أو اكتبه هنا…",
    textHint: "سيستخرج ميزان الادعاءات القابلة للتحقق من النص، ثم تراجعها وتؤكدها قبل التحقق.",
    textSubmit: "استخراج الادعاءات", // spec
    textErrorEmpty: "يرجى إدخال النص الذي تريد فحصه.",
    textErrorTooLong: (max: string) => `النص أطول من الحد المسموح (${max} حرف). يرجى تقصيره.`,
    charCountOf: (n: string, max: string) => `عدد الأحرف: ${n} من ${max}`,
    extracting: "جارٍ استخراج الادعاءات من النص…",
    extractFailedTitle: "تعذّر استخراج الادعاءات",
    extractFailedTechnical:
      "حدثت مشكلة تقنية أثناء استخراج الادعاءات، ولم يُستخرج أي ادعاء. هذه ليست نتيجة عن محتوى النص.",
    extractRateLimited: "خدمة استخراج الادعاءات مشغولة حاليًا. حاول مرة أخرى بعد قليل.",
    extractNotConfigured: "خدمة استخراج الادعاءات غير مهيأة حاليًا. يمكنك إضافة الادعاءات يدويًا.",
    extractBlocked:
      "تعذّرت معالجة هذا النص لاستخراج الادعاءات. يمكنك تعديله، أو إضافة الادعاءات يدويًا.",
    extractNetwork: "تعذّر الاتصال بالخادم. تحقّق من الاتصال ثم حاول مرة أخرى.",
    retry: "إعادة المحاولة",
    addManually: "إضافة الادعاءات يدويًا",
    continueReview: "متابعة مراجعة الادعاءات المستخرجة",
  },
  claimReview: {
    title: "مراجعة الادعاءات",
    subtitle:
      "راجع الادعاءات التي استخرجها ميزان من النص: عدّلها أو احذفها أو أضف ادعاءً، ثم حدّد ما تريد التحقق منه.",
    gateNote: "لن يبدأ أي تحقق قبل تأكيدك. يُعتمد نص الادعاء كما يظهر بعد تعديلك.",
    listLabel: "الادعاءات المستخرجة",
    counts: (n: string, m: string) => `عدد الادعاءات: ${n} — المحدد للتحقق: ${m}`,
    selectAll: "تحديد الكل",
    selectNone: "إلغاء تحديد الكل",
    selectClaim: (i: string) => `تحديد الادعاء ${i} للتحقق`,
    claimNumber: (i: string) => `الادعاء ${i}`,
    badgeEdited: "معدَّل",
    badgeManual: "مضاف يدويًا",
    badgeAmbiguous: "صياغة غير واضحة",
    badgeIncomplete: "ادعاء غير مكتمل",
    originalExcerpt: "من النص الأصلي:",
    providedEvidence: "دليل مذكور في النص:",
    providedReference: "مرجع مذكور في النص:",
    edit: "تعديل",
    delete: "حذف",
    save: "حفظ",
    cancel: "إلغاء",
    editLabel: (i: string) => `تعديل نص الادعاء ${i}`,
    errorEmptyClaim: "لا يمكن حفظ ادعاء فارغ.",
    errorClaimTooLong: (max: string) => `الادعاء أطول من الحد المسموح (${max} حرف).`,
    errorTooMany: (max: string) => `لا يمكن إضافة أكثر من ${max} ادعاءً.`,
    addTitle: "إضافة ادعاء",
    addLabel: "نص الادعاء الجديد",
    addPlaceholder: "اكتب ادعاءً دينيًا واحدًا…",
    addSubmit: "إضافة الادعاء",
    confirm: "تحقّق من الادعاءات المحددة", // spec
    errorNoneSelected: "اختر ادعاءً واحدًا على الأقل للمتابعة.",
    backToText: "العودة لتعديل النص",
    emptyTitle: "لم نجد ادعاءات دينية قابلة للتحقق في هذا المحتوى.",
    emptyBody: "يمكنك تعديل النص ثم إعادة الاستخراج، أو إضافة ادعاء يدويًا.",
    missingTitle: "لا توجد ادعاءات لمراجعتها",
    missingBody: "أدخل نصًا في «فحص محتوى كامل» ثم استخرج الادعاءات.",
    goToFullContent: "الذهاب إلى فحص محتوى كامل",
    confirming: "جارٍ تأكيد الادعاءات…",
    confirmedTitle: (n: string) => `تم تأكيد ${n} من الادعاءات وتجهيزها للتحقق`,
    confirmedBody: "سيُتحقَّق من الادعاءات كما أكّدتها أنت، دون أي تعديل.",
    backToReview: "العودة إلى المراجعة",
    confirmFailed: "تعذّر تأكيد الادعاءات بسبب مشكلة تقنية. حاول مرة أخرى.",
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
    trustedSources: "المصادر المعتمدة",
    retry: "إعادة الفحص",
    note: "هذه حالة تقنية للنظام فقط، وليست نتيجة تحقق من أي ادعاء.",
  },
  notFound: {
    title: "الصفحة غير موجودة",
  },
} as const;

export type Dictionary = typeof ar;
