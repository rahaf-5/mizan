// @vitest-environment jsdom
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ClaimReview } from "@/features/claim-review/ClaimReview";
import type { ReviewClaim } from "@/lib/claims/types";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { jsonResponse, renderWithSession } from "../helpers";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const SOURCE = "قراءة سورة الكهف يوم الجمعة واجبة، وهي سبب لمغفرة الذنوب، أنصحكم جميعًا بقراءتها.";
const A: ReviewClaim = {
  id: "a",
  origin: "extracted",
  originalText: "قراءة سورة الكهف يوم الجمعة واجبة",
  extractedText: "قراءة سورة الكهف يوم الجمعة واجبة.",
  text: "قراءة سورة الكهف يوم الجمعة واجبة.",
  selected: true,
  extractionStatus: "clear",
  providedEvidence: null,
  providedReference: null,
};
const B: ReviewClaim = {
  ...A,
  id: "b",
  originalText: "وهي سبب لمغفرة الذنوب",
  extractedText: "قراءة سورة الكهف يوم الجمعة سبب لمغفرة الذنوب.",
  text: "قراءة سورة الكهف يوم الجمعة سبب لمغفرة الذنوب.",
  extractionStatus: "ambiguous",
  providedReference: "رواه الحاكم",
};

function Probe() {
  const { state } = useInputSession();
  return <div data-testid="probe">{JSON.stringify({ review: state.review, confirmation: state.confirmation, text: state.contentText })}</div>;
}
const probe = () => JSON.parse(screen.getByTestId("probe").textContent || "{}");

let fetchSpy: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchSpy = vi.fn();
  vi.stubGlobal("fetch", fetchSpy);
});
afterEach(() => {
  vi.unstubAllGlobals();
  // Claim Review may only call the CONFIRMATION gate — never extraction, retrieval or verification.
  for (const [url] of fetchSpy.mock.calls) expect(String(url)).toMatch(/\/api\/v1\/claims\/confirm$/);
});

const setup = (claims: ReviewClaim[] = [A, B]) =>
  renderWithSession(
    <>
      <ClaimReview />
      <Probe />
    </>,
    { contentText: SOURCE, review: { sourceText: SOURCE, claims } },
  );

const card = (n: string) => screen.getByRole("article", { name: `الادعاء ${n}` });
const confirmedResponse = (claims: { claim_id: string; confirmed_claim_text: string; user_confirmation_status: string }[]) =>
  jsonResponse({
    kind: "confirmed",
    next_stage: "claim_classification",
    verification_started: false,
    confirmed_claims: claims.map((c) => ({ ...c, claim_type: null, provided_evidence: null, provided_reference: null })),
  });
const sentClaims = () => JSON.parse(fetchSpy.mock.calls[0][1].body);

describe("Claim Review", () => {
  it("shows every extracted claim with selection, counts, badges and the original excerpt", () => {
    setup();
    expect(screen.getAllByRole("article")).toHaveLength(2);
    expect(screen.getByText("عدد الادعاءات: 2 — المحدد للتحقق: 2")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "تحديد الادعاء 1 للتحقق" })).toBeChecked();
    expect(within(card("2")).getByText(/صياغة غير واضحة/)).toBeInTheDocument();
    expect(within(card("2")).getByText("رواه الحاكم")).toBeInTheDocument();
    expect(within(card("1")).getByText("«قراءة سورة الكهف يوم الجمعة واجبة»")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "تحقّق من الادعاءات المحددة" })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/صحيح|ضعيف|مدعوم|متناقض|supported|contradicted/);
  });

  it("deselecting excludes a claim; zero selected shows the required message and sends nothing", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("checkbox", { name: "تحديد الادعاء 1 للتحقق" }));
    await user.click(screen.getByRole("checkbox", { name: "تحديد الادعاء 2 للتحقق" }));
    expect(screen.getByText("عدد الادعاءات: 2 — المحدد للتحقق: 0")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "تحقّق من الادعاءات المحددة" }));
    const alert = screen.getByText("اختر ادعاءً واحدًا على الأقل للمتابعة.");
    expect(alert.closest("[role=alert]")).not.toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("editing a claim: the edited text is what gets confirmed; extracted text is kept separately", async () => {
    const user = userEvent.setup();
    fetchSpy.mockResolvedValue(confirmedResponse([{ claim_id: "a", confirmed_claim_text: "قراءة سورة الكهف يوم الجمعة مستحبة.", user_confirmation_status: "edited" }]));
    setup();
    await user.click(within(card("1")).getByRole("button", { name: /تعديل/ }));
    const box = screen.getByRole("textbox", { name: "تعديل نص الادعاء 1" });
    await user.clear(box);
    await user.type(box, "قراءة سورة الكهف يوم الجمعة مستحبة.");
    await user.click(within(card("1")).getByRole("button", { name: "حفظ" }));
    expect(within(card("1")).getByText(/معدَّل/)).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "تحديد الادعاء 2 للتحقق" }));
    await user.click(screen.getByRole("button", { name: "تحقّق من الادعاءات المحددة" }));
    const body = sentClaims();
    expect(body.explicit_user_confirmation).toBe(true);
    const a = body.claims.find((c: { claim_id: string }) => c.claim_id === "a");
    expect(a).toMatchObject({ text: "قراءة سورة الكهف يوم الجمعة مستحبة.", extracted_claim_text: "قراءة سورة الكهف يوم الجمعة واجبة.", selected: true });
    expect(body.claims.find((c: { claim_id: string }) => c.claim_id === "b").selected).toBe(false);
  });

  it("cannot save an empty edit", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(within(card("1")).getByRole("button", { name: /تعديل/ }));
    await user.clear(screen.getByRole("textbox", { name: "تعديل نص الادعاء 1" }));
    await user.click(within(card("1")).getByRole("button", { name: "حفظ" }));
    expect(within(card("1")).getByRole("alert")).toHaveTextContent("لا يمكن حفظ ادعاء فارغ.");
    expect(probe().review.claims[0].text).toBe(A.text);
  });

  it("deleting a claim removes it from the confirmation request", async () => {
    const user = userEvent.setup();
    fetchSpy.mockResolvedValue(confirmedResponse([{ claim_id: "b", confirmed_claim_text: B.text, user_confirmation_status: "confirmed" }]));
    setup();
    await user.click(within(card("1")).getByRole("button", { name: /حذف/ }));
    expect(screen.getAllByRole("article")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "تحقّق من الادعاءات المحددة" }));
    expect(sentClaims().claims.map((c: { claim_id: string }) => c.claim_id)).toEqual(["b"]);
  });

  it("manually added claims go through the same confirmation path", async () => {
    const user = userEvent.setup();
    fetchSpy.mockResolvedValue(confirmedResponse([]));
    setup([A]);
    await user.type(screen.getByRole("textbox", { name: "نص الادعاء الجديد" }), "الصلاة عماد الدين.");
    await user.click(screen.getByRole("button", { name: "إضافة الادعاء" }));
    expect(screen.getAllByRole("article")).toHaveLength(2);
    expect(within(card("2")).getByText("مضاف يدويًا")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "تحقّق من الادعاءات المحددة" }));
    const manual = sentClaims().claims.find((c: { origin: string }) => c.origin === "manual");
    expect(manual).toMatchObject({ text: "الصلاة عماد الدين.", selected: true, extracted_claim_text: null });
  });

  it("explicit confirmation goes through the gate, then opens the results page", async () => {
    const user = userEvent.setup();
    fetchSpy.mockResolvedValue(confirmedResponse([
      { claim_id: "a", confirmed_claim_text: A.text, user_confirmation_status: "confirmed" },
      { claim_id: "b", confirmed_claim_text: B.text, user_confirmation_status: "confirmed" },
    ]));
    setup();
    expect(fetchSpy).not.toHaveBeenCalled(); // nothing is sent before the click
    await user.click(screen.getByRole("button", { name: "تحقّق من الادعاءات المحددة" }));
    await screen.findByText("تم تأكيد 2 من الادعاءات");
    expect(push).toHaveBeenCalledWith("/full-content/results");
    expect(screen.getByRole("link", { name: "عرض نتائج التحقق" })).toHaveAttribute("href", "/full-content/results");
    expect(fetchSpy).toHaveBeenCalledTimes(1); // only the confirmation gate; verification runs on the results page
    expect(probe().confirmation.confirmedClaims).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "العودة إلى المراجعة" }));
    expect(screen.getAllByRole("article")).toHaveLength(2);
  });

  it("confirmation failure is reported as technical and can be retried", async () => {
    const user = userEvent.setup();
    fetchSpy.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    setup();
    await user.click(screen.getByRole("button", { name: "تحقّق من الادعاءات المحددة" }));
    expect(await screen.findByText("تعذّر تأكيد الادعاءات بسبب مشكلة تقنية. حاول مرة أخرى.")).toBeInTheDocument();
    expect(probe().confirmation).toBeNull();
  });

  it("empty extraction: shows the empty state, back link and manual add", async () => {
    const user = userEvent.setup();
    setup([]);
    expect(screen.getByText("لم نجد ادعاءات دينية قابلة للتحقق في هذا المحتوى.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "العودة لتعديل النص" })).toHaveAttribute("href", "/full-content");
    await user.type(screen.getByRole("textbox", { name: "نص الادعاء الجديد" }), "صيام عرفة يكفر سنتين.");
    await user.click(screen.getByRole("button", { name: "إضافة الادعاء" }));
    expect(screen.getAllByRole("article")).toHaveLength(1);
    expect(probe().text).toBe(SOURCE); // original content preserved
  });

  it("without a review (e.g. after reload) points back to Full Content", () => {
    renderWithSession(<ClaimReview />);
    expect(screen.getByText("لا توجد ادعاءات لمراجعتها")).toBeInTheDocument();
  });

  it("keyboard: Space toggles a claim checkbox", async () => {
    const user = userEvent.setup();
    setup();
    screen.getByRole("checkbox", { name: "تحديد الادعاء 1 للتحقق" }).focus();
    await user.keyboard(" ");
    expect(screen.getByRole("checkbox", { name: "تحديد الادعاء 1 للتحقق" })).not.toBeChecked();
    await waitFor(() => expect(screen.getByText("عدد الادعاءات: 2 — المحدد للتحقق: 1")).toBeInTheDocument());
  });
});
