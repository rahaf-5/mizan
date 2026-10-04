import { DocumentIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { ClaimReview } from "@/features/claim-review/ClaimReview";
import { getDictionary } from "@/i18n";

const t = getDictionary();

export default function ClaimReviewPage() {
  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-3xl space-y-6">
      <PageHeader title={t.claimReview.title} subtitle={t.claimReview.subtitle} icon={<DocumentIcon className="size-6" />} />
      <ClaimReview />
    </section>
  );
}
