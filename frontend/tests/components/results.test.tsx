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
    expect(screen.getByRole("heading", { name: /يمكن استخدامها \(1\)/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /تحتاج تعديلًا أو مراجعة \(1\)/ })).toBeInTheDocument();
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
    expect(screen.getByRole("heading", { name: /لا تُستخدم بصيغتها الحالية \(1\)/ })).toBeInTheDocument();
    expect(screen.getByText("أدلة متعارضة")).toBeInTheDocument();
    expect(screen.getByText("لم يُعثر على دليل")).toBeInTheDocument();
    expect(screen.getByText(/عدم العثور على دليل لا يعني أن الادعاء خاطئ/)).toBeInTheDocument();

    // Hadith: unavailable source, explicitly no verdict and no invented grading.
    expect(screen.getByText("المصدر المطلوب غير متاح حاليًا")).toBeInTheDocument();
    expect(screen.getByText(/الدرر السنية — الموسوعة الحديثية/)).toBeInTheDocument();
    expect(screen.queryByText(/صحيح البخاري|حسن|ضعيف/)).toBeNull();

    expect(screen.getByText("خارج نطاق ميزان حاليًا")).toBeInTheDocument();
    // Technical failure shows no verdict about the claim.
    expect(screen.getByText("تعذّر إكمال التحقق")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /تعذّر التحقق منها حاليًا \(3\)/ })).toBeInTheDocument();
    // Summary by decision; each card keeps its exact status.
    const tile = (d: string) => document.querySelector(`li[data-decision="${d}"] p`)?.textContent;
    expect([tile("usable"), tile("needs_review"), tile("do_not_use"), tile("unverifiable")]).toEqual(["0", "2", "1", "3"]);
    expect(screen.getByText("عدد الادعاءات: 6")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "إعادة التحقق" })).toBeInTheDocument();
  });

  it("result card: decision → claim → why → what to do → short evidence preview; details only on request", async () => {
    const user = userEvent.setup();
    serve({ c1: contradicted() });
    const text = contradicted().confirmed_claim_text;
    setup([claim("c1", text)]);
    const card = (await screen.findByText("يخالف الدليل")).closest("li") as HTMLElement;
    // Order inside the card.
    const order = ["يخالف الدليل", text, "لماذا هذه النتيجة؟", "ماذا تفعل؟", "الأدلة التي اعتمد عليها ميزان", "عرض الأدلة والتفاصيل"];
    const pos = order.map((x) => card.textContent!.indexOf(x));
    expect(pos.every((p) => p >= 0)).toBe(true);
    expect([...pos].sort((a, b) => a - b)).toEqual(pos);
    // The claim appears once; the why states the documented location; one short action.
    expect(within(card).getAllByText(text)).toHaveLength(1);
    expect(within(card).getByText("ورد في ادعائك أن النص في «سورة آل عمران»، لكنه في المصحف في سورة البقرة، الآية 158.")).toBeInTheDocument();
    expect(within(card).getByText("لا تنشره بصيغته الحالية؛ صحّح الجزء المخالف أو احذفه.")).toBeInTheDocument();
    // Preview: source — place only; no text, provider, link or technical fields yet.
    expect(within(card).getByText("— سورة البقرة، الآية 158")).toBeInTheDocument();
    expect(card.querySelector("[data-evidence-id]")).toBeNull();
    expect(within(card).queryByRole("link")).toBeNull();
    // No duplicated / technical sections in the main card.
    for (const gone of ["ما الذي تحقّق منه ميزان في الادعاء", "الموضع الموثّق في المصحف", "مؤشرات التحقق", "شرح ميزان", "حدود هذه النتيجة", "Quranpedia", "المزوّد"])
      expect(card.textContent).not.toContain(gone);
    expect(card.textContent).not.toMatch(/sha256|text_sha256|source_record_id|%|confidence|درجة الثقة/);

    // Level 3: the traceable details.
    await user.click(within(card).getByRole("button", { name: "عرض الأدلة والتفاصيل" }));
    const ev = card.querySelector(`[data-evidence-id="${QURAN_EVIDENCE.evidence_id}"]`) as HTMLElement;
    expect(within(ev).getByText("القرآن الكريم")).toBeInTheDocument();
    // The fixture's span is a normalised matching key → the record's own text is shown instead.
    const region = within(ev).getByRole("region", { name: "النص من المصدر" });
    expect(within(region).getByText(QURAN_EVIDENCE.text)).toBeInTheDocument();
    expect(ev.textContent).not.toMatch(/ان الصفا والمروه/);
    expect(within(ev).getByText(QURAN_EVIDENCE.reference)).toBeInTheDocument();
    expect(within(ev).getByRole("link", { name: "فتح السجل الأصلي" })).toHaveAttribute("href", QURAN_EVIDENCE.source_url);
    expect(within(card).getByRole("button", { name: "إخفاء الأدلة والتفاصيل" })).toHaveAttribute("aria-expanded", "true");
  });

  it("conflicting evidence: details group supporting / opposing; limitations only inside details", async () => {
    const user = userEvent.setup();
    serve({ c3: conflicting });
    setup([claim("c3", conflicting.confirmed_claim_text)]);
    const card = (await screen.findByText("أدلة متعارضة")).closest("li") as HTMLElement;
    expect(within(card).getByText(/المصادر مختلفة بشأن «كذا»/)).toBeInTheDocument();
    expect(within(card).queryByText("حدود هذا التحقق")).toBeNull();
    await user.click(within(card).getByRole("button", { name: "عرض الأدلة والتفاصيل" }));
    const pro = within(card).getByRole("region", { name: "أدلة تؤيد" });
    const con = within(card).getByRole("region", { name: "أدلة تخالف" });
    expect(within(pro).getByText("لا تأخذه سِنَة أي: نعاس.")).toBeInTheDocument(); // verbatim cited passage
    expect(within(con).getByText("لا يغلبه نعاس ولا نوم")).toBeInTheDocument();
    expect(within(pro).queryByText("لا يغلبه نعاس ولا نوم")).toBeNull();
    expect(within(card).getByText("حدود هذا التحقق")).toBeInTheDocument();
    expect(within(card).getByText(conflicting.limitations[0])).toBeInTheDocument();
    expect(card.textContent).not.toMatch(/المؤلف|غير مذكور لدى المزوّد|تحليل آلي|مطابقة آلية|قوة الدليل/);
  });

  it("no evidence used → no empty evidence section and no details button", async () => {
    serve({ c4: noEvidence });
    setup([claim("c4", noEvidence.confirmed_claim_text)]);
    const card = (await screen.findByText("لم يُعثر على دليل")).closest("li") as HTMLElement;
    expect(within(card).getByText(/عدم العثور على دليل لا يعني أن الادعاء خاطئ/)).toBeInTheDocument();
    expect(within(card).queryByText("الأدلة التي اعتمد عليها ميزان")).toBeNull();
    expect(within(card).queryByRole("button", { name: "عرض الأدلة والتفاصيل" })).toBeNull();
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
    expect(screen.getByText("نتيجة التحقق من الصياغة المقترحة")).toBeInTheDocument();
    const tile = (d: string) => document.querySelector(`li[data-decision="${d}"] p`)?.textContent;
    expect([tile("usable"), tile("do_not_use")]).toEqual(["0", "1"]);
    await user.click(screen.getByRole("button", { name: "اعتماد الصياغة المقترحة" }));
    expect(await screen.findByText("مدعوم بالأدلة")).toBeInTheDocument();
    expect(screen.queryByText("يخالف الدليل")).toBeNull();
    // Report updated dynamically: claim moved group and summary counters changed (spec §15).
    expect([tile("usable"), tile("do_not_use")]).toEqual(["1", "0"]);
    expect(screen.getByText("اعتمدت الصياغة المقترحة بعد التحقق منها.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /يمكن استخدامها \(1\)/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /لا تُستخدم بصيغتها الحالية/ })).toBeNull();
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
