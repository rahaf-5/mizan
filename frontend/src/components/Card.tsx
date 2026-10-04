export function Card({
  children,
  className = "",
  as: Tag = "div",
}: {
  children: React.ReactNode;
  className?: string;
  as?: "div" | "section" | "article";
}) {
  return (
    <Tag
      className={`rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm sm:p-6 ${className}`}
    >
      {children}
    </Tag>
  );
}
