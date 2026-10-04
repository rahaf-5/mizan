import { PlaceholderPage } from "@/components/PlaceholderPage";
import { getDictionary } from "@/i18n";

export default function NotFound() {
  return <PlaceholderPage title={getDictionary().notFound.title} />;
}
