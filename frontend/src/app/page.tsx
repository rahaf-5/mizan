import Link from "next/link";
import { getDictionary } from "@/i18n";

const t = getDictionary();

const actions = [
  { href: "/quick-check", icon: "⚡", title: t.home.quickCheckTitle, description: t.home.quickCheckDescription },
  { href: "/full-content", icon: "📄", title: t.home.fullContentTitle, description: t.home.fullContentDescription },
] as const;

/** Home shell. Full Home behaviour is implemented in Task 2. */
export default function HomePage() {
  return (
    <section aria-labelledby="home-title" className="space-y-10">
      <header className="space-y-3 text-center">
        <h1 id="home-title" className="text-4xl font-bold sm:text-5xl">
          <span aria-hidden="true">⚖️ </span>
          {t.brand.name}
        </h1>
        <p className="text-xl text-[var(--color-muted)]">{t.brand.tagline}</p>
      </header>

      <ul className="grid gap-4 sm:grid-cols-2">
        {actions.map((a) => (
          <li key={a.href}>
            <Link
              href={a.href}
              className="block h-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 shadow-sm transition hover:border-[var(--color-brand)] hover:shadow-md"
            >
              <span aria-hidden="true" className="text-3xl">
                {a.icon}
              </span>
              <h2 className="mt-3 text-2xl font-bold">{a.title}</h2>
              <p className="mt-1 text-[var(--color-muted)]">{a.description}</p>
            </Link>
          </li>
        ))}
      </ul>

      <p className="text-center text-sm text-[var(--color-muted)]">{t.home.principle}</p>
    </section>
  );
}
