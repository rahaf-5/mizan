import { describe, expect, it } from "vitest";
import { defaultLocale, getDictionary, localeConfig } from "@/i18n";

describe("Arabic-first RTL foundation", () => {
  it("defaults to Arabic RTL", () => {
    expect(defaultLocale).toBe("ar");
    expect(localeConfig.ar).toEqual({ dir: "rtl", lang: "ar" });
  });

  it("uses the approved brand copy and disclaimer", () => {
    const t = getDictionary();
    expect(t.brand.name).toBe("ميزان");
    expect(t.brand.tagline).toBe("تحقّق قبل أن تنشر");
    expect(t.disclaimer).toBe(
      "ميزان أداة مساعدة للتحقق من المحتوى، ولا يُعد بديلًا عن الرجوع لأهل العلم عند الحاجة.",
    );
  });
});
