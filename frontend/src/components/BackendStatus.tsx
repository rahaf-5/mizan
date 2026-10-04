"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { getHealth, type ComponentStatus, type HealthReport } from "@/lib/api";
import { getDictionary } from "@/i18n";

const t = getDictionary();

type State =
  | { kind: "loading" }
  | { kind: "ok"; report: HealthReport }
  | { kind: "error"; message: string };

function Row({ label, value }: { label: string; value: ComponentStatus }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 py-2">
      <dt className="text-[var(--color-muted)]">{label}</dt>
      <dd dir="ltr" className="font-mono text-sm">
        {value.status}
        {value.detail ? ` (${value.detail})` : ""}
      </dd>
    </div>
  );
}

/** Technical connectivity check (frontend -> backend). Not a verification result. */
export function BackendStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  // Bumping `attempt` triggers a (re)check. setState runs only in async callbacks.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getHealth().then(
      (report) => {
        if (!cancelled) setState({ kind: "ok", report });
      },
      (err: unknown) => {
        if (!cancelled) {
          setState({ kind: "error", message: err instanceof Error ? err.message : String(err) });
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = () => {
    setState({ kind: "loading" });
    setAttempt((n) => n + 1);
  };

  return (
    <Card as="section" className="space-y-4">
      <div aria-live="polite" className="space-y-1">
        {state.kind === "loading" && <p>{t.status.checking}</p>}
        {state.kind === "error" && (
          <p className="font-medium">
            <span aria-hidden="true">✕ </span>
            {t.status.backendUnreachable}
            <span dir="ltr" className="ms-2 font-mono text-sm text-[var(--color-muted)]">
              {state.message}
            </span>
          </p>
        )}
        {state.kind === "ok" && (
          <>
            <p className="font-medium">
              <span aria-hidden="true">✓ </span>
              {t.status.backendReachable} —{" "}
              {state.report.status === "ok" ? t.status.overallOk : t.status.overallDegraded}
            </p>
            {state.report.config_loaded && (
              <p className="text-sm text-[var(--color-muted)]">
                <span aria-hidden="true">✓ </span>
                {t.status.configLoaded}
                <span dir="ltr" className="ms-2 font-mono">
                  {state.report.environment} · v{state.report.version}
                </span>
              </p>
            )}
          </>
        )}
      </div>

      {state.kind === "ok" && (
        <dl className="divide-y divide-[var(--color-border)]">
          <Row label={t.status.database} value={state.report.database} />
          <Row label={t.status.llmProvider} value={state.report.llm_provider} />
          <Row label={t.status.ocr} value={state.report.ocr} />
          {Object.entries(state.report.trusted_sources).map(([name, value]) => (
            <Row key={name} label={`${t.status.trustedSources}: ${name}`} value={value} />
          ))}
        </dl>
      )}

      <button
        type="button"
        onClick={retry}
        className="rounded-lg bg-[var(--color-brand)] px-4 py-2 font-medium text-white hover:bg-[var(--color-brand-strong)] dark:text-[var(--color-surface)]"
      >
        {t.status.retry}
      </button>
    </Card>
  );
}
