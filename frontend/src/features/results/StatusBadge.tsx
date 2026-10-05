import { AlertIcon, CheckCircleIcon, InfoIcon } from "@/components/icons";
import { getDictionary } from "@/i18n";

const t = getDictionary();

export type BadgeKind = keyof typeof t.results.status;

const tone: Record<BadgeKind, { cls: string; icon: React.ReactNode }> = {
  supported: { cls: "border-[var(--color-success-border)] bg-[var(--color-success-soft)]", icon: <CheckCircleIcon className="size-4" /> },
  partially_supported: { cls: "border-[var(--color-warning-border)] bg-[var(--color-warning-soft)]", icon: <AlertIcon className="size-4" /> },
  contradicted: { cls: "border-[var(--color-danger)] bg-[var(--color-warning-soft)] text-[var(--color-danger)]", icon: <AlertIcon className="size-4" /> },
  conflicting_evidence: { cls: "border-[var(--color-warning-border)] bg-[var(--color-warning-soft)]", icon: <AlertIcon className="size-4" /> },
  insufficient_evidence: { cls: "border-[var(--color-info-border)] bg-[var(--color-info-soft)]", icon: <InfoIcon className="size-4" /> },
  no_evidence_found: { cls: "border-[var(--color-info-border)] bg-[var(--color-info-soft)]", icon: <InfoIcon className="size-4" /> },
  required_source_unavailable: { cls: "border-[var(--color-info-border)] bg-[var(--color-info-soft)]", icon: <InfoIcon className="size-4" /> },
  out_of_scope: { cls: "border-[var(--color-info-border)] bg-[var(--color-info-soft)]", icon: <InfoIcon className="size-4" /> },
  system_error: { cls: "border-[var(--color-border-strong)] bg-[var(--color-surface)]", icon: <AlertIcon className="size-4" /> },
};

/** Status label: icon shape + text, never color alone (spec §14, §18). */
export function StatusBadge({ kind }: { kind: BadgeKind }) {
  return (
    <span
      data-status={kind}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-bold ${tone[kind].cls}`}
    >
      {tone[kind].icon}
      {t.results.status[kind]}
    </span>
  );
}
