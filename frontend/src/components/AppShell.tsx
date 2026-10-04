import Link from "next/link";
import { getDictionary } from "@/i18n";

const t = getDictionary();

const navItems = [
  { href: "/", label: t.nav.home },
  { href: "/quick-check", label: t.nav.quickCheck },
  { href: "/full-content", label: t.nav.fullContent },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-[var(--color-card)] focus:px-4 focus:py-2 focus:shadow"
      >
        {t.a11y.skipToContent}
      </a>

      <header className="border-b border-[var(--color-border)] bg-[var(--color-card)]">
        <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-baseline gap-2 no-underline">
            <span aria-hidden="true" className="text-2xl">
              ⚖️
            </span>
            <span className="text-2xl font-bold text-[var(--color-brand)]">{t.brand.name}</span>
            <span className="hidden text-sm text-[var(--color-muted)] sm:inline">
              {t.brand.tagline}
            </span>
          </Link>
          <nav aria-label={t.a11y.mainNav}>
            <ul className="flex flex-wrap gap-1 text-sm sm:gap-2">
              {navItems.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className="block rounded-lg px-3 py-2 text-[var(--color-ink)] hover:bg-[var(--color-brand-soft)]"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
        {children}
      </main>

      <footer className="border-t border-[var(--color-border)] bg-[var(--color-card)]">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-2 px-4 py-5 text-sm text-[var(--color-muted)] sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p role="note">{t.disclaimer}</p>
          <Link href="/status" className="shrink-0 underline-offset-4 hover:underline">
            {t.nav.status}
          </Link>
        </div>
      </footer>
    </div>
  );
}
