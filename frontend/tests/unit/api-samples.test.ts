/**
 * Contract check against REAL backend responses: `contracts/api-samples.json` is produced by
 * the actual FastAPI app (backend/tests/test_api_samples.py). Every field path the UI's typed
 * fixtures use must exist in those responses, so the frontend never reads a field the API
 * does not send.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { AlternativeWording, FinalUserResult } from "@/lib/verify/types";
import {
  conflicting,
  contradicted,
  finalResult,
  hadithUnavailable,
  noEvidence,
  outOfScope,
  supported,
  systemError,
} from "../fixtures/outcomes";

type Json = unknown;
const samples = JSON.parse(
  readFileSync(fileURLToPath(new URL("../../../contracts/api-samples.json", import.meta.url)), "utf-8"),
) as Record<string, Json>;

function shape(value: Json, prefix = "", out = new Set<string>()): Set<string> {
  if (Array.isArray(value)) value.forEach((v) => shape(v, `${prefix}[]`, out));
  else if (value && typeof value === "object")
    for (const [k, v] of Object.entries(value)) {
      const path = prefix ? `${prefix}.${k}` : k;
      out.add(path);
      shape(v, path, out);
    }
  return out;
}

/** Union of key paths per outcome kind across all real samples. */
function realByKind(): Map<string, Set<string>> {
  const byKind = new Map<string, Set<string>>();
  const add = (o: { kind: string }) => {
    const set = byKind.get(o.kind) ?? new Set<string>();
    shape(o).forEach((p) => set.add(p));
    byKind.set(o.kind, set);
  };
  for (const [name, s] of Object.entries(samples)) {
    if (name.startsWith("verify_")) (s as FinalUserResult).outcomes.forEach(add);
    else if ((s as AlternativeWording).outcome) add((s as AlternativeWording).outcome!);
  }
  return byKind;
}

describe("frontend contracts match real API responses", () => {
  const real = realByKind();

  it.each([
    ["verification", [contradicted(), supported("s", "أ"), conflicting, noEvidence]],
    ["required_source_unavailable", [hadithUnavailable]],
    ["out_of_scope", [outOfScope]],
    ["system_error", [systemError]],
  ] as const)("%s outcome fields exist in the real response", (kind, fixtures) => {
    const realPaths = real.get(kind)!;
    expect(realPaths, `no real sample of kind ${kind}`).toBeDefined();
    const used = new Set<string>();
    fixtures.forEach((f) => shape(f, "", used));
    // metadata is a provider-specific bag; only the keys the UI reads are checked below.
    const missing = [...used].filter((p) => !p.includes(".metadata.") && !realPaths.has(p));
    expect(missing).toEqual([]);
  });

  it("evidence metadata keys the UI reads are real", () => {
    const paths = real.get("verification")!;
    expect(paths.has("evidence[].metadata.provider_author")).toBe(true);
    expect(paths.has("evidence[].metadata.surah_number")).toBe(true);
  });

  it("FinalUserResult and AlternativeWording envelopes", () => {
    const envelope = shape(samples.verify_contradicted_quran);
    for (const p of shape({ ...finalResult(outOfScope), outcomes: [] })) expect(envelope.has(p), p).toBe(true);
    const alt = samples.alternative_verified as AlternativeWording;
    for (const k of ["kind", "original_claim_id", "run_id", "proposed_text", "verified", "outcome"] as const)
      expect(alt).toHaveProperty(k);
    expect(alt.kind).toBe("alternative_wording");
  });

  it("real samples carry the new presentation fields", () => {
    const o = (samples.verify_contradicted_quran as FinalUserResult).outcomes[0];
    expect(o.kind === "verification" && o.verified_reference).toBeTruthy();
    const lim = samples.verify_supported_tafsir_with_limitation as FinalUserResult;
    expect(lim.limitations.length).toBeGreaterThan(0);
  });
});
