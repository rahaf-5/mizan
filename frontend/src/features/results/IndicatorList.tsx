import type { Indicator } from "@/lib/verify/presentation";

const MARK = { true: "✓", false: "✗", null: "!" } as const;

/** Checks Mizan performed, as plain facts. The mark is decorative; the sentence carries the meaning. */
export function IndicatorList({ items, className = "" }: { items: Indicator[]; className?: string }) {
  if (!items.length) return null;
  return (
    <ul className={`space-y-1 ${className}`}>
      {items.map((it) => (
        <li key={it.text} className="flex gap-2" data-ok={String(it.ok)}>
          <span aria-hidden="true" className="w-4 shrink-0 text-center font-bold">
            {MARK[String(it.ok) as keyof typeof MARK]}
          </span>
          <span>{it.text}</span>
        </li>
      ))}
    </ul>
  );
}
