"use client";

import { useRef, type KeyboardEvent } from "react";
import { ImageIcon, TextIcon } from "@/components/icons";
import { getDictionary } from "@/i18n";
import type { ContentMode } from "@/lib/input/types";

const t = getDictionary();

export const MODES: { mode: ContentMode; label: string; icon: React.ReactNode }[] = [
  { mode: "text", label: t.fullContent.modeText, icon: <TextIcon className="size-5" /> },
  { mode: "image", label: t.fullContent.modeImage, icon: <ImageIcon className="size-5" /> },
];

export const tabId = (mode: ContentMode) => `content-tab-${mode}`;
export const panelId = (mode: ContentMode) => `content-panel-${mode}`;

/** Accessible tablist (WAI-ARIA tabs, RTL-aware arrow keys). */
export function ModeTabs({
  value,
  onChange,
}: {
  value: ContentMode;
  onChange: (mode: ContentMode) => void;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const onKeyDown = (e: KeyboardEvent) => {
    const idx = MODES.findIndex((m) => m.mode === value);
    let next = idx;
    // In RTL, ArrowLeft moves forward (to the next tab on the left).
    if (e.key === "ArrowLeft") next = (idx + 1) % MODES.length;
    else if (e.key === "ArrowRight") next = (idx - 1 + MODES.length) % MODES.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = MODES.length - 1;
    else return;
    e.preventDefault();
    const mode = MODES[next].mode;
    onChange(mode);
    refs.current[mode]?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label={t.fullContent.modeLabel}
      onKeyDown={onKeyDown}
      className="inline-flex w-full gap-1 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-1 sm:w-auto"
    >
      {MODES.map((m) => {
        const selected = m.mode === value;
        return (
          <button
            key={m.mode}
            ref={(el) => {
              refs.current[m.mode] = el;
            }}
            type="button"
            role="tab"
            id={tabId(m.mode)}
            aria-selected={selected}
            aria-controls={panelId(m.mode)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(m.mode)}
            className={`inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl px-6 py-2 font-medium transition-colors sm:flex-none ${
              selected
                ? "bg-[var(--color-brand)] text-[var(--color-on-brand)] shadow-sm"
                : "text-[var(--color-ink)] hover:bg-[var(--color-brand-soft)]"
            }`}
          >
            {m.icon}
            {m.label}
          </button>
        );
      })}
    </div>
  );
}
