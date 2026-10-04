import { DocumentIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { FullContentInput } from "@/features/full-content/FullContentInput";
import { getDictionary } from "@/i18n";

const t = getDictionary();

export default function FullContentPage() {
  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title={t.fullContent.title}
        subtitle={t.fullContent.subtitle}
        icon={<DocumentIcon className="size-6" />}
      />
      <FullContentInput />
    </section>
  );
}
