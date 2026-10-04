import { describe, expect, it } from "vitest";
import { initialInputSession, inputSessionReducer } from "@/lib/input/session";
import {
  prepareContentImage,
  prepareContentText,
  prepareQuickCheckClaim,
} from "@/lib/input/submission";

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

  it("image submission carries no text and waits for OCR", () => {
    const file = new File(["x"], "a.png", { type: "image/png" });
    const s = prepareContentImage({ file, name: "a.png", type: "image/png", sizeBytes: 1 });
    expect(s.next).toBe("ocr");
    expect("extractionInput" in s).toBe(false);
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
