"""Strict, failure-inclusive scoring for a frozen development pilot.

Only model raw text is parsed. A prediction's cached ``parsed`` field is never
trusted. Statistical intervals resample entire source-system groups, retaining
all presentation variants and contrasts within each sampled group. They are
exploratory development estimates, not held-out generalization evidence.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VERDICTS = ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")
INVALID = "INVALID"
SUCCESS_STATUSES = frozenset(("ok", "success", "completed"))


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON object key")
        obj[key] = value
    return obj


def _reject_constant(value):
    raise ValueError("non-finite JSON number: " + value)


def parse_prediction(text: str) -> dict:
    """Return a strictly parsed prediction, or raise ValueError.

    Whitespace around one JSON object is accepted. Markdown fences, commentary,
    trailing material, duplicate keys, extra fields and citation duplicates are
    invalid. No case folding, coercion, extraction or repair is performed.
    """
    if not isinstance(text, str):
        raise ValueError("raw output must be text")
    try:
        result = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (TypeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("output is not one strict JSON object: " + str(exc)) from exc
    if not isinstance(result, dict) or set(result) != {"verdict", "evidence_ids"}:
        raise ValueError("object must contain exactly verdict and evidence_ids")
    if result["verdict"] not in VERDICTS:
        raise ValueError("verdict must be an allowed uppercase label")
    ids = result["evidence_ids"]
    if not isinstance(ids, list) or any(not isinstance(item, str) or not item or item.strip() != item for item in ids):
        raise ValueError("evidence_ids must be a list of nonempty, unpadded strings")
    if len(set(ids)) != len(ids):
        raise ValueError("evidence_ids must not repeat")
    return {"verdict": result["verdict"], "evidence_ids": list(ids)}


def _visible_ids(case: dict) -> set[str]:
    payload = case.get("model_payload", {})
    packet = payload.get("evidence_packet", {})
    if isinstance(packet, dict):
        measurements = packet.get("measurements", [])
        if not isinstance(measurements, list):
            raise ValueError("evidence_packet.measurements must be a list")
        result = [item["evidence_id"] for item in measurements if isinstance(item, dict) and "evidence_id" in item]
        if len(result) != len(set(result)):
            raise ValueError("duplicate visible evidence ID")
    else:
        result = []
    report = payload.get("evidence_report", "")
    if report:
        if not isinstance(report, str):
            raise ValueError("evidence_report must be text")
        report_ids = re.findall(r"Evidence ID:\s*(E_[0-9a-f]{24})(?:\.|\s|$)", report)
        if len(report_ids) != len(set(report_ids)):
            raise ValueError("duplicate evidence-report ID")
        result += report_ids
    if any(not isinstance(item, str) or not item for item in result):
        raise ValueError("visible evidence IDs must be nonempty strings")
    return set(result)


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(field + " must be a nonempty, unpadded string")
    return value


def _fraction(numerator: int | float, denominator: int | float):
    return numerator / denominator if denominator else None


def _metrics(rows: list[dict]) -> dict:
    n = len(rows)
    valid = [r for r in rows if r["format_valid"]]
    unsupported = [r for r in rows if r["expected"] != "SUPPORTED"]
    decisive = [r for r in rows if r["expected"] != "INSUFFICIENT_EVIDENCE"]
    truth_insuff = [r for r in rows if r["expected"] == "INSUFFICIENT_EVIDENCE"]
    confusion = {gold: {pred: 0 for pred in (*VERDICTS, INVALID)} for gold in VERDICTS}
    for row in rows:
        confusion[row["expected"]][row["predicted_verdict"]] += 1
    per_class = {}
    for label in VERDICTS:
        tp = confusion[label][label]
        fp = sum(confusion[g][label] for g in VERDICTS if g != label)
        fn = sum(count for pred, count in confusion[label].items() if pred != label)
        f1 = _fraction(2 * tp, 2 * tp + fp + fn)
        per_class[label] = {"support": sum(confusion[label].values()), "precision": _fraction(tp, tp + fp),
                            "recall": _fraction(tp, tp + fn), "f1": f1 if f1 is not None else 0.0}
    return {
        "cases": n, "valid_responses": len(valid),
        "strict_correct": sum(r["label_correct"] for r in rows),
        "joint_correct": sum(r["joint_correct"] for r in rows),
        "strict_accuracy": _fraction(sum(r["label_correct"] for r in rows), n),
        "format_rate": _fraction(len(valid), n),
        "valid_only_accuracy": _fraction(sum(r["label_correct"] for r in valid), len(valid)),
        "evidence_exact_accuracy": _fraction(sum(r["evidence_exact"] for r in rows), n),
        "joint_accuracy": _fraction(sum(r["joint_correct"] for r in rows), n),
        "valid_reference_rate": _fraction(sum(r["citations_reference_visible"] for r in rows), n),
        "mean_evidence_precision_valid_only": _fraction(sum(r["evidence_precision"] for r in valid), len(valid)),
        "mean_evidence_recall_valid_only": _fraction(sum(r["evidence_recall"] for r in valid), len(valid)),
        "unsupported_acceptance_count": sum(r["predicted_verdict"] == "SUPPORTED" for r in unsupported),
        "unsupported_claims": len(unsupported),
        "unsupported_acceptance_rate": _fraction(sum(r["predicted_verdict"] == "SUPPORTED" for r in unsupported), len(unsupported)),
        "excess_abstention_count": sum(r["predicted_verdict"] == "INSUFFICIENT_EVIDENCE" for r in decisive),
        "decisive_claims": len(decisive),
        "excess_abstention_rate": _fraction(sum(r["predicted_verdict"] == "INSUFFICIENT_EVIDENCE" for r in decisive), len(decisive)),
        "insufficiency_recall": _fraction(sum(r["label_correct"] for r in truth_insuff), len(truth_insuff)),
        "macro_f1_fixed_three_labels": sum(x["f1"] for x in per_class.values()) / len(VERDICTS),
        "per_class": per_class, "confusion": confusion,
        "invalid_response_reasons": dict(Counter(r["invalid_reason"] for r in rows if not r["format_valid"])),
    }


def _paired_metrics(rows):
    contrasts = defaultdict(list)
    representations = defaultdict(list)
    for r in rows:
        if r["contrast_group_id"]:
            contrasts[(r["group_id"], r["presentation"], r["contrast_group_id"])].append(r)
        if r["base_case_id"]:
            representations[(r["group_id"], r["base_case_id"])].append(r)
    complete_contrasts = [v for v in contrasts.values() if len(v) == 2 and {r["expected"] for r in v} == {"SUPPORTED", "CONTRADICTED"}]
    complete_repr = [v for v in representations.values() if len(v) == 2 and len({r["presentation"] for r in v}) == 2]
    same_verdict = lambda group: all(r["format_valid"] for r in group) and len({r["predicted_verdict"] for r in group}) == 1
    return {
        "contrast_groups": len(contrasts), "eligible_binary_contrast_pairs": len(complete_contrasts),
        "excluded_nonbinary_or_incomplete_contrast_groups": len(contrasts) - len(complete_contrasts),
        "contrast_pair_both_labels_correct": _fraction(sum(all(r["label_correct"] for r in g) for g in complete_contrasts), len(complete_contrasts)),
        "contrast_pair_both_joint_correct": _fraction(sum(all(r["joint_correct"] for r in g) for g in complete_contrasts), len(complete_contrasts)),
        "representation_groups": len(representations), "eligible_representation_pairs": len(complete_repr),
        "representation_verdict_invariance": _fraction(sum(same_verdict(g) for g in complete_repr), len(complete_repr)),
        "representation_both_labels_correct": _fraction(sum(all(r["label_correct"] for r in g) for g in complete_repr), len(complete_repr)),
        "representation_both_joint_correct": _fraction(sum(all(r["joint_correct"] for r in g) for g in complete_repr), len(complete_repr)),
        "note": "Invariance alone can reward a consistently wrong model; both-correct rates are reported separately.",
    }


def _percentile(values, q):
    ordered = sorted(values)
    loc = (len(ordered) - 1) * q
    lo, hi = math.floor(loc), math.ceil(loc)
    return ordered[lo] * (hi - loc) + ordered[hi] * (loc - lo) if lo != hi else ordered[lo]


def _bootstrap(rows, seed, samples):
    groups = defaultdict(list)
    for row in rows:
        groups[row["group_id"]].append(row)
    keys = sorted(groups)
    if not keys or not samples:
        return {"source_groups": len(keys), "samples": samples, "intervals": {}, "status": "disabled_or_empty"}
    totals = {k: (len(v), sum(r["label_correct"] for r in v), sum(r["joint_correct"] for r in v)) for k, v in groups.items()}
    rng = random.Random(seed)
    accuracy, joint = [], []
    for _ in range(samples):
        chosen = rng.choices(keys, k=len(keys))
        n = sum(totals[k][0] for k in chosen)
        accuracy.append(sum(totals[k][1] for k in chosen) / n)
        joint.append(sum(totals[k][2] for k in chosen) / n)
    return {"source_groups": len(keys), "samples": samples, "intervals": {
        "strict_accuracy": [_percentile(accuracy, .025), _percentile(accuracy, .975)],
        "joint_accuracy": [_percentile(joint, .025), _percentile(joint, .975)]},
        "interval_type": "unadjusted exploratory percentile 95% source-group cluster bootstrap",
        "resampling_unit": "source-system group; all cases and presentations retained together",
        "limitation": "Pilot-development groups; intervals do not establish held-out generalization.",
        "seed": seed}


def evaluate(public_cases: list[dict], gold: list[dict], predictions: list[dict], seed=20261020, bootstrap_samples=1000) -> dict:
    """Score all expected cases for each observed model/condition combination.

    Missing predictions, errors, duplicates and malformed responses score wrong.
    A duplicate prediction key invalidates that case, including exact repeats.
    Unknown case IDs are excluded and reported; they never enlarge the scored
    denominator or count as successes. Gold and public case sets must agree.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if isinstance(bootstrap_samples, bool) or not isinstance(bootstrap_samples, int) or bootstrap_samples < 0:
        raise ValueError("bootstrap_samples must be a nonnegative integer")
    if not isinstance(public_cases, list) or not public_cases:
        raise ValueError("public_cases must be a nonempty list")
    public = {}
    visible = {}
    for case in public_cases:
        cid = _identifier(case.get("case_id"), "case_id")
        if cid in public:
            raise ValueError("duplicate public case_id: " + cid)
        _identifier(case.get("group_id"), "group_id")
        public[cid] = case
        visible[cid] = _visible_ids(case)
    answers = {}
    for answer in gold:
        cid = _identifier(answer.get("case_id"), "gold case_id")
        if cid in answers:
            raise ValueError("duplicate gold case_id: " + cid)
        if answer.get("expected") not in VERDICTS:
            raise ValueError("invalid gold verdict")
        ids = answer.get("required_evidence_ids")
        if not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids) or len(ids) != len(set(ids)):
            raise ValueError("invalid gold required_evidence_ids")
        answers[cid] = answer
    if set(public) != set(answers):
        raise ValueError("public and gold case IDs must match exactly")
    for cid, answer in answers.items():
        if not set(answer["required_evidence_ids"]).issubset(visible[cid]):
            raise ValueError("gold cites evidence absent from model payload: " + cid)
    indexed = defaultdict(list)
    combinations = set()
    unknown = []
    for pred in predictions:
        model = _identifier(pred.get("model_key"), "model_key")
        condition = _identifier(pred.get("condition"), "condition")
        cid = _identifier(pred.get("case_id"), "prediction case_id")
        combinations.add((model, condition))
        if cid not in public:
            unknown.append({"model_key": model, "condition": condition, "case_id": cid})
        else:
            indexed[(model, condition, cid)].append(pred)
    rows, summaries, completeness = [], [], []
    for model, condition in sorted(combinations):
        modelrows = []
        for cid in sorted(public):
            case, answer = public[cid], answers[cid]
            items = indexed[(model, condition, cid)]
            parsed, invalid, raw = None, None, None
            if not items:
                invalid = "missing_prediction"
            elif len(items) > 1:
                invalid = "duplicate_prediction"
            else:
                pred = items[0]
                raw = pred.get("raw_output")
                status = pred.get("status", "ok")
                if status == "missing":
                    invalid = "missing_prediction"
                elif status not in SUCCESS_STATUSES or pred.get("error"):
                    invalid = "execution_error"
                else:
                    try:
                        parsed = parse_prediction(raw)
                    except ValueError:
                        invalid = "invalid_format"
            valid = parsed is not None
            predicted = parsed["verdict"] if valid else INVALID
            ids = set(parsed["evidence_ids"]) if valid else set()
            required = set(answer["required_evidence_ids"])
            references = valid and ids.issubset(visible[cid])
            exact = valid and references and ids == required
            correct = valid and predicted == answer["expected"]
            precision = len(ids & required) / len(ids) if ids else (1.0 if not required else 0.0)
            recall = len(ids & required) / len(required) if required else 1.0
            row = {"case_id": cid, "group_id": case["group_id"], "base_case_id": case.get("base_case_id", ""),
                   "contrast_group_id": case.get("contrast_group_id", ""), "presentation": case.get("presentation", "unknown"),
                   "family": case.get("family", "unknown"), "target_metric": case.get("target_metric", "unknown"),
                   "model_key": model, "condition": condition, "expected": answer["expected"],
                   "predicted_verdict": predicted, "predicted_evidence_ids": sorted(ids), "required_evidence_ids": sorted(required),
                   "format_valid": valid, "invalid_reason": invalid, "label_correct": bool(correct),
                   "citations_reference_visible": bool(references), "evidence_exact": bool(exact),
                   "evidence_precision": precision if valid else 0.0, "evidence_recall": recall if valid else 0.0,
                   "joint_correct": bool(correct and exact), "prediction_records": len(items),
                   "raw_output_sha256": hashlib.sha256(raw.encode()).hexdigest() if isinstance(raw, str) else None}
            modelrows.append(row)
        summary = {"model_key": model, "condition": condition, **_metrics(modelrows), "paired": _paired_metrics(modelrows)}
        summary["breakdowns"] = {}
        for field in ("family", "presentation", "target_metric", "group_id"):
            grouped = defaultdict(list)
            for row in modelrows:
                grouped[row[field]].append(row)
            summary["breakdowns"][field] = {k: _metrics(v) for k, v in sorted(grouped.items())}
        summary["bootstrap"] = _bootstrap(modelrows, seed, bootstrap_samples)
        summaries.append(summary)
        missing = sum(r["invalid_reason"] == "missing_prediction" for r in modelrows)
        duplicate = sum(r["invalid_reason"] == "duplicate_prediction" for r in modelrows)
        completeness.append({"model_key": model, "condition": condition, "expected_cases": len(public),
                             "cases_with_any_record": len(public) - missing, "missing_cases": missing,
                             "duplicate_cases": duplicate, "extra_duplicate_records": sum(max(r["prediction_records"] - 1, 0) for r in modelrows),
                             "execution_error_cases": sum(r["invalid_reason"] == "execution_error" for r in modelrows),
                             "invalid_format_cases": sum(r["invalid_reason"] == "invalid_format" for r in modelrows),
                             "complete_unique_record_set": missing == 0 and duplicate == 0,
                             "all_cases_valid": all(r["format_valid"] for r in modelrows)})
        rows.extend(modelrows)
    # Matched-condition and matched-model differences use the same complete
    # case denominator. Missing responses remain zeroes in both comparisons.
    comparisons = []
    lookup = {(s["model_key"], s["condition"]): [r for r in rows if (r["model_key"], r["condition"]) == (s["model_key"], s["condition"])] for s in summaries}
    keys = sorted(lookup)
    for i, left in enumerate(keys):
        for right in keys[i + 1:]:
            if left[0] != right[0] and left[1] != right[1]:
                continue
            lrows, rrows = lookup[left], lookup[right]
            groups = sorted({r["group_id"] for r in lrows})
            grouped = {g: [(l, r) for l, r in zip(lrows, rrows) if l["group_id"] == g] for g in groups}
            delta = {metric: sum(int(r[metric]) - int(l[metric]) for l, r in zip(lrows, rrows)) / len(public) for metric in ("label_correct", "joint_correct")}
            samples = {metric: [] for metric in delta}
            rng = random.Random(seed)
            for _ in range(bootstrap_samples):
                selected = rng.choices(groups, k=len(groups))
                den = sum(len(grouped[g]) for g in selected)
                for metric in delta:
                    samples[metric].append(sum(int(r[metric]) - int(l[metric]) for g in selected for l, r in grouped[g]) / den)
            comparisons.append({"left": {"model_key": left[0], "condition": left[1]}, "right": {"model_key": right[0], "condition": right[1]},
                                "direction": "right minus left", "source_groups": len(groups), "cases": len(public),
                                "strict_accuracy_difference": delta["label_correct"], "joint_accuracy_difference": delta["joint_correct"],
                                "exploratory_95pct_intervals": {k: [_percentile(v, .025), _percentile(v, .975)] for k, v in samples.items() if v},
                                "samples": bootstrap_samples, "seed": seed, "multiplicity_adjusted": False})
    return {"schema": "phase2_pilot_evaluation_v1", "scope": "Exploratory pilot-development evaluation; not confirmatory held-out performance.",
            "expected_cases_per_model_condition": len(public), "source_groups": len({c["group_id"] for c in public.values()}),
            "scoring": {"strict_denominator": "all expected cases; missing, duplicate, failed and malformed predictions score wrong",
                        "citation_rule": "exact set of required visible evidence IDs for joint correctness; order ignored",
                        "empty_citations": "precision and recall equal 1 when both required and predicted sets are empty",
                        "macro_f1": "fixed three labels, absent undefined class F1 set to zero; invalid predictions count as false negatives",
                        "error_rates": "Unsupported acceptance and excess abstention count explicit valid labels; inspect strict accuracy and completion alongside these rates.",
                        "bootstrap": "whole source-system groups, with every presentation and contrast retained",
                        "parser": "exact two-field JSON only; no repair, fences, coercion or cached parsed field"},
            "summaries": summaries, "completeness": completeness, "unknown_prediction_cases": unknown,
            "paired_comparisons": comparisons, "rows": rows}


def write_reports(result: dict, outdir: str | Path) -> None:
    """Write JSON, case-level CSV and compact per-model CSV."""
    path = Path(outdir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "evaluation.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for filename, records in (("case_scores.csv", result.get("rows", [])),
                              ("model_scores.csv", [{k: v for k, v in s.items() if not isinstance(v, (dict, list))} for s in result.get("summaries", [])]),
                              ("completeness.csv", result.get("completeness", []))):
        with (path / filename).open("w", encoding="utf-8", newline="") as handle:
            if records:
                writer = csv.DictWriter(handle, fieldnames=list(records[0]))
                writer.writeheader()
                for record in records:
                    writer.writerow({k: json.dumps(v, separators=(",", ":")) if isinstance(v, (list, dict)) else v for k, v in record.items()})
