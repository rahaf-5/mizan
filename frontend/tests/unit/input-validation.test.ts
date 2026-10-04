import { describe, expect, it } from "vitest";
import {
  hasImageSignature,
  looksLikeMultipleClaims,
  validateContentText,
  validateImageFile,
  validateQuickCheck,
} from "@/lib/input/validation";

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

describe("image validation (JPG/PNG only)", () => {
  const f = (name: string, type: string, size = 10) => ({ name, type, size });

  it.each([
    ["a.png", "image/png", "image/png"],
    ["a.PNG", "image/png", "image/png"],
    ["a.jpg", "image/jpeg", "image/jpeg"],
    ["a.jpeg", "image/jpeg", "image/jpeg"],
    ["a.jpg", "", "image/jpeg"],
  ])("accepts %s (%s)", (name, type, expected) => {
    expect(validateImageFile(f(name, type))).toEqual({ ok: true, type: expected });
  });

  it.each([
    ["a.gif", "image/gif"],
    ["a.webp", "image/webp"],
    ["a.heic", "image/heic"],
    ["a.pdf", "application/pdf"],
    ["a.png", "image/jpeg"], // mismatch
    ["a.txt", ""],
    ["png", "image/png"], // no extension
  ])("rejects %s (%s)", (name, type) => {
    expect(validateImageFile(f(name, type))).toEqual({ ok: false, reason: "unsupported_type" });
  });

  it("rejects empty files", () => {
    expect(validateImageFile(f("a.png", "image/png", 0))).toEqual({ ok: false, reason: "empty_file" });
  });

  it("checks real file signatures", async () => {
    const png = new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])]);
    const jpg = new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xe0])]);
    const fake = new Blob(["not an image"]);
    expect(await hasImageSignature(png, "image/png")).toBe(true);
    expect(await hasImageSignature(jpg, "image/jpeg")).toBe(true);
    expect(await hasImageSignature(fake, "image/png")).toBe(false);
    expect(await hasImageSignature(png, "image/jpeg")).toBe(false);
  });
});
