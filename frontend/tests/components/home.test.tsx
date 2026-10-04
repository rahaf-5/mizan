// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "@/app/page";
import { AppShell } from "@/components/AppShell";

describe("Home", () => {
  it("shows brand, tagline, description and the disclaimer", () => {
    render(
      <AppShell>
        <HomePage />
      </AppShell>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "ميزان" })).toBeInTheDocument();
    expect(screen.getAllByText("تحقّق قبل أن تنشر").length).toBeGreaterThan(0);
    expect(screen.getByText(/يساعدك ميزان على التحقق من الادعاءات الدينية/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(
      "ميزان أداة مساعدة للتحقق من المحتوى، ولا يُعد بديلًا عن الرجوع لأهل العلم عند الحاجة.",
    );
  });

  it("offers exactly two primary paths that link to the right screens", () => {
    render(<HomePage />);
    const paths = screen.getByRole("region", { name: "اختر طريقة الفحص" });
    const links = within(paths).getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(within(paths).getByRole("link", { name: /فحص سريع/ })).toHaveAttribute("href", "/quick-check");
    expect(within(paths).getByRole("link", { name: /فحص محتوى كامل/ })).toHaveAttribute(
      "href",
      "/full-content",
    );
    expect(links[0]).toHaveAccessibleName(/ادعاء ديني واحد/);
    expect(links[1]).toHaveAccessibleName(/نص ديني، ثم مراجعة الادعاءات قبل التحقق/);
    expect(document.body.textContent).not.toMatch(/صورة/);
  });

  it("has no statistics, dashboards or extra primary actions", () => {
    render(<HomePage />);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("shell has skip link, labelled navigation and main landmark", () => {
    render(
      <AppShell>
        <HomePage />
      </AppShell>,
    );
    expect(screen.getByRole("link", { name: "تخطَّ إلى المحتوى الرئيسي" })).toHaveAttribute("href", "#main");
    expect(screen.getByRole("navigation", { name: "التنقل الرئيسي" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
  });
});
