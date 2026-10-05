// @vitest-environment jsdom
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FullContentResults } from "@/features/results/FullContentResults";
import type { ConfirmedClaim } from "@/lib/claims/types";
import type { ClaimOutcome } from "@/lib/verify/types";
import {
  conflicting,
  contradicted,
  finalResult,
  hadithUnavailable,
  noEvidence,
  outOfScope,
  QURAN_EVIDENCE,
  supported,
  systemError,
  TAFSIR_EVIDENCE,
} from "../fixtures/outcomes";
import { jsonResponse, renderWithSession } from "../helpers";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const claim = (id: string, text: string): ConfirmedClaim => ({
  claim_id: id,
  confirmed_claim_text: text,
  user_confirmation_status: "confirmed",
  claim_type: null,
  provided_evidence: null,
  provided_reference: null,
});

let fetchSpy: ReturnType<typeof vi.fn>;
const verifyBodies = () =>
  fetchSpy.mock.calls.filter(([u]) => String(u).endsWith("/api/v1/verify")).map(([, init]) => JSON.parse(String(init.body)));

/** Each /verify call answers with the outcome registered for the claim it carries. */
function serve(byId: Record<string, ClaimOutcome | (() => ClaimOutcome)>, alt?: (body: { run_id: string; claim_id: string }) => Response) {
  fetchSpy.mockImplementation((url: string, init: RequestInit) => {
    const body = JSON.parse(String(init.body));
    if (url.endsWith("/api/v1/verify")) {
      const id = body.claims[0].claim_id as string;
      const o = byId[id];
      return Promise.resolve(jsonResponse(finalResult(typeof o === "function" ? o() : o, `run-${id}`)));
    }
    if (url.endsWith("/api/v1/alternative-wording") && alt) return Promise.resolve(alt(body));
    return Promise.reject(new Error(`unexpected ${url}`));
  });
}

const setup = (claims: ConfirmedClaim[]) =>
  renderWithSession(<FullContentResults />, {
    confirmation: { confirmedClaims: claims, nextStage: "claim_classification" },
  });

beforeEach(() => {
  fetchSpy = vi.fn();
  vi.stubGlobal("fetch", fetchSpy);
});
afterEach(() => {
  vi.unstubAllGlobals();
  for (const [u] of fetchSpy.mock.calls) expect(String(u)).toMatch(/\/api\/v1\/(verify|alternative-wording)$/);
});

describe("Full Content results", () => {
  it("without confirmed claims nothing is verified and the user is guided back", () => {
    setup([]);
    expect(screen.getByText("لا توجد ادعاءات مؤكدة للتحقق منها.")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("verifies ONLY the confirmed claims, one request per claim, in order, with progress", async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    fetchSpy.mockImplementation(async (url: string, init: RequestInit) => {
      const id = JSON.parse(String(init.body)).claims[0].claim_id;
      if (id === "a") await gate;
      return jsonResponse(finalResult(id === "a" ? supported("a", "أ") : noEvidence, `run-${id}`));
    });
    setup([claim("a", "أ"), claim("c4", "ب")]);
    expect(await screen.findByText("جارٍ التحقق من الادعاء 1 من 2")).toBeInTheDocument();
    expect(verifyBodies()).toHaveLength(1); // sequential: the second waits for the first
    release();
    await waitFor(() => expect(screen.queryByText(/جارٍ التحقق من الادعاء/)).toBeNull());
    const bodies = verifyBodies();
    expect(bodies.map((b) => b.claims.map((c: ConfirmedClaim) => c.claim_id))).toEqual([["a"], ["c4"]]);
    expect(bodies[0].claims[0].confirmed_claim_text).toBe("أ");
    expect(screen.getByText("ملخص التقرير")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /محتوى تم التحقق منه/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /تحتاج مراجعة الأدلة/ })).toBeInTheDocument();
  });

  it("renders every outcome kind with its own status, why and what-to-do — never mixed", async () => {
    serve({ c1: contradicted(), c3: conflicting, c4: noEvidence, c5: hadithUnavailable, c6: outOfScope, c7: systemError });
    setup([
      claim("c1", contradicted().confirmed_claim_text),
      claim("c3", conflicting.confirmed_claim_text),
      claim("c4", noEvidence.confirmed_claim_text),
      claim("c5", "قال رسول الله ﷺ: «إنما الأعمال بالنيات»"),
      claim("c6", "حكم كذا"),
      claim("c7", "ادعاء"),
    ]);
    await waitFor(() => expect(verifyBodies()).toHaveLength(6));
    await waitFor(() => expect(screen.queryByText(/جارٍ التحقق من الادعاء/)).toBeNull());

    expect(screen.getByText("يخالف الدليل")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /لا تستخدم هذه الادعاءات بصيغتها الحالية/ })).toBeInTheDocument();
    expect(screen.getByText("أدلة متعارضة")).toBeInTheDocument();
    expect(screen.getByText("لماذا لم يُصدر ميزان حكمًا قاطعًا؟")).toBeInTheDocument();
    expect(screen.getByText("لم يُعثر على دليل")).toBeInTheDocument();
    expect(screen.getByText(/عدم العثور على دليل لا يعني أن الادعاء خاطئ/)).toBeInTheDocument();
    expect(screen.getByText(/وجد البحث 1 نتيجة مرتبطة بالكلمات فقط/)).toBeInTheDocument();

    // Hadith: unavailable source, explicitly no verdict and no invented grading.
    expect(screen.getByText("المصدر المطلوب غير متاح حاليًا")).toBeInTheDocument();
    expect(screen.getByText(/الدرر السنية — الموسوعة الحديثية/)).toBeInTheDocument();
    expect(screen.queryByText(/صحيح البخاري|حسن|ضعيف/)).toBeNull();

    expect(screen.getByText("خارج نطاق ميزان حاليًا")).toBeInTheDocument();
    // Technical failure shows no verdict about the claim.
    expect(screen.getByText("تعذّر إكمال التحقق")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /تعذّر التحقق بسبب مشكلة تقنية/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "إعادة التحقق" })).toBeInTheDocument();
  });

  it("evidence card separates the verbatim source text from Mizan's explanation and links the original record", async () => {
    const user = userEvent.setup();
    serve({ c1: contradicted() });
    setup([claim("c1", contradicted().confirmed_claim_text)]);
    await user.click(await screen.findByRole("button", { name: /عرض الأدلة والمصادر/ }));
    const card = document.querySelector(`[data-evidence-id="${QURAN_EVIDENCE.evidence_id}"]`) as HTMLElement;
    const sourceRegion = within(card).getByRole("region", { name: "النص من المصدر" });
    expect(within(sourceRegion).getByText(QURAN_EVIDENCE.text)).toBeInTheDocument();
    // The explanation is not inside the source-text region.
    expect(within(sourceRegion).queryByText(/النص موجود في سورة البقرة/)).toBeNull();
    expect(within(card).getByText("شرح ميزان")).toBeInTheDocument();
    expect(within(card).getByText(/النص موجود في سورة البقرة/)).toBeInTheDocument();
    expect(within(card).getByText("مطابقة آلية حرفية مع نص المصدر.")).toBeInTheDocument();
    expect(within(card).getByText(QURAN_EVIDENCE.reference)).toBeInTheDocument();
    expect(within(card).getByText("Quranpedia")).toBeInTheDocument();
    const link = within(card).getByRole("link", { name: QURAN_EVIDENCE.source_address });
    expect(link).toHaveAttribute("href", QURAN_EVIDENCE.source_url);
    // No numeric confidence score anywhere.
    expect(document.body.textContent).not.toMatch(/%|confidence|درجة الثقة/);
  });

  it("tafsir evidence shows provider author and marks LLM analysis as not part of the source", async () => {
    const user = userEvent.setup();
    serve({ c3: conflicting });
    setup([claim("c3", conflicting.confirmed_claim_text)]);
    await user.click(await screen.findByRole("button", { name: /عرض الأدلة والمصادر/ }));
    const card = document.querySelector(`[data-evidence-id="${TAFSIR_EVIDENCE.evidence_id}"]`) as HTMLElement;
    expect(within(card).getByText("تفسير")).toBeInTheDocument();
    expect(within(card).getByText(TAFSIR_EVIDENCE.metadata.provider_author as string)).toBeInTheDocument();
    expect(within(card).getByText("تحليل آلي مقيّد بنص المصدر أعلاه — وليس جزءًا من المصدر.")).toBeInTheDocument();
  });

  it("alternative wording: a VERIFIED proposal can be adopted and replaces the claim and its result", async () => {
    const user = userEvent.setup();
    const original = contradicted();
    const fixed = "قال تعالى في سورة البقرة: «إن الصفا والمروة من شعائر الله»";
    serve({ c1: original }, (body) => {
      expect(body).toEqual({ run_id: "run-c1", claim_id: "c1" });
      return jsonResponse({
        kind: "alternative_wording",
        original_claim_id: "c1",
        run_id: "run-c1:alt",
        proposed_text: fixed,
        verified: true,
        outcome: supported("c1:alt", fixed),
      });
    });
    setup([claim("c1", original.confirmed_claim_text)]);
    await user.click(await screen.findByRole("button", { name: "اقترح صياغة بديلة" }));
    expect(await screen.findByText("✓ تم التحقق من الصياغة المقترحة")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "اعتماد الصياغة المقترحة" }));
    expect(await screen.findByText("مدعوم بالأدلة")).toBeInTheDocument();
    expect(screen.queryByText("يخالف الدليل")).toBeNull();
    expect(screen.getAllByText(fixed).length).toBeGreaterThan(0);
  });

  it("alternative wording: an UNVERIFIED proposal is never displayed as an answer", async () => {
    const user = userEvent.setup();
    serve({ c1: contradicted() }, () =>
      jsonResponse({ kind: "alternative_wording", original_claim_id: "c1", run_id: "run-c1:alt", proposed_text: "صياغة غير موثقة", verified: false, outcome: null }),
    );
    setup([claim("c1", contradicted().confirmed_claim_text)]);
    await user.click(await screen.findByRole("button", { name: "اقترح صياغة بديلة" }));
    expect(await screen.findByText("لم يتمكن ميزان من التحقق من صياغة بديلة موثوقة. راجع الادعاء والمصادر قبل النشر.")).toBeInTheDocument();
    expect(screen.queryByText("صياغة غير موثقة")).toBeNull();
    expect(screen.queryByRole("button", { name: "اعتماد الصياغة المقترحة" })).toBeNull();
  });

  it("alternative wording is not offered for supported, no-evidence or unavailable results", async () => {
    serve({ s: supported("s", "أ"), c4: noEvidence, c5: hadithUnavailable });
    setup([claim("s", "أ"), claim("c4", "ب"), claim("c5", "ج")]);
    await waitFor(() => expect(screen.queryByText(/جارٍ التحقق من الادعاء/)).toBeNull());
    expect(screen.queryByRole("button", { name: "اقترح صياغة بديلة" })).toBeNull();
  });

  it("a malformed backend response is a technical failure, not a verdict", async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ unexpected: true }));
    setup([claim("a", "أ")]);
    expect(await screen.findByText("تعذّر إكمال التحقق")).toBeInTheDocument();
    expect(screen.queryByText("مدعوم بالأدلة")).toBeNull();
  });
});
