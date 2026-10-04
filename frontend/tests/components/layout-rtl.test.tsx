import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import RootLayout from "@/app/layout";
import HomePage from "@/app/page";

describe("root layout", () => {
  it("renders the Home page as Arabic RTL", () => {
    const html = renderToStaticMarkup(
      <RootLayout>
        <HomePage />
      </RootLayout>,
    );
    expect(html).toMatch(/^<html lang="ar" dir="rtl">/);
    expect(html).toContain("تحقّق قبل أن تنشر");
  });
});
