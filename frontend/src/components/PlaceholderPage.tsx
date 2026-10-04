import Link from "next/link";
import { Card } from "@/components/Card";
import { getDictionary } from "@/i18n";

const t = getDictionary();

/** Shell placeholder for screens implemented in later tasks. */
export function PlaceholderPage({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <section aria-labelledby="page-title" className="space-y-6">
      <header className="space-y-1">
        <h1 id="page-title" className="text-3xl font-bold">
          {title}
        </h1>
        {subtitle ? <p className="text-[var(--color-muted)]">{subtitle}</p> : null}
      </header>
      <Card>
        <p>{t.placeholder.comingSoon}</p>
        <Link href="/" className="mt-4 inline-block text-[var(--color-brand)] underline underline-offset-4">
          {t.placeholder.backHome}
        </Link>
      </Card>
    </section>
  );
}
