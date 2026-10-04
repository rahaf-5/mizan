import { BoltIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { QuickCheckForm } from "@/features/quick-check/QuickCheckForm";
import { getDictionary } from "@/i18n";

const t = getDictionary();

export default function QuickCheckPage() {
  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-3xl space-y-6">
      <PageHeader title={t.quickCheck.title} subtitle={t.quickCheck.subtitle} icon={<BoltIcon className="size-6" />} />
      <QuickCheckForm />
    </section>
  );
}
