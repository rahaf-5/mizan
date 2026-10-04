// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FullContentPage from "@/app/full-content/page";
import { FullContentInput } from "@/features/full-content/FullContentInput";
import { InputSessionProvider, useInputSession } from "@/lib/input/InputSessionProvider";
import { jsonResponse, renderWithSession } from "../helpers";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const KAHF = "قراءة سورة الكهف يوم الجمعة واجبة، وهي سبب لمغفرة الذنوب، أنصحكم جميعًا بقراءتها.";

function SessionProbe() {
  const { state } = useInputSession();
  return <div data-testid="probe">{JSON.stringify({ review: state.review, text: state.contentText })}</div>;
}
const probe = () => JSON.parse(screen.getByTestId("probe").textContent || "{}");

let fetchSpy: ReturnType<typeof vi.fn>;
beforeEach(() => {
  push.mockReset();
  fetchSpy = vi.fn();
  vi.stubGlobal("fetch", fetchSpy);
});
afterEach(() => {
  vi.unstubAllGlobals();
  // The only call this screen may make is claim EXTRACTION — never confirmation/verification.
  for (const [url] of fetchSpy.mock.calls) expect(String(url)).toMatch(/\/api\/v1\/claims\/extract$/);
});

const setup = (state = {}) =>
  renderWithSession(
    <>
      <FullContentInput />
      <SessionProbe />
    </>,
    state,
  );

const extracted = (claims: { id: string; text: string; excerpt?: string }[]) =>
  jsonResponse({
    kind: "extraction",
    discarded_ungrounded_count: 0,
    claims: claims.map((c) => ({
      claim_id: c.id,
      original_text: c.excerpt ?? c.text,
      extracted_claim_text: c.text,
      extraction_status: "clear",
      provided_evidence: null,
      provided_reference: null,
      user_confirmation_status: "pending",
    })),
  });

describe("Full Content Check — text only", () => {
  it("renders a single labelled text area, no image controls", () => {
    const { container } = render(
      <InputSessionProvider>
        <FullContentPage />
      </InputSessionProvider>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "فحص محتوى كامل" })).toBeInTheDocument();
    expect(screen.getAllByRole("textbox")).toHaveLength(1);
    expect(screen.queryByRole("tab")).toBeNull();
    expect(container.querySelector('input[type="file"]')).toBeNull();
    expect(document.body.textContent).not.toMatch(/صورة|OCR/);
  });

  it("requires text and does not call the backend", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    expect(screen.getByRole("alert")).toHaveTextContent("يرجى إدخال النص الذي تريد فحصه.");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("enforces the 10,000 character limit before calling the backend", async () => {
    const user = userEvent.setup();
    setup({ contentText: "ا".repeat(10_001) });
    expect(screen.getByText(/عدد الأحرف: .* من/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    expect(screen.getByRole("alert")).toHaveTextContent("النص أطول من الحد المسموح");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("keeps the draft in the session", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("textbox", { name: "النص" }), "مسودة");
    expect(probe().text).toBe("مسودة");
  });
});

describe("Full Content → Claim Extraction", () => {
  it("sends only the text, shows progress, then opens Claim Review with pending claims", async () => {
    const user = userEvent.setup();
    let resolve: (r: Response) => void = () => {};
    fetchSpy.mockReturnValue(new Promise<Response>((r) => (resolve = r)));
    setup({ contentText: KAHF });
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    expect(screen.getAllByRole("status").some((s) => s.textContent?.includes("جارٍ استخراج الادعاءات"))).toBe(true);
    expect(screen.getByRole("button", { name: "استخراج الادعاءات" })).toBeDisabled();
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/claims\/extract$/);
    expect(JSON.parse(init.body)).toEqual({ text: KAHF });
    resolve(
      extracted([
        { id: "a", text: "قراءة سورة الكهف يوم الجمعة واجبة." },
        { id: "b", text: "قراءة سورة الكهف يوم الجمعة سبب لمغفرة الذنوب.", excerpt: "وهي سبب لمغفرة الذنوب" },
      ]),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/full-content/claims"));
    const { review } = probe();
    expect(review.sourceText).toBe(KAHF);
    expect(review.claims.map((c: { text: string; selected: boolean }) => [c.text, c.selected])).toEqual([
      ["قراءة سورة الكهف يوم الجمعة واجبة.", true],
      ["قراءة سورة الكهف يوم الجمعة سبب لمغفرة الذنوب.", true],
    ]);
    expect(probe().text).toBe(KAHF); // original text kept
  });

  it("zero claims is a successful extraction (review shows the empty state)", async () => {
    const user = userEvent.setup();
    fetchSpy.mockResolvedValue(extracted([]));
    setup({ contentText: "جزاكم الله خيرًا" });
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/full-content/claims"));
    expect(probe().review.claims).toEqual([]);
  });

  it.each([
    [502, { kind: "failure", error: { code: "llm_invalid_response", stage: "claim_extraction", message: "x", retryable: true } }, "حدثت مشكلة تقنية أثناء استخراج الادعاءات", true],
    [504, { kind: "failure", error: { code: "llm_timeout", stage: "claim_extraction", message: "x", retryable: true } }, "حدثت مشكلة تقنية أثناء استخراج الادعاءات", true],
    [429, { kind: "failure", error: { code: "llm_rate_limited", stage: "claim_extraction", message: "x", retryable: true } }, "مشغولة حاليًا", true],
    [503, { kind: "failure", error: { code: "llm_not_configured", stage: "claim_extraction", message: "x", retryable: false } }, "غير مهيأة حاليًا", false],
  ])("provider failure (%s) is a technical failure, never 'no claims'", async (status, body, message, retryable) => {
    const user = userEvent.setup();
    fetchSpy.mockResolvedValue(jsonResponse(body, status));
    setup({ contentText: KAHF });
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    const alert = await screen.findByText(new RegExp(message));
    expect(alert.closest("[role=alert]")).toHaveTextContent("تعذّر استخراج الادعاءات");
    expect(document.body.textContent).not.toMatch(/لم نجد ادعاءات/);
    expect(push).not.toHaveBeenCalled();
    expect(probe().review).toBeNull(); // nothing invented
    expect(screen.queryByRole("button", { name: "إعادة المحاولة" }) !== null).toBe(retryable);
  });

  it("network failure can be retried and then succeeds", async () => {
    const user = userEvent.setup();
    fetchSpy.mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(extracted([{ id: "a", text: "الصلاة عماد الدين." }]));
    setup({ contentText: "الصلاة عماد الدين." });
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    await user.click(await screen.findByRole("button", { name: "إعادة المحاولة" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/full-content/claims"));
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("blocked content offers manual claim entry", async () => {
    const user = userEvent.setup();
    fetchSpy.mockResolvedValue(jsonResponse({ kind: "failure", error: { code: "llm_content_blocked", stage: "claim_extraction", message: "x", retryable: false } }, 422));
    setup({ contentText: KAHF });
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    await user.click(await screen.findByRole("button", { name: "إضافة الادعاءات يدويًا" }));
    expect(push).toHaveBeenCalledWith("/full-content/claims");
    expect(probe().review).toEqual({ sourceText: KAHF, claims: [] });
  });

  it("offers to continue an existing review for the same text", () => {
    setup({ contentText: KAHF, review: { sourceText: KAHF, claims: [] } });
    expect(screen.getByRole("link", { name: /متابعة مراجعة الادعاءات المستخرجة/ })).toHaveAttribute("href", "/full-content/claims");
  });
});
