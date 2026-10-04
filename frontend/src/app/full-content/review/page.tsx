import { DocumentIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { OcrReview } from "@/features/ocr-review/OcrReview";
import { getDictionary } from "@/i18n";

const t = getDictionary();

export default function OcrReviewPage() {
  return (
    <section aria-labelledby="page-title" className="space-y-6">
      <PageHeader title={t.ocrReview.title} subtitle={t.ocrReview.subtitle} icon={<DocumentIcon className="size-6" />} />
      <OcrReview />
    </section>
  );
}
