import { BackendStatus } from "@/components/BackendStatus";
import { getDictionary } from "@/i18n";

const t = getDictionary();

export default function StatusPage() {
  return (
    <section aria-labelledby="status-title" className="space-y-6">
      <header className="space-y-1">
        <h1 id="status-title" className="text-3xl font-bold">
          {t.status.title}
        </h1>
        <p className="text-[var(--color-muted)]">{t.status.description}</p>
        <p className="text-sm text-[var(--color-muted)]">{t.status.note}</p>
      </header>
      <BackendStatus />
    </section>
  );
}
