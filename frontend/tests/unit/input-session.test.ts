import { describe, expect, it } from "vitest";
import { initialInputSession, inputSessionReducer } from "@/lib/input/session";
import {
  prepareContentText,
  prepareQuickCheckClaim,
  prepareReviewedOcrText,
} from "@/lib/input/submission";
import { makeExtraction } from "../helpers";

describe("prepared submissions mirror the backend ExtractionInput", () => {
  it("quick check keeps the claim exactly as entered", () => {
    const raw = "  قراءة سورة الكهف يوم الجمعة سبب في حصول نور بين الجمعتين.  ";
    const s = prepareQuickCheckClaim(raw);
    expect(s.kind).toBe("quick_check_claim");
    if (s.kind !== "quick_check_claim") throw new Error();
    expect(s.extractionInput).toEqual({
      mode: "quick_check",
      input_type: "text",
      text: raw,
      ocr_text_reviewed_by_user: false,
    });
    expect(s.next).toBe("claim_confirmation");
  });

  it("full content text goes to claim extraction", () => {
    const s = prepareContentText("نص");
    if (s.kind !== "full_content_text") throw new Error();
    expect(s.extractionInput.mode).toBe("full_content");
    expect(s.next).toBe("claim_extraction");
  });

  it("OCR-derived input uses the REVIEWED text and keeps the raw text separately", () => {
    const file = new File(["x"], "a.png", { type: "image/png" });
    const image = { file, name: "a.png", type: "image/png" as const, sizeBytes: 1 };
    const extraction = makeExtraction({ raw_text: "نص خام" });
    const s = prepareReviewedOcrText({ image, extraction, reviewedText: "نص مُراجَع" });
    if (s.kind !== "full_content_reviewed_ocr_text") throw new Error();
    expect(s.extractionInput).toEqual({
      mode: "full_content",
      input_type: "image",
      text: "نص مُراجَع",
      ocr_text_reviewed_by_user: true,
    });
    expect(s.ocr).toMatchObject({ rawText: "نص خام", editedByUser: true });
    expect(s.next).toBe("claim_extraction");
  });
});

describe("input session reducer", () => {
  it("moves a Quick Check draft into Full Content text mode", () => {
    let st = inputSessionReducer(initialInputSession, { type: "quickCheck/setText", text: "أ\nب" });
    st = inputSessionReducer({ ...st, contentMode: "image" }, { type: "quickCheck/moveToFullContent" });
    expect(st.contentText).toBe("أ\nب");
    expect(st.contentMode).toBe("text");
    expect(st.quickCheckText).toBe("أ\nب");
  });

  it("keeps drafts per mode when switching", () => {
    let st = inputSessionReducer(initialInputSession, { type: "content/setText", text: "نص" });
    st = inputSessionReducer(st, { type: "content/setMode", mode: "image" });
    st = inputSessionReducer(st, { type: "content/setMode", mode: "text" });
    expect(st.contentText).toBe("نص");
  });
});

describe("OCR session: raw vs reviewed", () => {
  const file = new File(["x"], "a.png", { type: "image/png" });
  const image = { file, name: "a.png", type: "image/png" as const, sizeBytes: 1 };

  it("edits never change the raw OCR output", () => {
    const extraction = makeExtraction({ raw_text: "نص  خام\n" });
    let st = inputSessionReducer(initialInputSession, { type: "ocr/received", image, extraction });
    expect(st.ocr?.reviewedText).toBe("نص  خام\n");
    st = inputSessionReducer(st, { type: "ocr/editReviewed", text: "نص مصحح" });
    expect(st.ocr?.reviewedText).toBe("نص مصحح");
    expect(st.ocr?.extraction.raw_text).toBe("نص  خام\n");
    expect(st.ocr?.extraction).toBe(extraction); // same, untouched object
    st = inputSessionReducer(st, { type: "ocr/restoreRaw" });
    expect(st.ocr?.reviewedText).toBe("نص  خام\n");
  });

  it("choosing a new image discards the previous OCR result", () => {
    let st = inputSessionReducer(initialInputSession, {
      type: "ocr/received",
      image,
      extraction: makeExtraction(),
    });
    st = inputSessionReducer(st, { type: "content/setImage", image: null });
    expect(st.ocr).toBeNull();
  });
});
