#!/usr/bin/env python3
"""Export authentic, frozen GeoScope 55-group records to CSV. No fitted/plot-derived data.

The archive is authenticated by the same SHA-256 and member checks as reproduce_analysis.py.
All outputs are derived from its original JSONL records or verified frozen evaluation.
This script cannot recover missing external OC20 case-level or log-probability inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile

from reproduce_analysis import EXPECTED_SHA256, load_verified


def csv_write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows to export: {path.name}")
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: (json.dumps(row.get(key), ensure_ascii=False, sort_keys=True)
                      if isinstance(row.get(key), (dict, list)) else row.get(key))
                for key in fields
            })


def source_csv(record: dict) -> dict:
    row = {
        "group_id": record.get("group_id"),
        "pair_id": record.get("pair_id"),
        "origin": record.get("origin"),
        "split": record.get("split"),
    }
    for key, value in record.get("measurements", {}).items():
        if isinstance(value, (str, int, float)) or value is None:
            row[key] = value
    a = record.get("measurements", {}).get("adsorbate_frame_rmsd_A")
    i = record.get("measurements", {}).get("internal_rmsd_A")
    try:
        row["adsorbate_frame_to_internal_ratio"] = float(a) / float(i) if float(i) != 0 else None
    except (TypeError, ValueError, ZeroDivisionError):
        row["adsorbate_frame_to_internal_ratio"] = None
    row["original_record_json"] = record
    return row


def read_member(z: zipfile.ZipFile, suffix: str) -> list[dict]:
    matches = [n for n in z.namelist() if n.endswith("/" + suffix)]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {suffix}; found {matches}")
    return [json.loads(s) for s in z.read(matches[0]).splitlines() if s.strip()]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", type=Path, default=Path("evidence/final_results_original.zip"))
    p.add_argument("--out", type=Path, default=Path("exported_figure_data"))
    args = p.parse_args()
    data, verified_members = load_verified(args.evidence)
    args.out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.evidence) as z:
        source = read_member(z, "source_pair_measurements.jsonl")
    measured = [s for s in source if s.get("origin") == "measured_endpoint_pair"]
    controls = [s for s in source if s.get("origin") == "synthetic_control"]
    if len(measured) != 55 or len(controls) != 55 or len({s["group_id"] for s in measured}) != 55:
        raise ValueError(f"Expected 55 measured and 55 controls, got {len(measured)}, {len(controls)}")
    csv_write(args.out / "UMA_55_real_source_measurements.csv", [source_csv(x) for x in measured])
    csv_write(args.out / "UMA_110_source_pairs_including_controls.csv", [source_csv(x) for x in source])
    public = data["cases_public.jsonl"]
    gold = data["cases_gold_DO_NOT_SEND_TO_MODELS.jsonl"]
    labels = {g["case_id"]: g for g in gold}
    if len(public) != 1760 or len(gold) != 1760:
        raise ValueError("Frozen benchmark must contain 1,760 cases and matching labels")
    csv_write(args.out / "UMA_1760_cases_and_gold_proofs.csv", [
        { "case_id": c["case_id"], "group_id": c.get("group_id"),
          "base_case_id": c.get("base_case_id"), "family": c.get("family"),
          "presentation": c.get("presentation"), "target_metric": c.get("target_metric"),
          "expected": labels[c["case_id"]]["expected"],
          "valid_proofs": labels[c["case_id"]]["valid_proofs"],
          "model_payload": c["model_payload"]}
        for c in public
    ])
    preds = [row for key in ("qwen", "phi", "smol") for row in data[f"predictions_{key}.jsonl"]]
    if len(preds) != 10560:
        raise ValueError(f"Expected 10,560 raw requests, got {len(preds)}")
    csv_write(args.out / "UMA_10560_first_attempts.csv", preds)
    scoring = data["evaluation.json"]
    if scoring.get("source_groups") != 55 or len(scoring.get("rows", [])) < 10000:
        raise ValueError("Frozen scored-case payload is incomplete")
    csv_write(args.out / "UMA_frozen_per_case_method_scores.csv", scoring["rows"])
    csv_write(args.out / "UMA_frozen_per_method_summary.csv", [
        {k: v for k, v in x.items() if not isinstance(v, (dict, list))}
        for x in scoring["summaries"]
    ])
    csv_write(args.out / "UMA_frozen_paired_comparisons.csv", scoring["paired_comparisons"])
    csv_write(args.out / "UMA_frozen_completeness.csv", scoring["completeness"])
    ratios = sorted(x["adsorbate_frame_to_internal_ratio"] for x in [source_csv(y) for y in measured]
                    if x["adsorbate_frame_to_internal_ratio"] is not None)
    info = {
        "archive": str(args.evidence),
        "sha256": hashlib.sha256(args.evidence.read_bytes()).hexdigest(),
        "expected_sha256": EXPECTED_SHA256,
        "verified_members": verified_members,
        "real_systems": len(measured),
        "synthetic_controls": len(controls),
        "cases": len(public),
        "model_first_attempts": len(preds),
        "ratios_finite": len(ratios),
        "median_adsorbate_to_internal": (ratios[len(ratios)//2] if len(ratios)%2 else (ratios[len(ratios)//2-1]+ratios[len(ratios)//2])/2),
        "ratios_above_10": sum(x > 10 for x in ratios),
        "note": "Rows copied from verified frozen input and evaluation; no plot digitization, estimated coordinates, or new LLM inference. External OC20 raw-case and confidence-span outputs are not included in the repository.",
    }
    (args.out / "PROVENANCE.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    if len(ratios) != 55 or sum(x > 10 for x in ratios) != 16:
        raise ValueError("Original geometry-count audit mismatch: expected 55 valid ratios, 16 >10")
    if abs(info["median_adsorbate_to_internal"] - 3.26988) > 0.005:
        raise ValueError("Original median RMSD ratio mismatch")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
