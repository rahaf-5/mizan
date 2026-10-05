import { DocumentIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { FullContentResults } from "@/features/results/FullContentResults";
import { getDictionary } from "@/i18n";

const t = getDictionary();

export default function FullContentResultsPage() {
  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-3xl space-y-6">
      <PageHeader title={t.results.fullTitle} subtitle={t.results.fullSubtitle} icon={<DocumentIcon className="size-6" />} />
      <FullContentResults />
    </section>
  );
}
