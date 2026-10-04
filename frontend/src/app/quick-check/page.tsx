import { PlaceholderPage } from "@/components/PlaceholderPage";
import { getDictionary } from "@/i18n";

const t = getDictionary();

export default function QuickCheckPage() {
  return <PlaceholderPage title={t.home.quickCheckTitle} subtitle={t.home.quickCheckDescription} />;
}
