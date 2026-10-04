// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QuickCheckForm } from "@/features/quick-check/QuickCheckForm";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { renderWithSession } from "../helpers";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const SINGLE = "قراءة سورة الكهف يوم الجمعة سبب في حصول نور بين الجمعتين.";

function SessionProbe() {
  const { state } = useInputSession();
  return <div data-testid="probe">{JSON.stringify({ prepared: state.prepared, content: state.contentText })}</div>;
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
  // Task 2 must never send a verification (or any) request.
  expect(fetchSpy).not.toHaveBeenCalled();
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

  it("prepares the claim exactly as entered, without verifying", async () => {
    const user = userEvent.setup();
    setup();
    const typed = `  ${SINGLE}  `;
    await user.type(screen.getByRole("textbox", { name: "الادعاء" }), typed);
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    const { prepared } = probe();
    expect(prepared.kind).toBe("quick_check_claim");
    expect(prepared.next).toBe("claim_confirmation");
    expect(prepared.extractionInput).toEqual({
      mode: "quick_check",
      input_type: "text",
      text: typed,
    });
    expect(screen.getByRole("status")).toHaveTextContent("تم تجهيز الادعاء للمراجعة والتأكيد");
    expect(screen.getByRole("status")).toHaveTextContent("لم يبدأ أي تحقق بعد");
  });

  it("keeps the claim when the user goes back to edit", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("textbox", { name: "الادعاء" }), SINGLE);
    await user.click(screen.getByRole("button", { name: "تحقق من الادعاء" }));
    await user.click(screen.getByRole("button", { name: "تعديل" }));
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
    expect(probe().prepared.kind).toBe("quick_check_claim");
  });
});
