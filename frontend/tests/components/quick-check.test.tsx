// @vitest-environment jsdom
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QuickCheckForm } from "@/features/quick-check/QuickCheckForm";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { finalResult, supported, systemError } from "../fixtures/outcomes";
import { jsonResponse, renderWithSession } from "../helpers";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const SINGLE = "قراءة سورة الكهف يوم الجمعة سبب في حصول نور بين الجمعتين.";

function SessionProbe() {
  const { state } = useInputSession();
  return <div data-testid="probe">{JSON.stringify({ prepared: state.prepared, content: state.contentText })}</div>;
}
const probe = () => JSON.parse(screen.getByTestId("probe").textContent || "{}");

let fetchSpy: ReturnType<typeof vi.fn>;
let verifyOutcome: () => Response;
const urls = () => fetchSpy.mock.calls.map(([u]) => String(u));
const bodyOf = (suffix: string) =>
  JSON.parse(String(fetchSpy.mock.calls.find(([u]) => String(u).endsWith(suffix))?.[1]?.body));

/** Routes by URL like the real backend: confirmation gate echoes; verify returns the fixture. */
const router = (url: string, init?: RequestInit) => {
  const body = JSON.parse(String(init?.body ?? "{}"));
  if (url.endsWith("/api/v1/claims/confirm")) {
    const c = body.claims[0];
    return Promise.resolve(
      jsonResponse({
        kind: "confirmed",
        explicit_user_confirmation: true,
        next_stage: "claim_classification",
        confirmed_claims: [
          { claim_id: c.claim_id, confirmed_claim_text: c.text.trim(), user_confirmation_status: "confirmed", claim_type: null, provided_evidence: null, provided_reference: null },
        ],
      }),
    );
  }
  if (url.endsWith("/api/v1/verify")) return Promise.resolve(verifyOutcome());
  return Promise.reject(new Error(`unexpected ${url}`));
};

beforeEach(() => {
  push.mockReset();
  fetchSpy = vi.fn(router);
  verifyOutcome = () => jsonResponse(finalResult(supported("x", SINGLE)));
  vi.stubGlobal("fetch", fetchSpy);
});
afterEach(() => {
  vi.unstubAllGlobals();
  // Only the confirmation gate and verification of the CONFIRMED claim may be called.
  for (const u of urls()) expect(u).toMatch(/\/api\/v1\/(claims\/confirm|verify)$/);
});

const setup = () =>
  renderWithSession(
    <>
      <QuickCheckForm />
      <SessionProbe />
    </>,
  );

describe("Quick Check", () => {
  it("has the approved Arabic label, placeholder and action", () => {
    setup();
    const field = screen.getByRole("textbox", { name: "الادعاء" });
    expect(field).toHaveAttribute("placeholder", SINGLE);
    expect(screen.getByRole("button", { name: "تحقق من الادعاء" })).toBeInTheDocument();
  });

  it("asks for a claim when the input is empty", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    const field = screen.getByRole("textbox", { name: "الادعاء" });
    expect(screen.getByRole("alert")).toHaveTextContent("يرجى كتابة الادعاء الذي تريد التحقق منه.");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveFocus();
    expect(probe().prepared).toBeNull();
  });

  it("shows the Arabic placeholder right-to-left while empty", () => {
    setup();
    expect(screen.getByRole("textbox", { name: "الادعاء" })).toHaveAttribute("dir", "rtl");
  });

  it("clears the error once the user types", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    await user.type(screen.getByRole("textbox", { name: "الادعاء" }), "أ");
    expect(screen.getByRole("alert")).toBeEmptyDOMElement();
  });

  it("confirms the claim exactly as entered, then verifies only the confirmed claim", async () => {
    const user = userEvent.setup();
    setup();
    const typed = `  ${SINGLE}  `;
    await user.type(screen.getByRole("textbox", { name: "الادعاء" }), typed);
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    expect(await screen.findByText("مدعوم بالأدلة")).toBeInTheDocument();
    expect(urls()).toEqual([expect.stringMatching(/claims\/confirm$/), expect.stringMatching(/verify$/)]);
    const confirm = bodyOf("/api/v1/claims/confirm");
    expect(confirm.explicit_user_confirmation).toBe(true);
    expect(confirm.claims).toHaveLength(1);
    expect(confirm.claims[0]).toMatchObject({ origin: "manual", text: typed, selected: true });
    const verify = bodyOf("/api/v1/verify");
    expect(verify.claims).toHaveLength(1);
    expect(verify.claims[0].confirmed_claim_text).toBe(SINGLE);
    expect(verify.claims[0].claim_id).toBe(confirm.claims[0].claim_id);
    expect(probe().prepared.kind).toBe("quick_check_claim");
    expect(screen.getByText("لماذا وضعه ميزان هنا؟")).toBeInTheDocument();
  });

  it("shows a technical failure (not a verdict) and retries verification", async () => {
    const user = userEvent.setup();
    let calls = 0;
    verifyOutcome = () => (++calls === 1 ? jsonResponse(finalResult(systemError)) : jsonResponse(finalResult(supported("x", SINGLE))));
    setup();
    await user.type(screen.getByRole("textbox", { name: "الادعاء" }), SINGLE);
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    expect(await screen.findByText("تعذّر إكمال التحقق")).toBeInTheDocument();
    expect(screen.queryByText("مدعوم بالأدلة")).toBeNull();
    await user.click(screen.getByRole("button", { name: "إعادة التحقق" }));
    expect(await screen.findByText("مدعوم بالأدلة")).toBeInTheDocument();
    expect(urls().filter((u) => u.endsWith("/verify"))).toHaveLength(2);
  });

  it("a network failure during verification is technical and retryable", async () => {
    const user = userEvent.setup();
    let calls = 0;
    verifyOutcome = () => {
      if (++calls === 1) throw new TypeError("offline");
      return jsonResponse(finalResult(supported("x", SINGLE)));
    };
    setup();
    await user.type(screen.getByRole("textbox", { name: "الادعاء" }), SINGLE);
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    expect(await screen.findByText(/تعذّر الاتصال بالخادم/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "إعادة التحقق" }));
    expect(await screen.findByText("مدعوم بالأدلة")).toBeInTheDocument();
  });

  it("a confirmation-gate failure is reported and nothing is verified", async () => {
    const user = userEvent.setup();
    fetchSpy.mockImplementation(() => Promise.resolve(jsonResponse({ kind: "error", error: { code: "x", retryable: true } }, 500)));
    setup();
    await user.type(screen.getByRole("textbox", { name: "الادعاء" }), SINGLE);
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    expect(await screen.findByText("تعذّر تأكيد الادعاء بسبب مشكلة تقنية. حاول مرة أخرى.")).toBeInTheDocument();
    expect(urls().some((u) => u.endsWith("/verify"))).toBe(false);
    expect(probe().prepared).toBeNull();
  });

  it("a claim over 1000 characters is an input error (not technical) and nothing is sent", async () => {
    const user = userEvent.setup();
    setup();
    const long = "أ".repeat(1001);
    const field = screen.getByRole("textbox", { name: "الادعاء" });
    await user.click(field);
    await user.paste(long);
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    expect(screen.getByRole("alert")).toHaveTextContent("الادعاء أطول من الحد المسموح");
    expect(screen.getByRole("alert")).not.toHaveTextContent("مشكلة تقنية");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("exactly 1000 characters is accepted", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("textbox", { name: "الادعاء" }));
    await user.paste("ب".repeat(1000));
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    await waitFor(() => expect(urls()[0]).toMatch(/claims\/confirm$/));
  });

  it("a validation rejection from the gate is shown as an input problem", async () => {
    const user = userEvent.setup();
    fetchSpy.mockImplementation(() => Promise.resolve(jsonResponse({ detail: [{ type: "string_too_long" }] }, 422)));
    setup();
    await user.type(screen.getByRole("textbox", { name: "الادعاء" }), SINGLE);
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    expect(await screen.findByText("تعذّر قبول نص الادعاء. راجع النص ثم حاول مرة أخرى.")).toBeInTheDocument();
    expect(urls().some((u) => u.endsWith("/verify"))).toBe(false);
  });

  it("keeps the claim when the user goes back to edit", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("textbox", { name: "الادعاء" }), SINGLE);
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    await screen.findByText("مدعوم بالأدلة");
    await user.click(screen.getByRole("button", { name: "تعديل الادعاء" }));
    expect(screen.getByRole("textbox", { name: "الادعاء" })).toHaveValue(SINGLE);
  });

  it("guides multi-claim input to Full Content Check instead of a generic error", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(
      screen.getByRole("textbox", { name: "الادعاء" }),
      `${SINGLE}{enter}صيام يوم عرفة يكفّر ذنوب سنتين.`,
    );
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    expect(screen.getByText("يبدو أن النص يحتوي على أكثر من ادعاء")).toBeInTheDocument();
    expect(probe().prepared).toBeNull();
    expect(screen.queryByRole("button", { name: "تحقق من الادعاء" })).toBeNull();
    await user.click(screen.getByRole("button", { name: /الانتقال إلى فحص محتوى كامل/ }));
    expect(push).toHaveBeenCalledWith("/full-content");
    expect(probe().content).toBe(`${SINGLE}\nصيام يوم عرفة يكفّر ذنوب سنتين.`);
  });

  it("lets the user continue as a single claim", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("textbox", { name: "الادعاء" }), `${SINGLE}{enter}سطر آخر هنا للتجربة`);
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    await user.click(screen.getByRole("button", { name: "المتابعة كادعاء واحد" }));
    await waitFor(() => expect(probe().prepared?.kind).toBe("quick_check_claim"));
  });
});
