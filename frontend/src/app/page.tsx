import Link from "next/link";
import { GeometricPattern } from "@/components/GeometricPattern";
import { BoltIcon, DocumentIcon, ForwardArrowIcon, ScalesIcon } from "@/components/icons";
import { getDictionary } from "@/i18n";

const t = getDictionary();

const paths = [
  {
    href: "/quick-check",
    icon: <BoltIcon className="size-6" />,
    title: t.home.quickCheckTitle,
    description: t.home.quickCheckDescription,
  },
  {
    href: "/full-content",
    icon: <DocumentIcon className="size-6" />,
    title: t.home.fullContentTitle,
    description: t.home.fullContentDescription,
  },
] as const;

export default function HomePage() {
  return (
    <div className="space-y-10 sm:space-y-12">
      <section aria-labelledby="home-title" className="relative isolate overflow-hidden rounded-3xl px-2 py-6 text-center sm:py-10">
        <GeometricPattern className="absolute inset-0 -z-10 text-[var(--color-brand)] opacity-[0.07]" />
        <span className="mx-auto mb-4 grid size-16 place-items-center rounded-2xl bg-[var(--color-brand)] text-[var(--color-on-brand)] shadow-sm">
          <ScalesIcon className="size-9" />
        </span>
        <h1 id="home-title" className="text-5xl font-bold tracking-tight sm:text-6xl">
          {t.brand.name}
        </h1>
        <p className="mt-3 text-2xl font-medium text-[var(--color-brand)]">{t.brand.tagline}</p>
        <p className="mx-auto mt-4 max-w-xl text-lg text-[var(--color-muted)]">{t.home.description}</p>
      </section>

      <section aria-labelledby="paths-title">
        <h2 id="paths-title" className="sr-only">
          {t.home.pathsLabel}
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2 sm:gap-5">
          {paths.map((p) => (
            <li key={p.href}>
              <Link
                href={p.href}
                className="group flex h-full flex-col gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 shadow-sm transition hover:-translate-y-0.5 hover:border-[var(--color-brand)] hover:shadow-md sm:p-7"
              >
                <span className="grid size-12 place-items-center rounded-xl bg-[var(--color-brand-soft)] text-[var(--color-brand)]">
                  {p.icon}
                </span>
                <span className="text-2xl font-bold">{p.title}</span>
                <span className="text-[var(--color-muted)]">{p.description}</span>
                <span aria-hidden="true" className="mt-auto inline-flex items-center gap-1.5 pt-2 font-medium text-[var(--color-brand)]">
                  {t.home.start}
                  <ForwardArrowIcon className="size-4 transition group-hover:-translate-x-1" />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
