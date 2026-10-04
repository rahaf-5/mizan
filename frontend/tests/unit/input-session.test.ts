import { describe, expect, it } from "vitest";
import { initialInputSession, inputSessionReducer } from "@/lib/input/session";
import { buildConfirmPayload, fromExtracted, manualClaim } from "@/lib/claims/review";
import { prepareQuickCheckClaim } from "@/lib/input/submission";

describe("prepared submissions mirror the backend ExtractionInput (text only)", () => {
  it("quick check keeps the claim exactly as entered", () => {
    const raw = "  قراءة سورة الكهف يوم الجمعة سبب في حصول نور بين الجمعتين.  ";
    const s = prepareQuickCheckClaim(raw);
    expect(s.kind).toBe("quick_check_claim");
    expect(s.extractionInput).toEqual({ mode: "quick_check", input_type: "text", text: raw });
    expect(s.next).toBe("claim_confirmation");
  });
});

describe("input session reducer", () => {
  it("has no image or OCR state", () => {
    expect(Object.keys(initialInputSession).sort()).toEqual([
      "confirmation",
      "contentText",
      "prepared",
      "quickCheckText",
      "review",
    ]);
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

describe("claim review state", () => {
  const extracted = fromExtracted([
    {
      claim_id: "a",
      original_text: "x",
      extracted_claim_text: "ادعاء أ",
      extraction_status: "clear",
      provided_evidence: null,
      provided_reference: null,
      user_confirmation_status: "pending",
    },
  ]);

  it("edits change only the current text, never the extracted text", () => {
    let st = inputSessionReducer(initialInputSession, { type: "review/start", sourceText: "x", claims: extracted });
    st = inputSessionReducer(st, { type: "review/edit", id: "a", text: "ادعاء معدل" });
    expect(st.review?.claims[0]).toMatchObject({ text: "ادعاء معدل", extractedText: "ادعاء أ" });
  });

  it("any review change clears a previous confirmation", () => {
    let st = inputSessionReducer(initialInputSession, { type: "review/start", sourceText: "x", claims: extracted });
    st = inputSessionReducer(st, { type: "confirmation/set", result: { confirmedClaims: [], nextStage: "claim_classification" } });
    st = inputSessionReducer(st, { type: "review/toggle", id: "a" });
    expect(st.confirmation).toBeNull();
  });

  it("confirm payload is explicit, excludes deleted claims and carries edited text", () => {
    let st = inputSessionReducer(initialInputSession, { type: "review/start", sourceText: "x", claims: extracted });
    st = inputSessionReducer(st, { type: "review/add", claim: manualClaim("يدوي") });
    st = inputSessionReducer(st, { type: "review/edit", id: "a", text: "معدل" });
    const manualId = st.review!.claims[1].id;
    st = inputSessionReducer(st, { type: "review/delete", id: manualId });
    const payload = buildConfirmPayload(st.review!);
    expect(payload.explicit_user_confirmation).toBe(true);
    expect(payload.claims).toHaveLength(1);
    expect(payload.claims[0]).toMatchObject({ claim_id: "a", text: "معدل", extracted_claim_text: "ادعاء أ" });
  });

  it("re-extraction replaces the review but keeps the source text", () => {
    let st = inputSessionReducer(initialInputSession, { type: "content/setText", text: "نص" });
    st = inputSessionReducer(st, { type: "review/start", sourceText: "نص", claims: [] });
    expect(st.contentText).toBe("نص");
    expect(st.review).toEqual({ sourceText: "نص", claims: [] });
  });
});
