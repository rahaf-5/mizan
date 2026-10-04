// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FullContentPage from "@/app/full-content/page";
import { FullContentInput } from "@/features/full-content/FullContentInput";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { InputSessionProvider } from "@/lib/input/InputSessionProvider";
import { renderWithSession } from "../helpers";

function SessionProbe() {
  const { state } = useInputSession();
  return <div data-testid="probe">{JSON.stringify({ prepared: state.prepared, text: state.contentText })}</div>;
}
const probe = () => JSON.parse(screen.getByTestId("probe").textContent || "{}");

let fetchSpy: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchSpy = vi.fn();
  vi.stubGlobal("fetch", fetchSpy);
});
afterEach(() => {
  vi.unstubAllGlobals();
  expect(fetchSpy).not.toHaveBeenCalled(); // no extraction / verification / upload request
});

const setup = (state = {}) =>
  renderWithSession(
    <>
      <FullContentInput />
      <SessionProbe />
    </>,
    state,
  );

describe("Full Content Check — text only (image/OCR out of MVP scope)", () => {
  it("renders the page title and a single labelled text area", () => {
    render(
      <InputSessionProvider>
        <FullContentPage />
      </InputSessionProvider>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "فحص محتوى كامل" })).toBeInTheDocument();
    expect(screen.getByText("أدخل النص الديني، ثم راجع الادعاءات المستخرجة قبل التحقق.")).toBeInTheDocument();
    expect(screen.getAllByRole("textbox")).toHaveLength(1);
    expect(screen.getByRole("textbox", { name: "النص" })).toBeInTheDocument();
  });

  it("has no image tab, file input, upload or OCR controls", () => {
    const { container } = setup();
    expect(screen.queryByRole("tablist")).toBeNull();
    expect(screen.queryByRole("tab")).toBeNull();
    expect(container.querySelector('input[type="file"]')).toBeNull();
    expect(document.body.textContent).not.toMatch(/صورة|OCR|رفع|Google/);
    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "استخراج الادعاءات" })).toBeInTheDocument();
  });

  it("requires text", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    expect(screen.getByRole("alert")).toHaveTextContent("يرجى إدخال النص الذي تريد فحصه.");
    expect(screen.getByRole("textbox", { name: "النص" })).toHaveAttribute("aria-invalid", "true");
    expect(probe().prepared).toBeNull();
  });

  it("keeps the draft in the session and shows a character count", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("textbox", { name: "النص" }), "مسودة");
    expect(probe().text).toBe("مسودة");
    expect(screen.getByText(/عدد الأحرف/)).toBeInTheDocument();
  });

  it("restores an existing draft (e.g. carried over from Quick Check)", () => {
    setup({ contentText: "نص منقول من الفحص السريع" });
    expect(screen.getByRole("textbox", { name: "النص" })).toHaveValue("نص منقول من الفحص السريع");
  });

  it("prepares the text exactly as entered for claim extraction, without extracting", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("textbox", { name: "النص" }), "  فقرة{enter}ثانية  ");
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    const { prepared } = probe();
    expect(prepared.kind).toBe("full_content_text");
    expect(prepared.next).toBe("claim_extraction");
    expect(prepared.extractionInput).toEqual({ mode: "full_content", input_type: "text", text: "  فقرة\nثانية  " });
    const status = screen.getAllByRole("status").find((s) => s.textContent?.includes("تم تجهيز النص"));
    expect(status).toHaveTextContent("لم يبدأ أي تحقق بعد");
  });

  it("edit returns to the text with the draft intact", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("textbox", { name: "النص" }), "نص");
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    await user.click(screen.getByRole("button", { name: "تعديل" }));
    expect(screen.getByRole("textbox", { name: "النص" })).toHaveValue("نص");
  });
});
