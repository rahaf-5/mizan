// @vitest-environment jsdom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FullContentInput } from "@/features/full-content/FullContentInput";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import { jpegFile, jsonResponse, makeExtraction, pngFile, renderWithSession } from "../helpers";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

function SessionProbe() {
  const { state } = useInputSession();
  return (
    <div data-testid="probe">
      {JSON.stringify({
        prepared: state.prepared,
        image: state.image?.name ?? null,
        text: state.contentText,
        ocr: state.ocr ? { raw: state.ocr.extraction.raw_text, reviewed: state.ocr.reviewedText } : null,
      })}
    </div>
  );
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
  // The only request this screen may ever make is the OCR upload — never extraction/verification.
  for (const [url, init] of fetchSpy.mock.calls) {
    expect(String(url)).toMatch(/\/api\/v1\/ocr$/);
    expect(init?.method).toBe("POST");
  }
});

const status = (text: string) => screen.getAllByRole("status").find((el) => el.textContent?.includes(text));

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
    expect(status("تم تجهيز النص لاستخراج الادعاءات")).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("Full Content — image", () => {
  it("shows upload UI with accepted formats", async () => {
    setup({ contentMode: "image" });
    expect(screen.getByText(/الصيغ المقبولة: JPG أو PNG — بحد أقصى 7 ميغابايت/)).toBeInTheDocument();
    expect(fileInput()).toHaveAttribute("accept", "image/jpeg,image/png,.jpg,.jpeg,.png");
  });

  it("shows the privacy notice before any upload and links it to the file input", () => {
    setup({ contentMode: "image" });
    const notice = screen.getByText(/تُرسَل الصورة التي ترفعها إلى خدمة Google Cloud Vision/);
    expect(notice).toBeInTheDocument();
    expect(screen.getByText("قبل رفع الصورة")).toBeInTheDocument();
    const describedBy = fileInput().getAttribute("aria-describedby") ?? "";
    const noticeId = notice.closest("[id]")?.getAttribute("id") ?? "missing";
    expect(describedBy.split(" ")).toContain(noticeId);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("requires an image before continuing", async () => {
    const user = userEvent.setup();
    setup({ contentMode: "image" });
    await user.click(screen.getByRole("button", { name: "رفع واستخراج النص" }));
    expect(screen.getByRole("alert")).toHaveTextContent("يرجى اختيار صورة أولًا.");
    expect(fetchSpy).not.toHaveBeenCalled();
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

  it("rejects images over the 7 MB limit before uploading", async () => {
    setup({ contentMode: "image" });
    const big = new File([new Uint8Array(7 * 1024 * 1024 + 1)], "big.png", { type: "image/png" });
    fireEvent.change(fileInput(), { target: { files: [big] } });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("حجم الصورة يتجاوز الحد المسموح (7 ميغابايت)"),
    );
    expect(probe().image).toBeNull();
  });
});

async function selectAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  fireEvent.change(fileInput(), { target: { files: [pngFile()] } });
  await waitFor(() => expect(probe().image).toBe("page.png"));
  await user.click(screen.getByRole("button", { name: "رفع واستخراج النص" }));
}

describe("Full Content — OCR upload", () => {
  it("uploads to the backend OCR endpoint and opens the review screen", async () => {
    const user = userEvent.setup();
    fetchSpy.mockResolvedValue(jsonResponse(makeExtraction({ raw_text: "نص خام" })));
    setup({ contentMode: "image" });
    await selectAndSubmit(user);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/full-content/review"));
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, init] = fetchSpy.mock.calls[0];
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("image")).toBeInstanceOf(File);
    // raw text stored for review; nothing prepared for extraction yet
    expect(probe().ocr).toEqual({ raw: "نص خام", reviewed: "نص خام" });
    expect(probe().prepared).toBeNull();
  });

  it("shows a processing state while OCR runs", async () => {
    const user = userEvent.setup();
    let resolve: (r: Response) => void = () => {};
    fetchSpy.mockReturnValue(new Promise<Response>((r) => (resolve = r)));
    setup({ contentMode: "image" });
    await selectAndSubmit(user);
    expect(status("جارٍ استخراج النص من الصورة")).toBeTruthy();
    expect(screen.getByRole("button", { name: "رفع واستخراج النص" })).toBeDisabled();
    resolve(jsonResponse(makeExtraction()));
    await waitFor(() => expect(push).toHaveBeenCalled());
  });

  it.each([
    [{ kind: "failure", provider: "google_vision", error: { code: "ocr_error", stage: "user_input", message: "x", retryable: true } }, 502, "حدثت مشكلة تقنية أثناء استخراج النص", true],
    [{ kind: "failure", provider: "google_vision", error: { code: "ocr_timeout", stage: "user_input", message: "x", retryable: true } }, 504, "حدثت مشكلة تقنية أثناء استخراج النص", true],
    [{ kind: "failure", provider: "none", error: { code: "ocr_not_configured", stage: "user_input", message: "x", retryable: false } }, 503, "خدمة استخراج النص من الصور غير مهيأة", false],
  ])("treats OCR failure as a technical problem (%#)", async (body, code, message, retryable) => {
    const user = userEvent.setup();
    fetchSpy.mockResolvedValue(jsonResponse(body, code));
    setup({ contentMode: "image" });
    await selectAndSubmit(user);
    const alert = await screen.findByText(new RegExp(message));
    expect(alert.closest("[role=alert]")).toHaveTextContent("تعذّر استخراج النص من الصورة");
    expect(push).not.toHaveBeenCalled();
    expect(probe().ocr).toBeNull();
    expect(screen.queryByRole("button", { name: "إعادة المحاولة" }) !== null).toBe(retryable);
    // never phrased as an evidence/verification result
    expect(document.body.textContent).not.toMatch(/insufficient_evidence|no_evidence_found|contradicted/);
  });

  it("retries after a technical failure", async () => {
    const user = userEvent.setup();
    fetchSpy
      .mockResolvedValueOnce(jsonResponse({ kind: "failure", provider: "g", error: { code: "ocr_error", stage: null, message: "x", retryable: true } }, 502))
      .mockResolvedValueOnce(jsonResponse(makeExtraction()));
    setup({ contentMode: "image" });
    await selectAndSubmit(user);
    await user.click(await screen.findByRole("button", { name: "إعادة المحاولة" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/full-content/review"));
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("handles network errors", async () => {
    const user = userEvent.setup();
    fetchSpy.mockRejectedValue(new TypeError("Failed to fetch"));
    setup({ contentMode: "image" });
    await selectAndSubmit(user);
    expect(await screen.findByText(/تعذّر الاتصال بخدمة استخراج النص/)).toBeInTheDocument();
  });

  it("shows backend content validation errors as file errors", async () => {
    const user = userEvent.setup();
    fetchSpy.mockResolvedValue(jsonResponse({ kind: "input_error", code: "unreadable_image", message: "x" }, 400));
    setup({ contentMode: "image" });
    await selectAndSubmit(user);
    expect(await screen.findByText(/تعذّرت قراءة الملف كصورة JPG أو PNG/)).toBeInTheDocument();
  });
});
