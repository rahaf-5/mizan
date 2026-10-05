"""Score a Mizan evaluation run.

    cd backend && python ../evaluation/score_eval.py ../evaluation/results/raw.json

Inputs: evaluation/dataset.json (ground truth) + raw runner output (evaluation/run_eval.mjs).
Outputs (evaluation/results/): results.json, results.csv, metrics.json.
Every number is computed here from those two files; nothing is entered by hand. Quran evidence
is additionally checked against the local official Mushaf 1 dump (backend/data/quranpedia).
External provider failures (rate limit / timeout / network) are counted separately and are
excluded from accuracy denominators.
"""

from __future__ import annotations

import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.pipeline.arabic_text import normalize_for_matching as norm  # noqa: E402

ALLOWLIST = {
    "quran",
    "tafsir_al_muyassar",
    "tafsir_ibn_kathir",
    "asbab_al_nuzul_al_wahidi",
    "al_muharrar_fi_asbab_al_nuzul",
}
PROVIDER_CODES = {"llm_rate_limited", "llm_timeout", "llm_provider_error", "llm_auth_failed", "network_error"}


def load_mushaf() -> dict[tuple[int, int], tuple[str, str]]:
    raw = json.load(gzip.open(ROOT / "backend/data/quranpedia/mushafs-1.json.gz"))["data"]
    out = {}
    for s in raw["surahs"]:
        for a in s["ayahs"]:
            out[(int(s["id"]), int(a["number"]))] = (s["name"], a["text"].replace("﻿", "").strip())
    return out


def status_of(rec: dict) -> str | None:
    if rec.get("stage") == "done":
        return rec["outcome"]["status"]
    return None


def provider_failure(rec: dict) -> bool:
    if rec.get("provider_failure"):
        return True
    o = rec.get("outcome") or {}
    return o.get("kind") == "system_error" and o.get("error_code") in PROVIDER_CODES


def pct(a: int, b: int) -> float | None:
    return round(100 * a / b, 1) if b else None


def main(raw_path: str) -> None:
    dataset = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
    raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    cases = {c["case_id"]: c for c in dataset["cases"]}
    runs = defaultdict(list)
    for r in raw["runs"]:
        runs[r["case_id"]].append(r)
    mushaf = load_mushaf()

    rows, provider_failures = [], []
    status_tot = status_ok = 0
    by_cat, by_expected, by_gt = (defaultdict(lambda: [0, 0]) for _ in range(3))
    type_tot = type_ok = 0
    src_tot = src_ok = ref_tot = ref_ok = 0
    api_tot = api_ok = 0
    ext = {"expected_claims": 0, "found": 0, "type_checked": 0, "type_ok": 0, "status_checked": 0,
           "status_ok": 0, "count_rules": 0, "count_ok": 0, "cases": 0, "cases_all_ok": 0}
    cit = Counter()
    cit_fail: list[str] = []

    def check_evidence(case_id: str, o: dict) -> None:
        for e in o.get("evidence", []):
            cit["evidence_items"] += 1
            ok = True
            if e["trusted_source_id"] not in ALLOWLIST:
                ok = False; cit_fail.append(f"{case_id}: source not in allowlist {e['trusted_source_id']}")
            if e["provider"] != "quranpedia":
                ok = False; cit_fail.append(f"{case_id}: unexpected provider {e['provider']}")
            if not e["reference"]:
                ok = False; cit_fail.append(f"{case_id}: empty reference")
            if e["source_url"] != "https://api.quranpedia.net" + e["source_address"]:
                ok = False; cit_fail.append(f"{case_id}: url/address mismatch {e['source_url']}")
            if not e["sha_ok"]:
                ok = False; cit_fail.append(f"{case_id}: SHA-256 does not match displayed text")
            if e["quran"]:
                q = e["quran"]
                name, text = mushaf.get((q["surah"], q["ayah"]), (None, None))
                if text is None or q["text"].strip() != text:
                    ok = False; cit_fail.append(f"{case_id}: Quran text differs from Mushaf 1 {q['surah']}:{q['ayah']}")
                if e["reference"] != f"{name}، الآية {q['ayah']}":
                    ok = False; cit_fail.append(f"{case_id}: Quran reference mismatch {e['reference']}")
                cit["quran_items_checked_against_mushaf"] += 1
            cit["evidence_ok"] += ok
        for a in o.get("assessments", []):
            cit["assessments"] += 1
            if not a["evidence_in_result"]:
                cit_fail.append(f"{case_id}: assessment cites evidence missing from the result")
            elif a["has_span"]:
                cit["spans"] += 1
                if a["span_ok"]:
                    cit["spans_ok"] += 1
                else:
                    cit_fail.append(f"{case_id}: cited span not found in evidence text ({a['by']})")
        if o.get("kind") == "verification":
            cit["results_with_gate"] += 1
            cit["gate_all_checks_passed"] += bool(o.get("gate_checks_passed")) and o.get("validation") in ("pass", "abstain")

    for cid, c in cases.items():
        rs = runs.get(cid, [])
        if not rs:
            rows.append({"case_id": cid, "category": c["category"], "pass": None, "notes": "not run"})
            continue
        r1 = rs[0]
        row = {"case_id": cid, "category": c["category"], "ground_truth": c["ground_truth"], "mode": c["mode"],
               "input": c.get("input") or c.get("request"), "notes": c.get("notes", "")}
        if c["mode"] == "api":
            api_tot += 1
            p = r1["http"] in c["expected_http"]
            api_ok += p
            row.update(expected=c["expected_http"], actual=r1["http"], **{"pass": p})
        elif c["mode"] == "verify":
            for r in rs:
                if r.get("stage") == "done":
                    check_evidence(cid, r["outcome"])
            if provider_failure(r1):
                provider_failures.append(cid)
                row.update(expected=c["expected_statuses"], actual="EXTERNAL_PROVIDER_FAILURE", **{"pass": None})
            else:
                st = status_of(r1)
                p = st in c["expected_statuses"]
                status_tot += 1; status_ok += p
                for key, bucket in ((c["category"], by_cat), (c["expected_statuses"][0], by_expected), (c["ground_truth"], by_gt)):
                    bucket[key][0] += 1; bucket[key][1] += p
                o = r1.get("outcome") or {}
                actual_types = set(o.get("claim_types") or [])
                if c["expected_claim_types"] and o:
                    type_tot += 1
                    t_ok = set(c["expected_claim_types"]) <= actual_types
                    type_ok += t_ok
                    row["claim_type_ok"] = t_ok
                if c["expected_sources"] and o.get("kind") == "verification":
                    src_tot += 1
                    got = {e["trusted_source_id"] for e in o["evidence"]}
                    s_ok = bool(got & set(c["expected_sources"]))
                    src_ok += s_ok
                    row["expected_source_retrieved"] = s_ok
                    if c["expected_references"]:
                        ref_tot += 1
                        refs = {e["reference"] for e in o["evidence"]} | {o.get("verified_reference") or ""}
                        r_ok = bool(refs & set(c["expected_references"]))
                        ref_ok += r_ok
                        row["expected_reference_found"] = r_ok
                row.update(expected=c["expected_statuses"], actual=st, actual_claim_types=sorted(actual_types),
                           actual_references=sorted({e["reference"] for e in o.get("evidence", [])}), **{"pass": p})
        else:  # extract
            ext["cases"] += 1
            if r1.get("extract_http") != 200:
                provider_failures.append(cid)
                row.update(actual="EXTERNAL_PROVIDER_FAILURE" if r1.get("provider_failure") else f"http {r1.get('extract_http')}", **{"pass": None})
            else:
                for v in r1["verified"]:
                    if v.get("stage") == "done":
                        check_evidence(cid, v["outcome"])
                extracted = r1["extracted"]
                all_ok = True
                details = []
                for exp in c["expected_claims"]:
                    ext["expected_claims"] += 1
                    match = next((v for v in r1["verified"] if all(norm(k) in norm(v["text"]) for k in exp["must_contain"])), None)
                    if not match:
                        all_ok = False; details.append(f"missing claim {exp['must_contain']}")
                        continue
                    ext["found"] += 1
                    o = match.get("outcome") or {}
                    if provider_failure(match):
                        details.append("verification: external provider failure"); continue
                    ext["type_checked"] += 1
                    t_ok = exp["type"] in (o.get("claim_types") or [])
                    ext["type_ok"] += t_ok
                    ext["status_checked"] += 1
                    s_ok = o.get("status") in exp["statuses"]
                    ext["status_ok"] += s_ok
                    all_ok &= t_ok and s_ok
                    details.append(f"«{match['text']}» → {o.get('status')} types={o.get('claim_types')}")
                if "max_claims" in c:
                    ext["count_rules"] += 1
                    c_ok = len(extracted) <= c["max_claims"]
                    ext["count_ok"] += c_ok
                    all_ok &= c_ok
                    details.append(f"extracted {len(extracted)} (max {c['max_claims']})")
                ext["cases_all_ok"] += all_ok
                row.update(expected=c["expected_claims"], actual=[x["text"] for x in extracted], details=details, **{"pass": all_ok})
        rows.append(row)

    # stability
    stab = []
    for cid, rs in runs.items():
        if len(rs) < 2:
            continue
        c = cases[cid]
        usable = [r for r in rs if not provider_failure(r)]
        if c["mode"] == "extract":
            sigs = [tuple(sorted(norm(v["text"]) for v in r.get("verified", []))) + tuple(sorted(str(status_of(v)) for v in r.get("verified", []))) for r in usable]
            statuses = [tuple(sorted(str(status_of(v)) for v in r.get("verified", []))) for r in usable]
            refs = [tuple(sorted({e["reference"] for v in r.get("verified", []) for e in (v.get("outcome") or {}).get("evidence", [])})) for r in usable]
        else:
            statuses = [status_of(r) for r in usable]
            refs = [tuple(sorted({e["reference"] for e in (r.get("outcome") or {}).get("evidence", [])})) for r in usable]
            sigs = statuses
        stab.append({"case_id": cid, "runs": len(rs), "usable_runs": len(usable),
                     "statuses": [str(s) for s in statuses], "status_stable": len(set(statuses)) == 1,
                     "references_stable": len(set(refs)) == 1, "extraction_stable": (len(set(sigs)) == 1) if c["mode"] == "extract" else None})

    metrics = {
        "dataset_cases": len(cases),
        "runs_total": len(raw["runs"]),
        "started_at": raw.get("started_at"), "finished_at": raw.get("finished_at"),
        "status_accuracy": {"evaluated": status_tot, "correct": status_ok, "incorrect": status_tot - status_ok, "accuracy_pct": pct(status_ok, status_tot),
                            "by_category": {k: {"total": v[0], "correct": v[1]} for k, v in sorted(by_cat.items())},
                            "by_expected_status": {k: {"total": v[0], "correct": v[1]} for k, v in sorted(by_expected.items())},
                            "by_ground_truth": {k: {"total": v[0], "correct": v[1]} for k, v in sorted(by_gt.items())}},
        "claim_type_classification": {"evaluated": type_tot, "correct": type_ok, "accuracy_pct": pct(type_ok, type_tot)},
        "retrieval": {"expected_source_cases": src_tot, "expected_source_retrieved": src_ok, "expected_source_success_pct": pct(src_ok, src_tot),
                      "expected_reference_cases": ref_tot, "expected_reference_found": ref_ok, "expected_reference_success_pct": pct(ref_ok, ref_tot),
                      "top_k": "not measurable: the API returns only the evidence used in the final result, not the ranked candidate list"},
        "extraction": {**ext, "expected_claims_found_pct": pct(ext["found"], ext["expected_claims"]),
                       "claim_type_pct": pct(ext["type_ok"], ext["type_checked"]), "status_pct": pct(ext["status_ok"], ext["status_checked"])},
        "api_validation": {"evaluated": api_tot, "correct": api_ok},
        "citation_verification": {**dict(cit), "failures": cit_fail},
        "stability": {"cases": len(stab), "status_stable": sum(s["status_stable"] for s in stab), "references_stable": sum(s["references_stable"] for s in stab), "details": stab},
        "external_provider_failures": {"count": len(provider_failures), "cases": provider_failures},
    }
    out = HERE / "results"
    (out / "results.json").write_text(json.dumps({"metrics": metrics, "cases": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    with (out / "results.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "category", "ground_truth", "mode", "input", "expected", "actual", "pass", "claim_type_ok", "expected_source_retrieved", "expected_reference_found", "notes"])
        for r in rows:
            w.writerow([r.get("case_id"), r.get("category"), r.get("ground_truth"), r.get("mode"), r.get("input"),
                        json.dumps(r.get("expected"), ensure_ascii=False), json.dumps(r.get("actual"), ensure_ascii=False),
                        r.get("pass"), r.get("claim_type_ok"), r.get("expected_source_retrieved"), r.get("expected_reference_found"), r.get("notes")])
    print(json.dumps({k: v for k, v in metrics.items() if k not in ("citation_verification", "stability")}, ensure_ascii=False, indent=1))
    print("citation:", {k: v for k, v in metrics["citation_verification"].items() if k != "failures"}, "failures:", len(cit_fail))
    print("stability:", metrics["stability"]["cases"], metrics["stability"]["status_stable"], metrics["stability"]["references_stable"])


if __name__ == "__main__":
    main(sys.argv[1])
