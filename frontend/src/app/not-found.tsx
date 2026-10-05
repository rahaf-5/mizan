import Link from "next/link";
import { Card } from "@/components/Card";
import { getDictionary } from "@/i18n";

const t = getDictionary().notFound;

export default function NotFound() {
  return (
    <section aria-labelledby="page-title" className="space-y-6">
      <h1 id="page-title" className="text-3xl font-bold">
        {t.title}
      </h1>
      <Card>
        <p>{t.body}</p>
        <Link href="/" className="mt-4 inline-block text-[var(--color-brand)] underline underline-offset-4">
          {t.backHome}
        </Link>
      </Card>
    </section>
  );
}
