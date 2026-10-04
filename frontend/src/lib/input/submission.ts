/** Builders for prepared submissions. They preserve the user's text exactly. */
import type { PreparedSubmission } from "./types";

const now = () => new Date().toISOString();

export function prepareQuickCheckClaim(text: string): PreparedSubmission {
  return {
    kind: "quick_check_claim",
    preparedAt: now(),
    next: "claim_confirmation",
    extractionInput: {
      mode: "quick_check",
      input_type: "text",
      text,
    },
  };
}
