"""Selective evaluation with failure-inclusive denominators and public-only tools.

Tool rejection is a workflow outcome, never a scientific insufficiency answer.
All selector ablations reuse one raw selection and never search for a substitute.
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

MODEL_KEYS = ("qwen", "phi", "smol")
RAW_CONDITIONS = ("direct", "select_evidence")
METHODS = ("direct", "arithmetic_only", "run_only", "full_definition")
VERDICTS = ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")
OPERATIONS = ("value", "mobile_lower", "adsorbate_upper", "none")
FENCE = re.compile(r"\A\s*```(?:json)?[ \t]*\r?\n(.*?)```\s*\Z", re.DOTALL)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-finite JSON constant: " + value)


def parse_response(text, selector=False):
    """Parse exact JSON, optionally inside one entire-output Markdown fence.

    The closing fence may immediately follow JSON. No content extraction,
    coercion, field repair, duplicate removal or case folding is performed.
    """
    if not isinstance(text, str):
        raise ValueError("raw output must be text")
    match = FENCE.fullmatch(text)
    if match:
        text = match.group(1)
    try:
        result = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (TypeError, ValueError) as exc:
        raise ValueError("output is not one exact JSON object") from exc
    wanted = {"evidence_ids", "operation"} if selector else {"verdict", "evidence_ids", "operation"}
    if not isinstance(result, dict) or set(result) != wanted:
        raise ValueError("response has incorrect fields")
    ids, operation = result["evidence_ids"], result["operation"]
    if not isinstance(ids, list) or len(ids) > 1 or any(not isinstance(x, str) or not x or x.strip() != x for x in ids):
        raise ValueError("evidence_ids must contain zero or one nonempty exact string")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate evidence ID")
    if operation not in OPERATIONS:
        raise ValueError("unknown operation")
    if (len(ids) == 0) != (operation == "none"):
        raise ValueError("empty selection and none operation must occur together")
    if not selector:
        if result["verdict"] not in VERDICTS:
            raise ValueError("unknown verdict")
        if (result["verdict"] == "INSUFFICIENT_EVIDENCE") != (len(ids) == 0):
            raise ValueError("insufficiency requires no citation; a decisive verdict requires one")
    return result


def _raw_state(prediction):
    if prediction is None or prediction.get("status") == "missing":
        return "INVALID_MISSING"
    if prediction.get("duplicate_prediction"):
        return "INVALID_DUPLICATE"
    if prediction.get("truncated"):
        return "INVALID_TRUNCATED"
    if prediction.get("status", "ok") != "ok" or prediction.get("error"):
        return "INVALID_EXECUTION"
    return None


def derive_prediction(case, prediction, method):
    """Derive one trace using only public case data and a raw model response.

    Gold labels and permissible proof sets are deliberately absent from this
    function's interface. Only the separately identified oracle searches the
    public packet for a proof.
    """
    from .benchmark import parse_payload, interval_for, judge_interval
    if method not in METHODS:
        raise ValueError("unknown selective method")
    selector = method != "direct"
    trace = {"case_id": case["case_id"], "method": method, "source_condition": "select_evidence" if selector else "direct",
             "disposition": None, "verdict": None, "evidence_ids": [], "operation": "none",
             "interval_A": None, "accepted_numeric": False, "format_valid": False,
             "tool_action": "not_calculated", "raw_output_sha256": None, "request_signature": None}
    invalid = _raw_state(prediction)
    if prediction:
        raw = prediction.get("raw_output")
        trace["raw_output_sha256"] = hashlib.sha256(raw.encode()).hexdigest() if isinstance(raw, str) else None
        trace["request_signature"] = prediction.get("request_signature")
    if invalid:
        trace["disposition"] = invalid
        return trace
    try:
        parsed_response = parse_response(prediction.get("raw_output"), selector=selector)
    except ValueError:
        trace["disposition"] = "INVALID_FORMAT"
        return trace
    trace.update(format_valid=True, evidence_ids=parsed_response["evidence_ids"], operation=parsed_response["operation"])
    parsed = parse_payload(case["model_payload"])
    ids = parsed_response["evidence_ids"]
    if ids:
        candidates = [r for r in parsed["measurements"] if r["evidence_id"] == ids[0]]
        if len(candidates) != 1:
            trace["disposition"] = "INVALID_IDENTIFIER"
            return trace
    if not selector:
        trace["verdict"] = parsed_response["verdict"]
        trace["disposition"] = "SCIENTIFIC_INSUFFICIENT" if not ids else "ACCEPT_NUMERIC"
        trace["accepted_numeric"] = bool(ids)
        trace["tool_action"] = "model_answer"
        return trace
    if not ids:
        trace.update(disposition="REJECT_NO_SELECTION", tool_action="no_selected_record")
        return trace
    try:
        lower, upper = interval_for(parsed, candidates[0], parsed_response["operation"],
                                    validate_scope=method == "full_definition", validate_pair=method != "arithmetic_only")
    except (ValueError, TypeError, KeyError) as exc:
        trace.update(disposition="REJECT_CONTRACT", tool_action="selected_record_rejected", rejection_reason=str(exc))
        return trace
    trace["interval_A"] = [str(lower), str(upper) if upper is not None else None]
    verdict = judge_interval(lower, upper, parsed["threshold_A"], parsed["operator"])
    if verdict is None:
        trace.update(disposition="REJECT_UNRESOLVED", tool_action="selected_bound_does_not_settle_claim")
        return trace
    if verdict not in ("SUPPORTED", "CONTRADICTED"):
        raise ValueError("interval calculator returned a non-numeric verdict")
    trace.update(disposition="ACCEPT_NUMERIC", verdict=verdict, accepted_numeric=True, tool_action="selected_interval_calculated")
    return trace


def _oracle(case):
    from .benchmark import enumerate_proofs
    proofs = enumerate_proofs(case["model_payload"])
    if proofs:
        verdicts = {p["verdict"] for p in proofs}
        if len(verdicts) != 1 or not verdicts <= {"SUPPORTED", "CONTRADICTED"}:
            raise ValueError("public oracle has inconsistent decisive proofs")
        proof = min(proofs, key=lambda p: (p["operation"], tuple(p["evidence_ids"])))
        return {"case_id": case["case_id"], "method": "oracle", "source_condition": "public_payload_oracle",
                "disposition": "ACCEPT_NUMERIC", "verdict": proof["verdict"], "evidence_ids": list(proof["evidence_ids"]),
                "operation": proof["operation"], "interval_A": None, "accepted_numeric": True, "format_valid": True,
                "tool_action": "public_payload_proof_enumeration", "raw_output_sha256": None, "request_signature": None}
    return {"case_id": case["case_id"], "method": "oracle", "source_condition": "public_payload_oracle",
            "disposition": "SCIENTIFIC_INSUFFICIENT", "verdict": "INSUFFICIENT_EVIDENCE", "evidence_ids": [],
            "operation": "none", "interval_A": None, "accepted_numeric": False, "format_valid": True,
            "tool_action": "public_payload_has_no_decisive_proof", "raw_output_sha256": None, "request_signature": None}


def _proof_key(proof):
    return proof["verdict"], tuple(sorted(proof["evidence_ids"])), proof["operation"]


def _score(trace, case, gold, model):
    row = dict(trace)
    answerable = gold["expected"] != "INSUFFICIENT_EVIDENCE"
    label_correct = trace["verdict"] == gold["expected"]
    proof_correct = trace["accepted_numeric"] and _proof_key(trace) in {_proof_key(p) for p in gold["valid_proofs"]}
    scientific = trace["method"] in ("direct", "oracle")
    row.update(model_key=model, expected=gold["expected"], answerable=answerable,
               label_correct=bool(label_correct), licensed_proof_correct=bool(proof_correct),
               correct_numeric_answer=bool(trace["accepted_numeric"] and label_correct and proof_correct),
               bad_numeric_acceptance=bool(trace["accepted_numeric"] and not (label_correct and proof_correct)),
               scientific_threeway_correct=bool(scientific and label_correct and (proof_correct if answerable else trace["disposition"] == "SCIENTIFIC_INSUFFICIENT")),
               scientific_label_correct=bool(scientific and label_correct),
               scientific_evaluation_enabled=scientific,
               group_id=case["group_id"], family=case.get("family", "unknown"), presentation=case.get("presentation", "unknown"),
               target_metric=case.get("target_metric", "unknown"), base_case_id=case.get("base_case_id"),
               contrast_group_id=case.get("contrast_group_id"), valid_proof_count=len(gold["valid_proofs"]))
    return row


def _ratio(n, d):
    return n / d if d else None


def _counts(rows):
    scientific = bool(rows) and rows[0]["scientific_evaluation_enabled"]
    return {"cases": len(rows), "answerable_cases": sum(r["answerable"] for r in rows),
            "insufficient_cases": sum(not r["answerable"] for r in rows),
            "numeric_acceptances": sum(r["accepted_numeric"] for r in rows),
            "answerable_numeric_acceptances": sum(r["answerable"] and r["accepted_numeric"] for r in rows),
            "correct_numeric_answers": sum(r["correct_numeric_answer"] for r in rows),
            "answerable_correct_numeric_answers": sum(r["answerable"] and r["correct_numeric_answer"] for r in rows),
            "unsafe_acceptances_on_insufficient": sum(not r["answerable"] and r["accepted_numeric"] for r in rows),
            "bad_numeric_acceptances": sum(r["bad_numeric_acceptance"] for r in rows),
            "wrong_verdict_numeric_acceptances": sum(r["accepted_numeric"] and not r["label_correct"] for r in rows),
            "correct_verdict_unlicensed_numeric_acceptances": sum(r["accepted_numeric"] and r["label_correct"] and not r["licensed_proof_correct"] for r in rows),
            "answerable_bad_numeric_acceptances": sum(r["answerable"] and r["bad_numeric_acceptance"] for r in rows),
            "answerable_rejections": sum(r["answerable"] and r["disposition"].startswith("REJECT_") for r in rows),
            "answerable_invalid": sum(r["answerable"] and r["disposition"].startswith("INVALID_") for r in rows),
            "answerable_missing": sum(r["answerable"] and r["disposition"] == "INVALID_MISSING" for r in rows),
            "answerable_scientific_abstentions": sum(r["answerable"] and r["disposition"] == "SCIENTIFIC_INSUFFICIENT" for r in rows),
            "format_valid_responses": sum(r["format_valid"] for r in rows),
            "scientific_threeway_correct": sum(r["scientific_threeway_correct"] for r in rows),
            "scientific_label_correct": sum(r["scientific_label_correct"] for r in rows),
            "scientific_enabled": scientific}


def _rates(c):
    n, a, i, accepted = c["cases"], c["answerable_cases"], c["insufficient_cases"], c["numeric_acceptances"]
    return {"numeric_coverage_all": _ratio(accepted, n), "answerable_coverage": _ratio(c["answerable_numeric_acceptances"], a),
            "answerable_correct_verdict_and_proof_rate": _ratio(c["answerable_correct_numeric_answers"], a),
            "unsafe_acceptance_on_insufficient_rate": _ratio(c["unsafe_acceptances_on_insufficient"], i),
            "bad_numeric_acceptance_per_all_cases": _ratio(c["bad_numeric_acceptances"], n),
            "bad_fraction_of_accepted_numeric": _ratio(c["bad_numeric_acceptances"], accepted),
            "conditional_accepted_correctness_with_proof": _ratio(c["correct_numeric_answers"], accepted),
            "conditional_accepted_verdict_accuracy_only": _ratio(accepted - c["wrong_verdict_numeric_acceptances"], accepted),
            "answerable_rejection_rate": _ratio(c["answerable_rejections"], a),
            "answerable_invalid_rate": _ratio(c["answerable_invalid"], a),
            "answerable_loss_rate": _ratio(a - c["answerable_numeric_acceptances"], a),
            "format_rate": _ratio(c["format_valid_responses"], n),
            "scientific_threeway_accuracy_with_proof": _ratio(c["scientific_threeway_correct"], n) if c["scientific_enabled"] else None,
            "scientific_threeway_label_accuracy": _ratio(c["scientific_label_correct"], n) if c["scientific_enabled"] else None}


def _summary(rows):
    c = _counts(rows)
    return {**c, **_rates(c), "dispositions": dict(Counter(r["disposition"] for r in rows))}


def _percentile(values, q):
    values = sorted(values)
    loc = (len(values) - 1) * q
    lo, hi = math.floor(loc), math.ceil(loc)
    return values[lo] if lo == hi else values[lo] * (hi - loc) + values[hi] * (loc - lo)


def _bootstrap(rows, seed, samples):
    grouped = defaultdict(list)
    for r in rows:
        grouped[r["group_id"]].append(r)
    groups = sorted(grouped)
    counts = {g: _counts(grouped[g]) for g in groups}
    values = defaultdict(list)
    rng = random.Random(seed)
    for _ in range(samples):
        chosen = rng.choices(groups, k=len(groups))
        total = {k: sum(counts[g][k] for g in chosen) for k in counts[groups[0]] if k != "scientific_enabled"}
        total["scientific_enabled"] = counts[groups[0]]["scientific_enabled"]
        for metric, value in _rates(total).items():
            if value is not None:
                values[metric].append(value)
    return {"source_groups": len(groups), "samples": samples, "seed": seed,
            "intervals": {k: [_percentile(v, .025), _percentile(v, .975)] for k, v in values.items()},
            "policy": "95% percentile bootstrap of whole source-system groups; every within-group variant retained",
            "undefined_resample_counts": {k: samples - len(values[k]) for k, value in _rates(_counts(rows)).items() if value is not None},
            "multiplicity_adjusted": False}


def _pair_scores(rows):
    contrast, representation = defaultdict(list), defaultdict(list)
    for r in rows:
        if r["contrast_group_id"]:
            contrast[(r["group_id"], r["presentation"], r["contrast_group_id"])].append(r)
        if r["base_case_id"]:
            representation[(r["group_id"], r["base_case_id"])].append(r)
    eligible = [v for v in contrast.values() if len(v) == 2 and {r["expected"] for r in v} == {"SUPPORTED", "CONTRADICTED"}]
    renderings = [v for v in representation.values() if len(v) == 2 and len({r["presentation"] for r in v}) == 2 and len({r["expected"] for r in v}) == 1]
    answerable = [v for v in renderings if all(r["answerable"] for r in v)]
    scientific = bool(rows) and rows[0]["scientific_evaluation_enabled"]
    return {"eligible_contrast_pairs": len(eligible),
            "contrast_both_numeric_accepted": sum(all(r["accepted_numeric"] for r in v) for v in eligible),
            "contrast_both_correct_with_proof": sum(all(r["correct_numeric_answer"] for r in v) for v in eligible),
            "contrast_both_correct_with_proof_rate": _ratio(sum(all(r["correct_numeric_answer"] for r in v) for v in eligible), len(eligible)),
            "eligible_representation_pairs": len(renderings), "answerable_representation_pairs": len(answerable),
            "representation_both_numeric_accepted_answerable": sum(all(r["accepted_numeric"] for r in v) for v in answerable),
            "representation_both_correct_with_proof_answerable": sum(all(r["correct_numeric_answer"] for r in v) for v in answerable),
            "representation_both_correct_with_proof_answerable_rate": _ratio(sum(all(r["correct_numeric_answer"] for r in v) for v in answerable), len(answerable)),
            "representation_both_scientific_correct_all_rate": _ratio(sum(all(r["scientific_threeway_correct"] for r in v) for v in renderings), len(renderings)) if scientific else None}


def _paired_effect(control, full):
    left = {r["case_id"]: r for r in control}
    right = {r["case_id"]: r for r in full}
    if set(left) != set(right):
        raise ValueError("paired methods do not share a complete case denominator")
    pairs = [(left[k], right[k]) for k in sorted(left)]
    answerable = sum(a["answerable"] for a, _ in pairs)
    control_bad = sum(a["bad_numeric_acceptance"] for a, _ in pairs)
    prevented = sum(a["bad_numeric_acceptance"] and not b["accepted_numeric"] for a, b in pairs)
    lost = sum(a["answerable"] and a["accepted_numeric"] and not b["accepted_numeric"] for a, b in pairs)
    new_bad = sum(b["bad_numeric_acceptance"] and not a["bad_numeric_acceptance"] for a, b in pairs)
    return {"cases": len(pairs), "answerable_cases": answerable, "control_bad_numeric_acceptances": control_bad,
            "control_answerable_numeric_acceptances": sum(a["answerable"] and a["accepted_numeric"] for a, _ in pairs),
            "method_answerable_numeric_acceptances": sum(b["answerable"] and b["accepted_numeric"] for _, b in pairs),
            "control_answerable_correct_numeric_answers": sum(a["answerable"] and a["correct_numeric_answer"] for a, _ in pairs),
            "method_answerable_correct_numeric_answers": sum(b["answerable"] and b["correct_numeric_answer"] for _, b in pairs),
            "bad_numeric_acceptances_prevented": prevented, "new_bad_numeric_acceptances": new_bad,
            "lost_answerable_numeric_acceptances": lost,
            "lost_control_correct_numeric_answers": sum(a["correct_numeric_answer"] and not b["accepted_numeric"] for a, b in pairs),
            "prevention_per_all_cases": _ratio(prevented, len(pairs)),
            "prevented_fraction_of_control_bad_acceptances": _ratio(prevented, control_bad),
            "lost_answerable_coverage": _ratio(lost, answerable),
            "answerable_coverage_difference": _ratio(sum(b["answerable"] and b["accepted_numeric"] for _, b in pairs) - sum(a["answerable"] and a["accepted_numeric"] for a, _ in pairs), answerable),
            "answerable_correct_with_proof_difference": _ratio(sum(b["answerable"] and b["correct_numeric_answer"] for _, b in pairs) - sum(a["answerable"] and a["correct_numeric_answer"] for a, _ in pairs), answerable)}


def _paired_bootstrap(control, full, seed, samples):
    cg, fg = defaultdict(list), defaultdict(list)
    for row in control:cg[row["group_id"]].append(row)
    for row in full:fg[row["group_id"]].append(row)
    groups = sorted(cg)
    # Store group-level counts once. Ratios are recomputed after resampling.
    stats = {g: _paired_effect(cg[g], fg[g]) for g in groups}
    count_fields = ("cases", "answerable_cases", "control_bad_numeric_acceptances", "bad_numeric_acceptances_prevented", "new_bad_numeric_acceptances", "lost_answerable_numeric_acceptances", "lost_control_correct_numeric_answers", "control_answerable_numeric_acceptances", "method_answerable_numeric_acceptances", "control_answerable_correct_numeric_answers", "method_answerable_correct_numeric_answers")
    vals = defaultdict(list)
    rng = random.Random(seed)
    for _ in range(samples):
        chosen = rng.choices(groups, k=len(groups))
        total = {k: sum(stats[g][k] for g in chosen) for k in count_fields}
        rates = {"prevention_per_all_cases": _ratio(total["bad_numeric_acceptances_prevented"], total["cases"]),
                 "prevented_fraction_of_control_bad_acceptances": _ratio(total["bad_numeric_acceptances_prevented"], total["control_bad_numeric_acceptances"]),
                 "lost_answerable_coverage": _ratio(total["lost_answerable_numeric_acceptances"], total["answerable_cases"]),
                 "answerable_coverage_difference": _ratio(total["method_answerable_numeric_acceptances"] - total["control_answerable_numeric_acceptances"], total["answerable_cases"]),
                 "answerable_correct_with_proof_difference": _ratio(total["method_answerable_correct_numeric_answers"] - total["control_answerable_correct_numeric_answers"], total["answerable_cases"])}
        for k, value in rates.items():
            if value is not None:vals[k].append(value)
    return {"source_groups": len(groups), "samples": samples, "seed": seed,
            "intervals": {k: [_percentile(v, .025), _percentile(v, .975)] for k, v in vals.items()},
            "policy": "Paired whole-source-group percentile bootstrap; selection sharing is identified separately",
            "multiplicity_adjusted": False}


def evaluate(public, gold, predictions, seed=20261021, bootstrap_samples=1000):
    """Score fixed models and methods, including absent raw model combinations."""
    from .benchmark import parse_payload
    if type(seed) is not int or seed < 0 or type(bootstrap_samples) is not int or bootstrap_samples < 0:
        raise ValueError("seed and bootstrap_samples must be nonnegative integer settings")
    if not isinstance(public, list) or not public:
        raise ValueError("public must be a nonempty list")
    cases, answers = {}, {}
    for case in public:
        cid = case.get("case_id")
        if not isinstance(cid, str) or not cid or cid.strip() != cid or cid in cases or not isinstance(case.get("group_id"), str) or not case["group_id"] or case["group_id"].strip() != case["group_id"]:
            raise ValueError("invalid or duplicate public identity")
        parse_payload(case["model_payload"])
        cases[cid] = case
    for answer in gold:
        cid = answer.get("case_id")
        if cid in answers or answer.get("expected") not in VERDICTS or not isinstance(answer.get("valid_proofs"), list):
            raise ValueError("invalid or duplicate gold answer")
        proofkeys = []
        for proof in answer["valid_proofs"]:
            parsed = parse_response(json.dumps(proof))
            if parsed["verdict"] != answer["expected"] or parsed["verdict"] == "INSUFFICIENT_EVIDENCE":
                raise ValueError("gold proof does not establish the gold decisive verdict")
            proofkeys.append(_proof_key(parsed))
        if len(proofkeys) != len(set(proofkeys)) or (answer["expected"] != "INSUFFICIENT_EVIDENCE") != bool(proofkeys):
            raise ValueError("gold requires all distinct decisive witnesses, or no proofs for insufficiency")
        answers[cid] = answer
    if set(cases) != set(answers):raise ValueError("public and gold IDs differ")
    indexed = defaultdict(list)
    unexpected = []
    for prediction in predictions:
        key = (prediction.get("model_key"), prediction.get("condition"), prediction.get("case_id"))
        if key[0] not in MODEL_KEYS or key[1] not in RAW_CONDITIONS or key[2] not in cases:
            unexpected.append({"model_key": key[0], "condition": key[1], "case_id": key[2]})
        else:indexed[key].append(prediction)
    rows, completeness = [], []
    for model in MODEL_KEYS:
        for condition in RAW_CONDITIONS:
            counts = Counter()
            for cid in sorted(cases):
                supplied = indexed[(model, condition, cid)]
                counts["expected_cases"] += 1
                if not supplied:
                    prediction = None
                elif len(supplied) > 1:
                    prediction = {"duplicate_prediction": True, "status": "ok"}
                    counts["extra_duplicate_records"] += len(supplied) - 1
                else:prediction = supplied[0]
                raw_error = _raw_state(prediction)
                if raw_error:counts[raw_error] += 1
                else:
                    try:parse_response(prediction.get("raw_output"), selector=condition == "select_evidence");counts["raw_contract_valid"] += 1
                    except ValueError:counts["INVALID_FORMAT"] += 1
                methods = ("direct",) if condition == "direct" else METHODS[1:]
                for method in methods:
                    trace = derive_prediction(cases[cid], prediction, method)
                    rows.append(_score(trace, cases[cid], answers[cid], model))
            completeness.append({"model_key": model, "condition": condition, **dict(counts),
                                 "missing_cases": counts["INVALID_MISSING"], "duplicate_cases": counts["INVALID_DUPLICATE"],
                                 "truncated_cases": counts["INVALID_TRUNCATED"], "execution_error_cases": counts["INVALID_EXECUTION"],
                                 "invalid_format_cases": counts["INVALID_FORMAT"], "valid_contract_cases": counts["raw_contract_valid"],
                                 "all_expected_unique_records": all(len(indexed[(model, condition, cid)]) == 1 and indexed[(model, condition, cid)][0].get("status") != "missing" for cid in cases),
                                 "all_contract_valid": counts["raw_contract_valid"] == len(cases)})
    for cid in sorted(cases):rows.append(_score(_oracle(cases[cid]), cases[cid], answers[cid], "payload_oracle"))
    grouped = defaultdict(list)
    for row in rows:grouped[(row["model_key"], row["method"])].append(row)
    summaries = []
    for (model, method), methodrows in sorted(grouped.items()):
        summary = {"model_key": model, "method": method, **_summary(methodrows), "paired_cases": _pair_scores(methodrows), "bootstrap": _bootstrap(methodrows, seed, bootstrap_samples)}
        breakdowns = {}
        for field in ("family", "presentation", "target_metric", "group_id"):
            bins = defaultdict(list)
            for row in methodrows:bins[row[field]].append(row)
            breakdowns[field] = {key: _summary(value) for key, value in sorted(bins.items())}
        summary["breakdowns"] = breakdowns
        summaries.append(summary)
    comparisons = []
    for model in MODEL_KEYS:
        full = grouped[(model, "full_definition")]
        for control in ("run_only", "arithmetic_only", "direct"):
            source = grouped[(model, control)]
            comparisons.append({"model_key": model, "control": control, "method": "full_definition",
                                "comparison_role": "primary" if control == "run_only" else "exploratory",
                                "same_selector_outputs": control != "direct", **_paired_effect(source, full),
                                "bootstrap": _paired_bootstrap(source, full, seed, bootstrap_samples)})
    return {"schema": "scientific_scope_selective_evaluation_v1", "expected_cases_per_model_method": len(cases),
            "source_groups": len({c["group_id"] for c in cases.values()}),
            "scoring": {"denominator": "Every expected case for all three fixed models, including missing, duplicate, truncated, malformed and failed responses",
                        "numeric_acceptance": "A contract-valid decisive answer citing one visible identifier and one operation, or a conclusive selected-interval calculation; malformed, unknown-ID, truncated and failed responses are invalid rather than accepted numbers",
                        "bad_numeric_acceptance": "An accepted numerical verdict lacks the correct verdict plus a licensed proof; wrong-verdict and correct-verdict-but-unlicensed counts are reported separately",
                        "scientific_insufficiency": "A direct/oracle scientific verdict; never inferred from a workflow rejection",
                        "proofs": "Any gold-licensed evidence-ID and operation witness is accepted; no single canonical-ID requirement",
                        "primary_endpoint": "Bad numerical acceptances prevented versus answerable coverage lost: full_definition against run_only on identical selections",
                        "scientific_threeway_accuracy": "Only direct and public-payload oracle; never compare guard rejection as a correct insufficiency answer",
                        "oracle": "Transparent deterministic proof enumeration of the public payload; strong baseline, not a novel method",
                        "zero_unsafe_warning": "Exact full-scope validation plus deterministic arithmetic can enforce zero unsafe acceptance by construction on this controlled family; report rejection and coverage costs",
                        "bootstrap": "Whole source-system groups retain all correlated cases and presentations; paired selectors share raw predictions"},
            "summaries": summaries, "completeness": completeness, "unexpected_predictions": unexpected,
            "paired_comparisons": comparisons, "rows": rows}


def write_reports(result, outdir):
    folder = Path(outdir);folder.mkdir(parents=True, exist_ok=True)
    (folder / "evaluation.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (folder / "paired_comparisons.json").write_text(json.dumps(result["paired_comparisons"], indent=2, allow_nan=False) + "\n", encoding="utf-8")
    compact = [{k: v for k, v in s.items() if not isinstance(v, (dict, list))} for s in result["summaries"]]
    for name, records in (("method_scores.csv", compact), ("case_scores.csv", result["rows"]), ("completeness.csv", result["completeness"])):
        with (folder / name).open("w", newline="", encoding="utf-8") as stream:
            if not records:continue
            keys = list(dict.fromkeys(k for record in records for k in record))
            writer = csv.DictWriter(stream, fieldnames=keys);writer.writeheader()
            for record in records:writer.writerow({k: json.dumps(v, separators=(",", ":")) if isinstance(v, (list, dict)) else v for k, v in record.items()})
