import { describe, expect, it } from "vitest";
import { initialInputSession, inputSessionReducer } from "@/lib/input/session";
import { prepareContentText, prepareQuickCheckClaim } from "@/lib/input/submission";

describe("prepared submissions mirror the backend ExtractionInput (text only)", () => {
  it("quick check keeps the claim exactly as entered", () => {
    const raw = "  قراءة سورة الكهف يوم الجمعة سبب في حصول نور بين الجمعتين.  ";
    const s = prepareQuickCheckClaim(raw);
    expect(s.kind).toBe("quick_check_claim");
    expect(s.extractionInput).toEqual({ mode: "quick_check", input_type: "text", text: raw });
    expect(s.next).toBe("claim_confirmation");
  });

  it("full content text goes to claim extraction", () => {
    const s = prepareContentText("نص");
    expect(s.kind).toBe("full_content_text");
    expect(s.extractionInput).toEqual({ mode: "full_content", input_type: "text", text: "نص" });
    expect(s.next).toBe("claim_extraction");
  });
});

describe("input session reducer", () => {
  it("has no image or OCR state", () => {
    expect(Object.keys(initialInputSession).sort()).toEqual(["contentText", "prepared", "quickCheckText"]);
  });

  it("moves a Quick Check draft into Full Content", () => {
    let st = inputSessionReducer(initialInputSession, { type: "quickCheck/setText", text: "أ\nب" });
    st = inputSessionReducer(st, { type: "quickCheck/moveToFullContent" });
    expect(st.contentText).toBe("أ\nب");
    expect(st.quickCheckText).toBe("أ\nب");
    expect(st.prepared).toBeNull();
  });

  it("keeps the full content draft independent of the quick check draft", () => {
    let st = inputSessionReducer(initialInputSession, { type: "content/setText", text: "نص" });
    st = inputSessionReducer(st, { type: "quickCheck/setText", text: "ادعاء" });
    expect(st.contentText).toBe("نص");
  });
});
