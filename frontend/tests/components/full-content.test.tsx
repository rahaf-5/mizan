// @vitest-environment jsdom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FullContentInput } from "@/features/full-content/FullContentInput";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { jpegFile, pngFile, renderWithSession } from "../helpers";

function SessionProbe() {
  const { state } = useInputSession();
  return (
    <div data-testid="probe">
      {JSON.stringify({ prepared: state.prepared, image: state.image?.name ?? null, text: state.contentText })}
    </div>
  );
}
const probe = () => JSON.parse(screen.getByTestId("probe").textContent || "{}");

let fetchSpy: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchSpy = vi.fn();
  vi.stubGlobal("fetch", fetchSpy);
});
afterEach(() => {
  vi.unstubAllGlobals();
  expect(fetchSpy).not.toHaveBeenCalled(); // no verification / OCR request in Task 2
});

const setup = (state = {}) =>
  renderWithSession(
    <>
      <FullContentInput />
      <SessionProbe />
    </>,
    state,
  );

const fileInput = () => screen.getByLabelText("اختيار صورة", { selector: "input" }) as HTMLInputElement;

describe("Full Content — modes", () => {
  it("starts in text mode with accessible tabs", () => {
    setup();
    expect(screen.getByRole("tablist", { name: "نوع المحتوى" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "نص" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "صورة" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tabpanel")).toHaveAccessibleName("نص");
    expect(screen.getByRole("textbox", { name: "النص" })).toBeInTheDocument();
  });

  it("switches between text and image and keeps the text draft", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("textbox", { name: "النص" }), "مسودة");
    await user.click(screen.getByRole("tab", { name: "صورة" }));
    expect(screen.getByRole("tab", { name: "صورة" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: "رفع واستخراج النص" })).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "النص" })).toBeNull();
    await user.click(screen.getByRole("tab", { name: "نص" }));
    expect(screen.getByRole("textbox", { name: "النص" })).toHaveValue("مسودة");
  });

  it("supports arrow-key navigation between tabs (RTL)", async () => {
    const user = userEvent.setup();
    setup();
    screen.getByRole("tab", { name: "نص" }).focus();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "صورة" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "صورة" })).toHaveAttribute("aria-selected", "true");
  });
});

describe("Full Content — text", () => {
  it("requires text", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    expect(screen.getByRole("alert")).toHaveTextContent("يرجى إدخال النص الذي تريد فحصه.");
    expect(probe().prepared).toBeNull();
  });

  it("prepares the text for claim extraction without extracting", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(screen.getByRole("textbox", { name: "النص" }), "فقرة{enter}ثانية");
    expect(screen.getByText(/عدد الأحرف/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "استخراج الادعاءات" }));
    const { prepared } = probe();
    expect(prepared.kind).toBe("full_content_text");
    expect(prepared.next).toBe("claim_extraction");
    expect(prepared.extractionInput.text).toBe("فقرة\nثانية");
    expect(screen.getByRole("status")).toHaveTextContent("تم تجهيز النص لاستخراج الادعاءات");
  });
});

describe("Full Content — image", () => {
  it("shows upload UI with accepted formats", async () => {
    setup({ contentMode: "image" });
    expect(screen.getByText("الصيغ المقبولة: JPG أو PNG")).toBeInTheDocument();
    expect(fileInput()).toHaveAttribute("accept", "image/jpeg,image/png,.jpg,.jpeg,.png");
  });

  it("requires an image before continuing", async () => {
    const user = userEvent.setup();
    setup({ contentMode: "image" });
    await user.click(screen.getByRole("button", { name: "رفع واستخراج النص" }));
    expect(screen.getByRole("alert")).toHaveTextContent("يرجى اختيار صورة أولًا.");
  });

  it.each([
    ["PNG", () => pngFile()],
    ["JPG", () => jpegFile()],
  ])("accepts a %s image", async (_label, make) => {
    setup({ contentMode: "image" });
    const file = make();
    fireEvent.change(fileInput(), { target: { files: [file] } });
    await waitFor(() => expect(probe().image).toBe(file.name));
    expect(screen.getByText(file.name)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "إزالة الصورة" })).toBeInTheDocument();
  });

  it.each([
    ["GIF", new File(["GIF89a"], "a.gif", { type: "image/gif" }), "يُقبل فقط ملفات الصور بصيغة JPG أو PNG."],
    ["PDF", new File(["%PDF"], "a.pdf", { type: "application/pdf" }), "يُقبل فقط ملفات الصور بصيغة JPG أو PNG."],
    ["renamed text", new File(["hello"], "a.png", { type: "image/png" }), "تعذّرت قراءة الملف كصورة JPG أو PNG. يرجى اختيار صورة أخرى."],
  ])("rejects %s", async (_label, file, message) => {
    setup({ contentMode: "image" });
    fireEvent.change(fileInput(), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(message));
    expect(probe().image).toBeNull();
  });

  it("removes the selected image", async () => {
    const user = userEvent.setup();
    setup({ contentMode: "image" });
    fireEvent.change(fileInput(), { target: { files: [pngFile()] } });
    await waitFor(() => expect(probe().image).toBe("page.png"));
    await user.click(screen.getByRole("button", { name: "إزالة الصورة" }));
    expect(probe().image).toBeNull();
  });

  it("prepares the image for OCR without producing any text", async () => {
    const user = userEvent.setup();
    setup({ contentMode: "image" });
    fireEvent.change(fileInput(), { target: { files: [pngFile()] } });
    await waitFor(() => expect(probe().image).toBe("page.png"));
    await user.click(screen.getByRole("button", { name: "رفع واستخراج النص" }));
    const { prepared } = probe();
    expect(prepared.kind).toBe("full_content_image");
    expect(prepared.next).toBe("ocr");
    expect(prepared.extractionInput).toBeUndefined();
    expect(prepared.text).toBeUndefined();
    expect(screen.getByRole("status")).toHaveTextContent("تم تجهيز الصورة لاستخراج النص");
  });
});
