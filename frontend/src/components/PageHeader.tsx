import Link from "next/link";
import { BackArrowIcon } from "@/components/icons";
import { getDictionary } from "@/i18n";

const t = getDictionary();

export function PageHeader({
  title,
  subtitle,
  icon,
}: {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
}) {
  return (
    <header className="space-y-4">
      <nav aria-label={t.a11y.breadcrumb}>
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-[var(--color-muted)] hover:text-[var(--color-brand)]"
        >
          <BackArrowIcon className="size-4" />
          {t.nav.home}
        </Link>
      </nav>
      <div className="flex items-start gap-3">
        {icon ? (
          <span className="mt-1 grid size-11 shrink-0 place-items-center rounded-xl bg-[var(--color-brand-soft)] text-[var(--color-brand)]">
            {icon}
          </span>
        ) : null}
        <div className="space-y-1">
          <h1 id="page-title" className="text-3xl font-bold sm:text-4xl">
            {title}
          </h1>
          {subtitle ? <p className="text-lg text-[var(--color-muted)]">{subtitle}</p> : null}
        </div>
      </div>
    </header>
  );
}
