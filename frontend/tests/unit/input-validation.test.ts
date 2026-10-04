import { describe, expect, it } from "vitest";
import { looksLikeMultipleClaims, validateContentText, validateQuickCheck } from "@/lib/input/validation";

const SINGLE = "قراءة سورة الكهف يوم الجمعة سبب في حصول نور بين الجمعتين.";

describe("Quick Check validation", () => {
  it.each(["", "   ", "\n\t "])("rejects empty input %#", (v) => {
    expect(validateQuickCheck(v)).toEqual({ status: "empty" });
  });

  it("accepts a single claim", () => {
    expect(validateQuickCheck(SINGLE)).toEqual({ status: "ok" });
    expect(validateQuickCheck("الصلاة عماد الدين")).toEqual({ status: "ok" });
  });

  it("suggests Full Content for several sentences", () => {
    expect(looksLikeMultipleClaims(`${SINGLE} صيام يوم عرفة يكفّر ذنوب سنتين.`)).toBe(true);
    expect(looksLikeMultipleClaims("هل هذا صحيح؟ الصلاة عماد الدين كما يقال")).toBe(true);
  });

  it("does not guess claims inside one sentence (that is Claim Extraction's job)", () => {
    const joined = "قراءة سورة الكهف يوم الجمعة سنة وصيام يوم عرفة يكفّر ذنوب سنتين";
    expect(validateQuickCheck(joined)).toEqual({ status: "ok" });
  });

  it("suggests Full Content for multiple lines", () => {
    expect(validateQuickCheck(`${SINGLE}\nصيام يوم عرفة يكفّر ذنوب سنتين`)).toEqual({
      status: "multiple_claims_suspected",
    });
  });

  it("suggests Full Content for a long paragraph", () => {
    const paragraph = Array.from({ length: 70 }, () => "كلمة").join(" ");
    expect(validateQuickCheck(paragraph).status).toBe("multiple_claims_suspected");
  });

  it("does not treat a short trailing fragment as a second claim", () => {
    expect(looksLikeMultipleClaims(`${SINGLE} حقًا.`)).toBe(false);
  });
});

describe("Full Content text validation", () => {
  it("requires non-blank text", () => {
    expect(validateContentText("  ")).toEqual({ status: "empty" });
    expect(validateContentText(SINGLE)).toEqual({ status: "ok" });
  });
});
