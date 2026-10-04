import { AlertIcon } from "@/components/icons";

/** Inline field error: icon + text, announced to assistive tech. */
export function FieldError({ id, message }: { id: string; message: string | null }) {
  return (
    <p id={id} role="alert" className="flex min-h-6 items-center gap-1.5 text-sm font-medium text-[var(--color-danger)]">
      {message ? (
        <>
          <AlertIcon className="size-4 shrink-0" />
          <span>{message}</span>
        </>
      ) : null}
    </p>
  );
}
