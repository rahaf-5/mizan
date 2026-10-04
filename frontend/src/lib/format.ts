import { getDictionary } from "@/i18n";

const t = getDictionary();
const nf = new Intl.NumberFormat("ar", { maximumFractionDigits: 1 });

export const formatNumber = (n: number): string => nf.format(n);

export function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return t.fullContent.sizeMB(nf.format(bytes / (1024 * 1024)));
  return t.fullContent.sizeKB(nf.format(Math.max(bytes / 1024, 0.1)));
}
