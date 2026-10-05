/**
 * Mizan evaluation runner — calls the REAL HTTP API exactly like the frontend does
 * (POST /api/v1/claims/extract → /claims/confirm → /verify), one request at a time.
 *
 * Node 18+:  node evaluation/run_eval.mjs [baseUrl] > evaluation/results/raw.json
 * Browser:   paste into a page served by the backend origin and call runEvaluation({...}).
 *
 * It records compact, checkable facts per run (status, components, relationships, evidence
 * records, integrity checks). It never judges correctness — scoring is done by score_eval.py.
 * External provider failures (rate limit, timeout, network) are recorded as such.
 */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const PROVIDER_CODES = new Set(["llm_rate_limited", "llm_timeout", "llm_provider_error", "llm_auth_failed", "llm_not_configured", "network_error"]);

async function sha256(text) {
  const data = new TextEncoder().encode(text);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function post(base, path, body) {
  const t0 = Date.now();
  try {
    const r = await fetch(base + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    let json = null;
    try { json = await r.json(); } catch { json = null; }
    return { http: r.status, body: json, ms: Date.now() - t0 };
  } catch (e) {
    return { http: 0, body: null, ms: Date.now() - t0, network_error: String(e) };
  }
}

async function compactOutcome(o) {
  if (!o) return { kind: "missing" };
  const base = { kind: o.kind, status: o.kind === "verification" ? o.status : o.kind };
  if (o.kind === "system_error") return { ...base, error_code: o.error?.code ?? null, provider_failure: PROVIDER_CODES.has(o.error?.code) };
  if (o.kind === "required_source_unavailable") return { ...base, claim_types: o.required_claim_types, unavailable_sources: o.unavailable_sources };
  if (o.kind === "out_of_scope") return { ...base, claim_types: [], reason: o.reason };
  const evidence = [];
  for (const e of o.evidence) {
    evidence.push({
      id: e.evidence_id,
      trusted_source_id: e.trusted_source_id,
      source_type: e.source_type,
      provider: e.provider,
      reference: e.reference,
      source_address: e.source_address,
      source_url: e.source_url,
      sha_ok: (await sha256(e.text)) === e.text_sha256,
      text_len: e.text.length,
      quran: e.source_type === "quran" ? { surah: e.metadata.surah_number, ayah: e.metadata.ayah_number, text: e.text } : null,
    });
  }
  const byId = Object.fromEntries(o.evidence.map((e) => [e.evidence_id, e]));
  const norm = (s) => s.replace(/[ً-ْٰ]/g, "").replace(/[أإآٱ]/g, "ا").replace(/ى/g, "ي").replace(/ة/g, "ه").replace(/ئ/g, "ي").replace(/ؤ/g, "و").replace(/\s+/g, " ").trim();
  return {
    ...base,
    claim_types: [...new Set(o.analysis.components.filter((c) => c.role === "substantive").map((c) => c.claim_type))],
    components: o.analysis.components.map((c) => ({ id: c.component_id, kind: c.kind, role: c.role, type: c.claim_type, outcome: c.outcome, text: c.text })),
    assessments: o.analysis.assessments.map((a) => {
      const ev = byId[a.evidence_id];
      let span_ok = null;
      if (a.evidence_span && ev) {
        span_ok = ev.text.includes(a.evidence_span) ||
          (ev.source_type === "quran" && norm(ev.metadata.ayah_text_normalized).includes(norm(a.evidence_span)));
      }
      return { evidence_id: a.evidence_id, component: a.component_id, rel: a.relationship, by: a.assessed_by, has_span: !!a.evidence_span, span_ok, evidence_in_result: !!ev };
    }),
    evidence,
    verified_reference: o.verified_reference ?? null,
    limitations: o.limitations ?? [],
    validation: o.validation?.outcome ?? null,
    gate_checks_passed: (o.validation?.checks ?? []).every((c) => c.passed),
  };
}

async function verifyText(base, caseId, text) {
  const cid = `${caseId}-${Math.random().toString(36).slice(2, 8)}`;
  const conf = await post(base, "/api/v1/claims/confirm", {
    explicit_user_confirmation: true,
    claims: [{ claim_id: cid, origin: "manual", original_text: text, extracted_claim_text: null, text, selected: true, extraction_status: null, provided_evidence: null, provided_reference: null }],
  });
  if (conf.http !== 200) return { stage: "confirm", http: conf.http, error: conf.body };
  const v = await post(base, "/api/v1/verify", { claims: conf.body.confirmed_claims });
  if (v.http !== 200) return { stage: "verify", http: v.http, error: v.body?.error?.code ?? v.body?.code ?? null, provider_failure: v.http === 0 || v.http === 503 || v.http === 429 };
  return { stage: "done", http: 200, ms: v.ms, outcome: await compactOutcome(v.body.outcomes[0]) };
}

const API_REQUESTS = {
  verify_empty_claim: { path: "/api/v1/verify", body: { claims: [{ claim_id: "v1", confirmed_claim_text: "", user_confirmation_status: "confirmed" }] } },
  verify_too_long: { path: "/api/v1/verify", body: { claims: [{ claim_id: "v2", confirmed_claim_text: "أ".repeat(1001), user_confirmation_status: "confirmed" }] } },
  verify_unconfirmed: { path: "/api/v1/verify", body: { claims: [{ claim_id: "v3", confirmed_claim_text: "قال تعالى: «قل هو الله أحد»", user_confirmation_status: "pending" }] } },
  verify_duplicate_ids: { path: "/api/v1/verify", body: { claims: [1, 2].map(() => ({ claim_id: "dup", confirmed_claim_text: "قال تعالى: «قل هو الله أحد»", user_confirmation_status: "confirmed" })) } },
  alternative_unknown_run: { path: "/api/v1/alternative-wording", body: { run_id: "unknown-run", claim_id: "x" } },
};

export async function runEvaluation({ base = "http://localhost:8000", dataset, repeats = {}, delayMs = 2500, only = null, log = () => {} }) {
  const out = { started_at: new Date().toISOString(), base, runs: [] };
  for (const c of dataset.cases) {
    if (only && !only.includes(c.case_id)) continue;
    const n = repeats[c.case_id] ?? 1;
    for (let run = 1; run <= n; run++) {
      const rec = { case_id: c.case_id, run, at: new Date().toISOString() };
      if (c.mode === "api") {
        const req = API_REQUESTS[c.request];
        const r = await post(base, req.path, req.body);
        Object.assign(rec, { http: r.http, code: r.body?.code ?? r.body?.error?.code ?? null });
      } else if (c.mode === "verify") {
        Object.assign(rec, await verifyText(base, c.case_id, c.input));
        await sleep(delayMs);
      } else if (c.mode === "extract") {
        const ex = await post(base, "/api/v1/claims/extract", { text: c.input });
        rec.extract_http = ex.http;
        if (ex.http !== 200) {
          rec.error = ex.body?.error?.code ?? ex.body?.code ?? null;
          rec.provider_failure = ex.http === 0 || ex.http >= 500;
        } else {
          rec.extracted = ex.body.claims.map((x) => ({ text: x.extracted_claim_text, original_text: x.original_text, status: x.extraction_status }));
          rec.verified = [];
          for (const x of ex.body.claims) {
            await sleep(delayMs);
            rec.verified.push({ text: x.extracted_claim_text, ...(await verifyText(base, c.case_id, x.extracted_claim_text)) });
          }
        }
        await sleep(delayMs);
      }
      out.runs.push(rec);
      log(`${c.case_id}#${run} ${rec.outcome?.status ?? rec.http ?? rec.extract_http ?? rec.stage}`);
    }
  }
  out.finished_at = new Date().toISOString();
  return out;
}

// Node CLI
if (typeof process !== "undefined" && process.argv?.[1]?.endsWith("run_eval.mjs")) {
  const { readFileSync } = await import("node:fs");
  const dataset = JSON.parse(readFileSync(new URL("./dataset.json", import.meta.url), "utf-8"));
  const stability = JSON.parse(readFileSync(new URL("./stability.json", import.meta.url), "utf-8"));
  const res = await runEvaluation({ base: process.argv[2] ?? "http://localhost:8000", dataset, repeats: stability.repeats, log: (m) => console.error(m) });
  console.log(JSON.stringify(res, null, 1));
}
