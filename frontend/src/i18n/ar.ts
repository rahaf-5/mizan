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
    preparedClaimLabel: "الادعاء كما أدخلته",
    confirming: "جارٍ تأكيد الادعاء…",
    confirmFailed: "تعذّر تأكيد الادعاء بسبب مشكلة تقنية. حاول مرة أخرى.",
    errorTooLong: (max: string) =>
      `الادعاء أطول من الحد المسموح (${max} حرف). اختصره إلى ادعاء واحد، أو استخدم «فحص محتوى كامل» للنصوص الطويلة.`,
    errorInvalid: "تعذّر قبول نص الادعاء. راجع النص ثم حاول مرة أخرى.",
    editClaim: "تعديل الادعاء",
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
    confirmedTitle: (n: string) => `تم تأكيد ${n} من الادعاءات`,
    confirmedBody: "سيُتحقَّق من الادعاءات كما أكّدتها أنت، دون أي تعديل.",
    backToReview: "العودة إلى المراجعة",
    viewResults: "عرض نتائج التحقق",
    confirmFailed: "تعذّر تأكيد الادعاءات بسبب مشكلة تقنية. حاول مرة أخرى.",
  },
  results: {
    title: "نتيجة التحقق",
    fullTitle: "تقرير التحقق",
    fullSubtitle: "نتائج الادعاءات التي أكّدتها، مع الأدلة ومصادرها المعتمدة.",
    progressTitle: "جارٍ التحقق",
    progress: (i: string, n: string) => `جارٍ التحقق من الادعاء ${i} من ${n}`,
    progressNote: "يبحث ميزان في المصادر المعتمدة ويقارن الادعاء بالأدلة. قد يستغرق ذلك بعض الوقت.",
    runState: { waiting: "في الانتظار", running: "جارٍ التحقق", done: "اكتمل", failed: "تعذّر" },
    summaryTitle: "ملخص التقرير",
    summaryTotal: (n: string) => `عدد الادعاءات: ${n}`,
    sections: {
      verified: "محتوى تم التحقق منه", // spec
      do_not_use_as_written: "لا تستخدم هذه الادعاءات بصيغتها الحالية", // spec
      needs_revision: "تحتاج مراجعة قبل النشر", // spec
      needs_evidence_review: "تحتاج مراجعة الأدلة", // spec
      not_verifiable_now: "لا يمكن التحقق منها حاليًا",
      technical: "تعذّر التحقق بسبب مشكلة تقنية",
    },
    status: {
      supported: "مدعوم بالأدلة",
      partially_supported: "مدعوم جزئيًا",
      contradicted: "يخالف الدليل",
      conflicting_evidence: "أدلة متعارضة",
      insufficient_evidence: "أدلة غير كافية",
      no_evidence_found: "لم يُعثر على دليل",
      required_source_unavailable: "المصدر المطلوب غير متاح حاليًا",
      out_of_scope: "خارج نطاق ميزان حاليًا",
      system_error: "تعذّر إكمال التحقق",
    },
    claimLabel: "الادعاء",
    whyTitle: "لماذا وضعه ميزان هنا؟", // spec
    whatTitle: "ماذا تفعل؟", // spec
    componentsTitle: "ما الذي تحقّق منه ميزان في الادعاء",
    componentOutcome: {
      supported: "مثبت",
      partially_supported: "مثبت جزئيًا",
      contradicted: "مخالف للدليل",
      conflicting: "الأدلة فيه متعارضة",
      insufficient: "الأدلة غير كافية",
      not_established: "لم يُثبت",
    },
    anchorNote: "سياق: الآية المشار إليها في الادعاء",
    verifiedLocation: "الموضع الموثّق:",
    verifiedReferenceTitle: "الموضع الموثّق في المصحف",
    evidenceSummaryTitle: "الأدلة التي اعتمد عليها ميزان",
    indicatorsTitle: "مؤشرات التحقق",
    verifiedReferenceNote: "من سجل المصدر المعتمد؛ لم يُغيَّر نص ادعائك.",
    limitationsTitle: "حدود هذه النتيجة",
    conflictGroups: {
      supports: "أدلة تؤيد",
      contradicts: "أدلة تخالف",
      other: "أدلة أخرى ذات صلة",
    },
    showEvidence: (n: string) => `عرض الأدلة والمصادر (${n})`,
    hideEvidence: "إخفاء الأدلة والمصادر",
    noEvidenceShown: "لا توجد أدلة مستخدمة في هذه النتيجة.",
    relatedUnverified: (n: string) =>
      `وجد البحث ${n} نتيجة مرتبطة بالكلمات فقط؛ لم تُستخدم في الحكم لأنها لا تكفي للتحقق.`,
    conflictTitle: "لماذا لم يُصدر ميزان حكمًا قاطعًا؟",
    conflictBody:
      "المصادر المعتمدة نفسها مختلفة بشأن هذا الجزء، فعُرضت الأدلة المؤيدة والمخالفة كما هي دون ترجيح.",
    evidence: {
      sourceText: "النص من المصدر", // spec
      citedSpan: "المقطع الذي استند إليه ميزان",
      indicatorsTitle: "مؤشرات التحقق لهذا الدليل",
      mizanExplanation: "شرح ميزان", // spec
      supportedPart: "الجزء المثبت:",
      unsupportedPart: "الجزء غير المثبت:",
      source: "المصدر",
      provider: "المزوّد",
      reference: "المرجع",
      author: "المؤلف (كما ورد من المزوّد)",
      authorMissing: "غير مذكور لدى المزوّد",
      relationType: "نوع الصلة بسبب النزول",
      relationUnspecified: "غير محدد لدى المزوّد",
      record: "السجل الأصلي لدى المزوّد",
      openRecord: "فتح السجل الأصلي",
      sourceType: { quran: "قرآن", tafsir: "تفسير", asbab_nuzul: "أسباب النزول", hadith: "حديث" },
    },
    unavailable: {
      why: (sources: string) =>
        `يتطلب هذا الادعاء التحقق من حديث نبوي، والمصدر المعتمد لذلك في ميزان (${sources}) غير متاح حاليًا. لذلك لم يُصدر ميزان أي حكم على هذا الادعاء، وهذا لا يعني أنه صحيح أو خاطئ.`,
      what: "راجع الحديث في مصدر حديثي موثوق أو اسأل أهل العلم قبل النشر.",
    },
    outOfScope: {
      why: "هذا الادعاء ليس من الأنواع التي يتحقق منها ميزان حاليًا (نص القرآن وموضعه، التفسير، أسباب النزول، الحديث). هذا لا يعني أنه خاطئ.",
      what: "ارجع إلى أهل العلم أو إلى مصدر علمي موثوق للتحقق منه قبل النشر.",
    },
    technical: {
      why: "حدثت مشكلة تقنية منعت ميزان من إكمال التحقق بصورة موثوقة، لذلك لا تُعرض أي نتيجة عن صحة الادعاء.",
      busy: "خدمة التحليل مشغولة حاليًا.",
      source: "أحد المصادر المعتمدة غير متاح مؤقتًا.",
      network: "تعذّر الاتصال بالخادم.",
      notConfigured: "خدمة التحقق غير مهيأة على الخادم.",
      invalidInput: "تعذّر قبول نص الادعاء (قد يكون أطول من الحد المسموح).",
      what: "أعد المحاولة بعد قليل. هذه ليست نتيجة عن محتوى الادعاء.",
      retry: "إعادة التحقق",
    },
    alternative: {
      action: "اقترح صياغة بديلة",
      working: "جارٍ اقتراح صياغة بديلة وإعادة التحقق منها في المصادر المعتمدة…",
      proposedLabel: "الصياغة المقترحة",
      whyLabel: "نتيجة التحقق من الصياغة المقترحة",
      verified: "✓ تم التحقق من الصياغة المقترحة", // spec
      failed:
        "لم يتمكن ميزان من التحقق من صياغة بديلة موثوقة. راجع الادعاء والمصادر قبل النشر.", // spec
      unverifiedNote: "لم تُعتمد هذه الصياغة لأن التحقق منها لم ينجح.",
      adopt: "اعتماد الصياغة المقترحة",
      adopted: "اعتمدت الصياغة المقترحة بعد التحقق منها.",
      error: "تعذّر اقتراح صياغة بديلة بسبب مشكلة تقنية. حاول مرة أخرى لاحقًا.",
      expired: "انتهت صلاحية نتيجة التحقق في الخادم. أعد التحقق من الادعاء ثم حاول مرة أخرى.",
    },
    restart: "فحص جديد",
    backToReview: "العودة إلى مراجعة الادعاءات",
    noClaims: "لا توجد ادعاءات مؤكدة للتحقق منها.",
    goToFullContent: "الذهاب إلى فحص محتوى كامل",
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
    body: "لم نعثر على الصفحة المطلوبة.",
    backHome: "العودة إلى الرئيسية",
  },
} as const;

export type Dictionary = typeof ar;
