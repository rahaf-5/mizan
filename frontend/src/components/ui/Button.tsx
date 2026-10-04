import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

const styles: Record<Variant, string> = {
  primary:
    "bg-[var(--color-brand)] text-[var(--color-on-brand)] hover:bg-[var(--color-brand-strong)] shadow-sm",
  secondary:
    "border border-[var(--color-border-strong)] bg-[var(--color-card)] text-[var(--color-ink)] hover:border-[var(--color-brand)] hover:text-[var(--color-brand)]",
  ghost: "text-[var(--color-brand)] hover:bg-[var(--color-brand-soft)]",
};

export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type={type}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-base font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${styles[variant]} ${className}`}
      {...props}
    />
  );
}
