import { PlaceholderPage } from "@/components/PlaceholderPage";
import { getDictionary } from "@/i18n";

const t = getDictionary();

export default function FullContentPage() {
  return <PlaceholderPage title={t.home.fullContentTitle} subtitle={t.home.fullContentDescription} />;
}
