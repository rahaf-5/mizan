import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  CHECK_MODES,
  INPUT_TYPES,
  CLAIM_OUTCOME_KINDS,
  CLAIM_TYPES,
  EVIDENCE_RELATIONSHIPS,
  EXTRACTION_STATUSES,
  OUT_OF_SCOPE_REASONS,
  RESULT_GROUPS,
  TRUSTED_SOURCE_IDS,
  USER_CONFIRMATION_STATUSES,
  VERIFICATION_STATUSES,
} from "@/lib/domain";
import { CLAIM_EXTRACTION_MAX_INPUT_CHARS, CLAIM_MAX_CHARS, MAX_REVIEW_CLAIMS } from "@/lib/claims/types";

const snapshotPath = fileURLToPath(new URL("../../../contracts/domain-contracts.json", import.meta.url));
const snapshot = JSON.parse(readFileSync(snapshotPath, "utf-8")) as {
  enums: Record<string, string[]>;
  claimOutcomeKinds: string[];
  limits: { claimExtractionMaxInputChars: number; claimMaxChars: number; maxReviewClaims: number };
};

describe("frontend domain mirror matches the backend contract snapshot", () => {
  it.each([
    ["VerificationStatus", VERIFICATION_STATUSES],
    ["EvidenceRelationship", EVIDENCE_RELATIONSHIPS],
    ["ClaimType", CLAIM_TYPES],
    ["ExtractionStatus", EXTRACTION_STATUSES],
    ["UserConfirmationStatus", USER_CONFIRMATION_STATUSES],
    ["ResultGroup", RESULT_GROUPS],
    ["OutOfScopeReason", OUT_OF_SCOPE_REASONS],
    ["TrustedSourceId", TRUSTED_SOURCE_IDS],
    ["CheckMode", CHECK_MODES],
    ["InputType", INPUT_TYPES],
  ] as const)("%s", (name, values) => {
    expect([...values]).toEqual(snapshot.enums[name]);
  });

  it("MVP input is text only and the snapshot carries no OCR contracts", () => {
    expect([...INPUT_TYPES]).toEqual(["text"]);
    expect(Object.keys(snapshot.enums).filter((k) => k.toLowerCase().includes("ocr"))).toEqual([]);
    expect("ocr" in snapshot).toBe(false);
  });

  it("claim extraction / review limits", () => {
    expect(CLAIM_EXTRACTION_MAX_INPUT_CHARS).toBe(snapshot.limits.claimExtractionMaxInputChars);
    expect(CLAIM_MAX_CHARS).toBe(snapshot.limits.claimMaxChars);
    expect(MAX_REVIEW_CLAIMS).toBe(snapshot.limits.maxReviewClaims);
  });

  it("claim outcome kinds", () => {
    expect([...CLAIM_OUTCOME_KINDS]).toEqual(snapshot.claimOutcomeKinds);
  });
});

describe("approved Mizan states", () => {
  it("has exactly the six verification statuses", () => {
    expect(VERIFICATION_STATUSES).toHaveLength(6);
  });

  it("does not treat no_evidence_found as an evidence relationship", () => {
    expect(EVIDENCE_RELATIONSHIPS as readonly string[]).not.toContain("no_evidence_found");
  });

  it("keeps out_of_scope and system_error out of verification statuses", () => {
    const statuses = VERIFICATION_STATUSES as readonly string[];
    for (const v of ["out_of_scope", "system_error", "true", "false"]) {
      expect(statuses).not.toContain(v);
    }
  });
});
