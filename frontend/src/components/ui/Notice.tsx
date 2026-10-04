import { AlertIcon, CheckCircleIcon, InfoIcon } from "@/components/icons";

type Tone = "info" | "warning" | "success";

const toneStyles: Record<Tone, string> = {
  info: "border-[var(--color-info-border)] bg-[var(--color-info-soft)]",
  warning: "border-[var(--color-warning-border)] bg-[var(--color-warning-soft)]",
  success: "border-[var(--color-success-border)] bg-[var(--color-success-soft)]",
};

const toneIcon: Record<Tone, React.ReactNode> = {
  info: <InfoIcon className="size-6 shrink-0" />,
  warning: <AlertIcon className="size-6 shrink-0" />,
  success: <CheckCircleIcon className="size-6 shrink-0" />,
};

/**
 * Message panel. Meaning never relies on color alone: every notice has an
 * icon shape and an explicit text title.
 */
export function Notice({
  tone,
  title,
  children,
  role,
  id,
  className = "",
}: {
  tone: Tone;
  title: string;
  children?: React.ReactNode;
  role?: "status" | "alert";
  id?: string;
  className?: string;
}) {
  return (
    <div
      id={id}
      role={role}
      data-tone={tone}
      className={`flex gap-3 rounded-2xl border p-4 text-[var(--color-ink)] sm:p-5 ${toneStyles[tone]} ${className}`}
    >
      {toneIcon[tone]}
      <div className="min-w-0 flex-1 space-y-2">
        <p className="font-bold">{title}</p>
        {children}
      </div>
    </div>
  );
}
