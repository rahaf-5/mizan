# Mizan — User Flows, Screens & UX States (MVP)

Arabic-first RTL UI. All copy lives in `frontend/src/i18n/ar.ts` (strings marked `// spec` are
taken verbatim from the product spec). Disclaimer on every page: «ميزان أداة مساعدة للتحقق من
المحتوى، ولا يُعد بديلًا عن الرجوع لأهل العلم عند الحاجة.»

## Routes

| Route | Screen |
|---|---|
| `/` | Home: two entry points (فحص سريع / فحص محتوى كامل) |
| `/quick-check` | Quick Check input → inline verification report |
| `/full-content` | Full Content text input (text only) → «استخراج الادعاءات» |
| `/full-content/claims` | Claim Review (edit / delete / select / add) → «تحقّق من الادعاءات المحددة» |
| `/full-content/results` | Verification report for the confirmed claims |
| `/status` | Technical system status (not a verification result) |
| any other | «الصفحة غير موجودة» + link home |

## Flow A — Quick Check

```
Input (one claim, editable)
  └─ «تحقق من الادعاء»  (= explicit confirmation)
       ├─ empty → inline error «يرجى كتابة الادعاء الذي تريد التحقق منه.», focus returns to the field
       ├─ looks like several claims → non-blocking guidance: «الانتقال إلى فحص محتوى كامل» or «المتابعة كادعاء واحد»
       └─ POST /claims/confirm (exact text, origin=manual)   status: «جارٍ تأكيد الادعاء…»
            ├─ failure → «تعذّر تأكيد الادعاء بسبب مشكلة تقنية…» (nothing verified)
            └─ POST /verify (the confirmed claim only) → progress → result card
                 └─ «تعديل الادعاء» → back to the input with the text kept; old result discarded
```

## Flow B — Full Content Check (text)

```
Text input → «استخراج الادعاءات» → POST /claims/extract (extraction only, no verification)
  → Claim Review: claim count, selection, edit, delete, add manual claim, selected count
  → «تحقّق من الادعاءات المحددة» → POST /claims/confirm (edited text is what is confirmed;
     deleted/deselected claims are not sent; manual claims included)
  → /full-content/results: verifies ONLY the confirmed claims, one request per claim, in order
  → Report Summary → result groups → claim cards → Evidence & Sources / Alternative wording
```

Changing the review after confirmation clears the confirmation and any results, so a stale
report can never be shown for edited claims.

## Report structure (spec §12)

1. **Progress** (while running): «جارٍ التحقق من الادعاء i من n» with each claim's state
   (في الانتظار / جارٍ التحقق / اكتمل / تعذّر).
2. **ملخص التقرير**: total and per-section counts.
3. **Sections** (only non-empty ones, in this order): محتوى تم التحقق منه · لا تستخدم هذه
   الادعاءات بصيغتها الحالية · تحتاج مراجعة قبل النشر · تحتاج مراجعة الأدلة · لا يمكن التحقق منها
   حاليًا · تعذّر التحقق بسبب مشكلة تقنية.
4. **Claim card**: claim text → status badge (icon + text, never colour only) → «لماذا وضعه
   ميزان هنا؟» → «ماذا تفعل؟» → what Mizan checked in the claim (per component) → conflict note →
   «عرض الأدلة والمصادر (n)» → «اقترح صياغة بديلة» (only for partially supported / contradicted).
5. **Evidence card**: «النص من المصدر» (verbatim provider text, its own region) → «المقطع الذي
   استند إليه ميزان» → relation to the claim → «شرح ميزان» (labelled as automated analysis or
   literal matching, not part of the source) → strength signals (no score) → reference,
   provider, author (as given by the provider, or «غير مذكور لدى المزوّد»), asbab relation type
   («غير محدد لدى المزوّد»), link to the original provider record.

## UX states

| State | What the user sees |
|---|---|
| Loading | Progress card (real per-claim progress); buttons disabled while confirming |
| Empty input | Inline field error + focus |
| Empty report | «لا توجد ادعاءات مؤكدة للتحقق منها.» + link to Full Content |
| Supported | «مدعوم بالأدلة» + evidence |
| Partially supported | «مدعوم جزئيًا»: supported vs unsupported parts + alternative wording |
| Contradicted | «يخالف الدليل»: what contradicts, the real location/text + alternative wording |
| Conflicting evidence | «أدلة متعارضة» + «لماذا لم يُصدر ميزان حكمًا قاطعًا؟» (both sides shown, no ranking) |
| Insufficient evidence | «أدلة غير كافية»: related evidence shown, why it does not suffice |
| No evidence | «لم يُعثر على دليل» + «عدم العثور على دليل لا يعني أن الادعاء خاطئ.» |
| Required source unavailable (hadith) | «المصدر المطلوب غير متاح حاليًا» naming الدرر السنية; no verdict, no grading |
| Out of scope | «خارج نطاق ميزان حاليًا» — explicitly not "false" |
| System error / network / malformed response | «تعذّر إكمال التحقق» + reason (service busy / source temporarily unavailable / server unreachable / not configured) + «إعادة التحقق»; explicitly "not a result about the claim" |
| Alternative — working | «جارٍ اقتراح صياغة بديلة وإعادة التحقق منها…» |
| Alternative — verified | «✓ تم التحقق من الصياغة المقترحة» + text + «اعتماد الصياغة المقترحة» |
| Alternative — not verified | «لم يتمكن ميزان من التحقق من صياغة بديلة موثوقة. راجع الادعاء والمصادر قبل النشر.» (the unverified text is never shown) |
| Alternative — expired / error | server result expired → re-verify first; technical error message |

## Accessibility & layout

RTL document (`dir="rtl"`, `lang="ar"`), `dir="auto"` for user text, labelled fields,
`aria-invalid`/`aria-describedby` on errors, `role="status"`/`aria-live` for progress,
`aria-expanded` on toggles, status conveyed by icon + text, mobile-first single column.
