// @vitest-environment jsdom
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OcrReview } from "@/features/ocr-review/OcrReview";
import { useInputSession } from "@/lib/input/InputSessionProvider";
import type { OcrExtraction } from "@/lib/ocr/types";
import { makeExtraction, pngFile, renderWithSession } from "../helpers";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const RAW = "قراءة سورة الكهف يوم الجمعة\nسبب في حصول نور بين الجمعتين.";

function Probe() {
  const { state } = useInputSession();
  return (
    <div data-testid="probe">
      {JSON.stringify({
        prepared: state.prepared,
        ocr: state.ocr ? { raw: state.ocr.extraction.raw_text, reviewed: state.ocr.reviewedText } : null,
        mode: state.contentMode,
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
  expect(fetchSpy).not.toHaveBeenCalled(); // review never calls extraction/verification
});

function setup(extraction: OcrExtraction | null = makeExtraction({ raw_text: RAW })) {
  const file = pngFile();
  const image = { file, name: file.name, type: "image/png" as const, sizeBytes: file.size };
  return renderWithSession(
    <>
      <OcrReview />
      <Probe />
    </>,
    extraction ? { image, contentMode: "image", ocr: { image, extraction, reviewedText: extraction.raw_text } } : {},
  );
}

const field = () => screen.getByRole("textbox", { name: "النص المستخرج" });

describe("Review Extracted Text", () => {
  it("shows the raw OCR text in an editable, labelled RTL text area", () => {
    setup();
    expect(field()).toHaveValue(RAW);
    expect(field()).not.toHaveAttribute("readonly");
    expect(screen.getByText("استُخرج النص من الصورة")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "تأكيد واستخراج الادعاءات" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "الصورة الأصلية" })).toBeInTheDocument();
  });

  it("never shows a numeric OCR confidence", () => {
    setup(makeExtraction({ raw_text: RAW, confidence: { page_confidence: 0.93, word_count: 9, low_confidence_threshold: 0.6, low_confidence_word_count: 0, low_confidence_words: [] } }));
    expect(document.body.textContent).not.toMatch(/0\.93|93\s*%|٩٣/);
  });

  it("keeps raw OCR unchanged while the user edits, and preserves the reviewed text exactly", async () => {
    const user = userEvent.setup();
    setup();
    await user.clear(field());
    const corrected = "  قراءة سورة الكهف يوم الجمعة سبب في حصول نور ما بين الجمعتين.  ";
    await user.type(field(), corrected);
    expect(probe().ocr).toEqual({ raw: RAW, reviewed: corrected });
    expect(screen.getByText("عدّلتَ النص المستخرج")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "تأكيد واستخراج الادعاءات" }));
    const { prepared } = probe();
    expect(prepared.kind).toBe("full_content_reviewed_ocr_text");
    expect(prepared.next).toBe("claim_extraction");
    expect(prepared.extractionInput).toEqual({
      mode: "full_content",
      input_type: "image",
      text: corrected,
      ocr_text_reviewed_by_user: true,
    });
    expect(prepared.ocr).toMatchObject({ rawText: RAW, editedByUser: true, ocrId: "ocr-test-1" });
    const done = screen.getAllByRole("status").find((s) => s.textContent?.includes("تم حفظ النص بعد مراجعتك"));
    expect(done).toHaveTextContent("لم يبدأ أي تحقق بعد");
  });

  it("can restore the text as extracted", async () => {
    const user = userEvent.setup();
    setup();
    await user.type(field(), " إضافة");
    await user.click(screen.getByRole("button", { name: "استعادة النص كما استُخرج" }));
    expect(field()).toHaveValue(RAW);
    expect(screen.queryByText("عدّلتَ النص المستخرج")).toBeNull();
  });

  it("does not continue with empty reviewed text", async () => {
    const user = userEvent.setup();
    setup();
    await user.clear(field());
    await user.click(screen.getByRole("button", { name: "تأكيد واستخراج الادعاءات" }));
    expect(screen.getByText("لا يمكن المتابعة بنص فارغ. صحّح النص أو ارفع صورة أخرى.")).toBeInTheDocument();
    expect(field()).toHaveFocus();
    expect(probe().prepared).toBeNull();
  });

  it("nothing is prepared for extraction before the user confirms", () => {
    setup();
    expect(probe().prepared).toBeNull();
  });

  it("partial OCR: explains, lists uncertain words, offers a clearer image, fabricates nothing", async () => {
    const user = userEvent.setup();
    setup(
      makeExtraction({
        raw_text: RAW,
        status: "completed_with_warnings",
        warnings: [{ code: "low_confidence_text", detail: "1 words" }, { code: "low_resolution_image", detail: null }],
        confidence: {
          page_confidence: 0.7,
          word_count: 9,
          low_confidence_threshold: 0.6,
          low_confidence_word_count: 1,
          low_confidence_words: [{ text: "الجمعتين", confidence: 0.3 }],
        },
      }),
    );
    const notice = screen.getByText("قد لا تكون بعض أجزاء النص قد قُرئت بشكل صحيح").closest("[role=alert]") as HTMLElement;
    expect(notice).toBeInTheDocument();
    expect(within(notice).getByText("الجمعتين")).toBeInTheDocument();
    expect(within(notice).getByText(/دقة الصورة منخفضة/)).toBeInTheDocument();
    expect(field()).toHaveValue(RAW); // exactly the raw text, nothing added
    await user.click(within(notice).getByRole("button", { name: "رفع صورة أوضح" }));
    expect(push).toHaveBeenCalledWith("/full-content");
    expect(probe().ocr).toBeNull();
    expect(probe().mode).toBe("image");
  });

  it("partial OCR can still continue with the user-reviewed text", async () => {
    const user = userEvent.setup();
    setup(makeExtraction({ raw_text: RAW, status: "completed_with_warnings", warnings: [{ code: "low_resolution_image", detail: null }] }));
    await user.click(screen.getByRole("button", { name: "تأكيد واستخراج الادعاءات" }));
    expect(probe().prepared.extractionInput.text).toBe(RAW);
  });

  it("empty OCR result: no text area, no confirm, clear replace/manual paths", async () => {
    const user = userEvent.setup();
    setup(makeExtraction({ raw_text: "", status: "no_text_found" }));
    expect(screen.getByText("لم يتمكن ميزان من قراءة نص في هذه الصورة")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button", { name: "تأكيد واستخراج الادعاءات" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "كتابة النص يدويًا" }));
    expect(push).toHaveBeenCalledWith("/full-content");
    expect(probe().mode).toBe("text");
  });

  it("empty OCR result: upload another image", async () => {
    const user = userEvent.setup();
    setup(makeExtraction({ raw_text: "  ", status: "no_text_found" }));
    await user.click(screen.getByRole("button", { name: "رفع صورة أخرى" }));
    expect(push).toHaveBeenCalledWith("/full-content");
    expect(probe().mode).toBe("image");
  });

  it("replace image goes back to upload", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: "تغيير الصورة" }));
    expect(push).toHaveBeenCalledWith("/full-content");
    expect(probe().ocr).toBeNull();
  });

  it("without an OCR result (e.g. after reload) points back to upload", () => {
    setup(null);
    expect(screen.getByText("لا توجد صورة لمراجعة نصها")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "الذهاب إلى رفع صورة" })).toHaveAttribute("href", "/full-content");
  });

  it("is keyboard operable: Tab reaches text area then confirm", async () => {
    const user = userEvent.setup();
    setup();
    field().focus();
    await user.keyboard("{End} نهاية");
    expect(probe().ocr.reviewed.endsWith(" نهاية")).toBe(true);
    await user.tab();
    // after editing, the restore button appears before the confirm button
    expect(screen.getByRole("button", { name: "استعادة النص كما استُخرج" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "تأكيد واستخراج الادعاءات" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(probe().prepared.kind).toBe("full_content_reviewed_ocr_text");
  });
});
