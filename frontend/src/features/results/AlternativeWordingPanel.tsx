"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/Notice";
import { getDictionary } from "@/i18n";
import { requestAlternative } from "@/lib/verify/client";
import { explainResult } from "@/lib/verify/presentation";
import type { AlternativeWording } from "@/lib/verify/types";

const t = getDictionary().results.alternative;

/**
 * Alternative wording (spec §15). ONE request; the backend proposes a wording and re-verifies
 * it through the full pipeline. It is shown as trusted — and can be adopted — only when that
 * re-verification succeeded. An unverified proposal is never displayed as an answer.
 */
export function AlternativeWordingPanel({
  runId,
  claimId,
  onAdopt,
}: {
  runId: string;
  claimId: string;
  onAdopt: (alt: AlternativeWording) => void;
}) {
  const [state, setState] = useState<
    | { s: "idle" }
    | { s: "working" }
    | { s: "verified"; alt: AlternativeWording }
    | { s: "not_verified" }
    | { s: "error"; expired: boolean }
  >({ s: "idle" });

  const run = async () => {
    setState({ s: "working" });
    const res = await requestAlternative(runId, claimId);
    if (res.kind === "alternative") {
      const alt = res.result;
      setState(alt.verified && alt.proposed_text && alt.outcome ? { s: "verified", alt } : { s: "not_verified" });
    } else {
      setState({ s: "error", expired: res.kind === "input_error" && res.code === "result_not_found" });
    }
  };

  if (state.s === "idle") {
    return (
      <Button variant="secondary" onClick={() => void run()}>
        {t.action}
      </Button>
    );
  }
  if (state.s === "working") {
    return (
      <p role="status" className="text-sm text-[var(--color-muted)]">
        {t.working}
      </p>
    );
  }
  if (state.s === "verified") {
    return (
      <Notice tone="success" role="status" title={t.verified}>
        <p className="text-sm text-[var(--color-muted)]">{t.proposedLabel}</p>
        <blockquote dir="auto" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-3">
          {state.alt.proposed_text}
        </blockquote>
        {state.alt.outcome?.kind === "verification" && explainResult(state.alt.outcome).length ? (
          <div className="space-y-1 text-sm">
            <p className="font-bold">{t.whyLabel}</p>
            {explainResult(state.alt.outcome).map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
        ) : null}
        <Button onClick={() => onAdopt(state.alt)}>{t.adopt}</Button>
      </Notice>
    );
  }
  if (state.s === "not_verified") {
    return <Notice tone="warning" role="status" title={t.failed} />;
  }
  return <Notice tone="warning" role="alert" title={state.expired ? t.expired : t.error} />;
}
