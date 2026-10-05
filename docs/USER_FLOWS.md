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
       ├─ longer than 1000 characters → inline input error with the limit (never "technical"), nothing sent
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

## Result experience (progressive disclosure, 2026-10-05)

One result card is used by Quick Check and by every claim in Full Content. Each piece of
information appears once:

1. **Decision** — status badge (icon + text, never colour only), the exact status.
2. **Claim** — shown once.
3. **«لماذا هذه النتيجة؟»** — plain explanation built only from the result (`explainResult`).
4. **«ماذا تفعل؟»** — one short action for the status; «اقترح صياغة بديلة» appears here only
   for partially supported / contradicted results, and a proposal is shown as trusted only after
   full re-verification. Technical failures show «إعادة التحقق» here.
5. **«الأدلة التي اعتمد عليها ميزان»** — preview «المصدر — الموضع» only, then one button
   «عرض الأدلة والتفاصيل». No section and no button when no evidence was used.
6. **Details (on request)** — per evidence: المصدر, the verbatim passage Mizan relied on (or the
   record's own text), المرجع, المصدر الأصلي (link to the original record). Conflicting evidence is
   grouped «أدلة تؤيد / أدلة تخالف / أدلة أخرى». «حدود هذا التحقق» appears here only when a
   limitation exists. Technical fields (fingerprints, internal ids) stay in the data, not the UI.

**Quick Check:** progress, then the single card, then «فحص جديد» / «تعديل الادعاء». No dashboard.

**Full Content:** progress, then «ملخص التقرير» (number of claims + tiles: يمكن استخدامها ·
تحتاج تعديلًا أو مراجعة · لا تُستخدم بصيغتها الحالية · تعذّر التحقق منها حاليًا [only if any]), then
the cards grouped under the same four headings. Mapping (presentation only): supported → usable;
partially supported / insufficient / no evidence / conflicting → needs review; contradicted → do
not use; source unavailable / out of scope / technical failure → could not verify now.

## UX states

| State | What the user sees |
|---|---|
| Loading | Progress card (real per-claim progress); buttons disabled while confirming |
| Empty input | Inline field error + focus |
| Empty report | «لا توجد ادعاءات مؤكدة للتحقق منها.» + link to Full Content |
| Supported | «مدعوم بالأدلة» + evidence |
| Partially supported | «مدعوم جزئيًا»: supported vs unsupported parts + alternative wording |
| Contradicted | «يخالف الدليل»: what contradicts, the real location/text + alternative wording |
| Conflicting evidence | «أدلة متعارضة» + «لماذا لم يُصدر ميزان حكمًا قاطعًا؟»; evidence grouped «أدلة تؤيد / أدلة تخالف / أدلة أخرى» (no ranking) |
| Insufficient evidence | «أدلة غير كافية»: related evidence shown, why it does not suffice |
| No evidence | «لم يُعثر على دليل» + «عدم العثور على دليل لا يعني أن الادعاء خاطئ.» |
| Required source unavailable (hadith) | «المصدر المطلوب غير متاح حاليًا» naming الدرر السنية; no verdict, no grading |
| Out of scope | «خارج نطاق ميزان حاليًا» — explicitly not "false" |
| System error / network / malformed response | «تعذّر إكمال التحقق» + reason (service busy / source temporarily unavailable / server unreachable / not configured) + «إعادة التحقق»; explicitly "not a result about the claim" |
| Alternative — working | «جارٍ اقتراح صياغة بديلة وإعادة التحقق منها…» |
| Alternative — verified | «✓ تم التحقق من الصياغة المقترحة» + text + its verification explanation + «اعتماد الصياغة المقترحة»; after adoption the card shows «اعتمدت الصياغة المقترحة بعد التحقق منها.» and the summary counters update |
| Alternative — not verified | «لم يتمكن ميزان من التحقق من صياغة بديلة موثوقة. راجع الادعاء والمصادر قبل النشر.» (the unverified text is never shown) |
| Alternative — expired / error | server result expired → re-verify first; technical error message |

## Accessibility & layout

RTL document (`dir="rtl"`, `lang="ar"`), `dir="auto"` for user text, labelled fields,
`aria-invalid`/`aria-describedby` on errors, `role="status"`/`aria-live` for progress,
`aria-expanded` on toggles, status conveyed by icon + text, mobile-first single column.

## «لماذا هذه النتيجة؟» wording (2026-10-05)

Built in `frontend/src/lib/verify/presentation.ts` (`explainResult`) only from the validated
result: claim components (verbatim spans of the user's claim), relationships, evidence records
and verbatim cited spans. A component that is the whole claim is referred to as «ما ورد في
ادعائك» instead of being quoted back. Rules per status:

- supported → what the source has that supports the claim (with the verbatim passage).
- contradicted → what the claim says vs. what the source says («يذكر … خلاف ما ورد في ادعائك: «…»»);
  for a wrong ayah location: the stated location vs. the documented one.
- partially supported → the supported part and the part not established.
- insufficient → which source/ayah was checked, and that it neither proves nor disproves the claim.
- conflicting → which sources support and which oppose; no verdict forced.
- no evidence → the spec sentence (absence of evidence is not falsehood).
- required source unavailable → Mizan needs the hadith source, which is unavailable; no verdict.

The raw analysis rationale is never shown. The heading changed from «لماذا وضعه ميزان هنا؟» to
«لماذا هذه النتيجة؟» (product decision).
