"""Construct frozen metric-scope cases without putting answers in model input.

``build_cases(pair_records, thresholds, margin_A=0.005, seed=20261019)``
returns ``(public_cases, gold_cases, summary)``. A public record has audit
metadata and a ``model_payload`` containing only a claim and evidence packet.
Only ``model_payload`` should be sent to a model. Gold records are separate.
This Phase 1 construction audits data and evaluation feasibility; its explicit
metric descriptions admit template/field-matching shortcuts and do not by
themselves establish a novel or difficult reasoning benchmark.

For each pair, threshold, and eligible target metric, five cases are produced:
metric_scope, missing_relevant_measurement, missing_irrelevant_measurement,
unit_conversion, and wrong_run: 15 cases per fully eligible pair/threshold.
The threshold in a unit-conversion claim stays in angstrom, while all supplied
measurements are expressed in nm. Missing-irrelevant cases remove one other
metric using a fixed cyclic rule independent of the answer.

Inputs must already have system/group IDs and a split. Physical conventions
must be supplied in metric_definitions; this module never infers them from
forces, energies, convergence flags, or an experiment's name.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any


METRICS = (
    ("mobile_rmsd", "mobile_rmsd_A", "mobile-atom coordinate RMSD"),
    ("adsorbate_frame_rmsd", "adsorbate_frame_rmsd_A", "adsorbate RMSD in the specified surface frame"),
    ("internal_rmsd", "internal_rmsd_A", "rigid-aligned internal adsorbate RMSD"),
)
FAMILIES = (
    "metric_scope",
    "missing_relevant_measurement",
    "missing_irrelevant_measurement",
    "unit_conversion",
    "wrong_run",
)
SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"


def _number(value: Any, name: str, *, nonnegative: bool = True) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not result.is_finite() or not math.isfinite(float(result)):
        raise ValueError(f"{name} must be finite")
    if nonnegative and result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _identifier(value: Any, name: str) -> str:
    if isinstance(value, bool) or value is None or not isinstance(value, (str, int)):
        raise ValueError(f"{name} must be a nonempty string or integer ID")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be nonempty")
    return text


def _definition(record: dict, metric_id: str, field: str) -> dict:
    definitions = record.get("metric_definitions", {})
    source = definitions.get(metric_id, definitions.get(field))
    if not isinstance(source, dict):
        raise ValueError(f"{record['pair_id']}: missing definition for {metric_id}")
    result = {}
    aliases = {
        "atom_subset": ("atom_subset", "atom_indices"),
        "frame": ("frame", "coordinate_frame"),
        "alignment": ("alignment", "alignment_procedure"),
        "pbc": ("pbc", "periodic_boundary", "periodic_boundary_treatment", "pbc_treatment", "periodic_treatment"),
    }
    for canonical, choices in aliases.items():
        found = next((source[key] for key in choices if key in source), None)
        if found is None or found == "" or found == [] or found == {}:
            raise ValueError(f"{record['pair_id']}: {metric_id} requires explicit {canonical}")
        result[canonical] = copy.deepcopy(found)
    supplied_unit = source.get("units", source.get("unit", "angstrom"))
    if str(supplied_unit).strip().lower() not in ("angstrom", "angstroms", "å", "a", "ångström"):
        raise ValueError(f"{record['pair_id']}: {metric_id} definition must use angstrom units")
    result["units"] = "angstrom"
    for key in ("atom_indices", "correspondence", "weighting", "cell_reference",
                "periodic_treatment", "periodic_boundary_treatment"):
        if key in source:
            result[key] = copy.deepcopy(source[key])
    # Whitelist structural definitions: root labels/rationales are never copied.
    return result


def _case_id(seed: int, pair_id: str, threshold: Decimal, target: str, family: str) -> str:
    key = json.dumps([seed, pair_id, str(threshold.normalize()), target, family], separators=(",", ":"))
    return "gs_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def build_cases(
    pair_records: list[dict],
    thresholds: list[float],
    margin_A: float = 0.005,
    seed: int = 20261019,
) -> tuple[list[dict], list[dict], dict]:
    """Build five diagnostic families for every usable metric/threshold.

    Required input fields: pair_id, system_id, group_id, split, origin,
    measurements, metric_definitions, and provenance. Measurements use the
    three ``*_rmsd_A`` fields in METRICS. Definitions are keyed by those fields
    or suffix-free metric IDs and require atom_subset, frame, alignment and
    pbc (supported aliases are documented in _definition). Origins are
    measured_endpoint_pair or synthetic_control. Provenance must name
    workflow_a and workflow_b; source hashes and run IDs are retained if given.

    Targets at or within margin_A of a threshold are excluded from *all*
    families. Other targets on the same pair remain eligible. A repeated pair
    ID, repeated threshold, or conflicting group split is an error. Inputs are
    never mutated. IDs/order are deterministic for a fixed seed, independent
    of the ordering of input records and thresholds.
    """
    if not isinstance(pair_records, list) or not isinstance(thresholds, list) or not thresholds:
        raise ValueError("pair_records and nonempty thresholds must be lists")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    margin = _number(margin_A, "margin_A")
    threshold_values = [_number(value, "threshold") for value in thresholds]
    if any(value <= 0 for value in threshold_values):
        raise ValueError("thresholds must be positive")
    if len(set(threshold_values)) != len(threshold_values):
        raise ValueError("thresholds must not repeat")
    threshold_values.sort()
    prepared = []
    seen_pairs = set()
    group_splits: dict[str, str] = {}
    for raw in pair_records:
        if not isinstance(raw, dict):
            raise ValueError("each pair record must be a dictionary")
        record = copy.deepcopy(raw)
        for key in ("pair_id", "system_id", "group_id", "split"):
            record[key] = _identifier(record.get(key), key)
        pair_id, group_id, split = record["pair_id"], record["group_id"], record["split"]
        if pair_id in seen_pairs:
            raise ValueError(f"duplicate pair_id: {pair_id}")
        seen_pairs.add(pair_id)
        if group_id in group_splits and group_splits[group_id] != split:
            raise ValueError(f"group {group_id} appears in more than one split")
        group_splits[group_id] = split
        if record.get("origin") not in ("measured_endpoint_pair", "synthetic_control"):
            raise ValueError(f"{pair_id}: unsupported origin")
        provenance = record.get("provenance")
        if not isinstance(provenance, dict) or any(not provenance.get(k) for k in ("workflow_a", "workflow_b")):
            raise ValueError(f"{pair_id}: provenance must explicitly identify both workflows")
        values, evidence = {}, []
        for metric_id, field, display_name in METRICS:
            value = _number(record.get("measurements", {}).get(field), f"{pair_id}.{field}")
            values[metric_id] = value
            evidence.append({
                "evidence_id": f"{pair_id}::{metric_id}",
                "pair_id": pair_id,
                "metric_id": metric_id,
                "display_name": display_name,
                "value": float(value),
                "unit": "angstrom",
                "definition": _definition(record, metric_id, field),
            })
        safe_provenance = {key: copy.deepcopy(provenance[key]) for key in (
            "workflow_a", "workflow_b", "source_hashes", "run_id_a", "run_id_b",
        ) if key in provenance}
        prepared.append((record, values, evidence, safe_provenance))
    prepared.sort(key=lambda item: item[0]["pair_id"])

    public, gold, skipped, contrasts = [], [], [], []
    for record, values, evidence, provenance in prepared:
        pair_id = record["pair_id"]
        for threshold in threshold_values:
            eligible = {metric_id for metric_id, value in values.items() if abs(value - threshold) > margin}
            skipped.extend({"pair_id": pair_id, "metric_id": metric_id, "threshold_A": float(threshold)}
                           for metric_id in values if metric_id not in eligible)
            base_case_ids = {}
            for index, (target_id, _, _) in enumerate(METRICS):
                if target_id not in eligible:
                    continue
                target_evidence = evidence[index]
                verdict = SUPPORTED if values[target_id] <= threshold else CONTRADICTED
                other_id = METRICS[(index + 1) % len(METRICS)][0]
                claim = (f"For endpoint pair {pair_id}, the {target_evidence['display_name']}, using the exact "
                         f"atom subset, frame, alignment and periodic-boundary treatment defined in the "
                         f"evidence, is at most {format(threshold, 'f')} angstrom.")
                for family in FAMILIES:
                    case_id = _case_id(seed, pair_id, threshold, target_id, family)
                    packet = {"pair_id": pair_id, "measurements": copy.deepcopy(evidence),
                              "provenance": copy.deepcopy(provenance)}
                    expected, required = verdict, [target_evidence["evidence_id"]]
                    case_origin = record["origin"]
                    condition_kind = {
                        "metric_scope": "unaltered_evidence",
                        "missing_relevant_measurement": "relevant_evidence_field_removal",
                        "missing_irrelevant_measurement": "irrelevant_evidence_field_removal",
                        "unit_conversion": "unit_reexpression",
                        "wrong_run": "synthetic_pair_identity_reassignment",
                    }[family]
                    reason = (f"{target_evidence['evidence_id']} reports {values[target_id]} angstrom; "
                              f"the requested bound is <= {threshold} angstrom.")
                    if family == "missing_relevant_measurement":
                        packet["measurements"] = [m for m in packet["measurements"] if m["metric_id"] != target_id]
                        expected, required = INSUFFICIENT, []
                        reason = f"No supplied measurement reports {target_id} for pair {pair_id}; other metrics cannot substitute."
                    elif family == "missing_irrelevant_measurement":
                        packet["measurements"] = [m for m in packet["measurements"] if m["metric_id"] != other_id]
                    elif family == "unit_conversion":
                        for item in packet["measurements"]:
                            item["value"] = float(values[item["metric_id"]] / Decimal(10))
                            item["unit"] = "nm"
                            item["definition"]["units"] = "nm"
                        reason += " The evidence is restated in nm; 1 nm = 10 angstrom."
                    elif family == "wrong_run":
                        case_origin = "synthetic_control"
                        unrelated = f"unrelated_to::{pair_id}"
                        while unrelated in seen_pairs:
                            unrelated = "unrelated_to::" + unrelated
                        packet["pair_id"] = unrelated
                        for item in packet["measurements"]:
                            item["pair_id"] = unrelated
                            item["evidence_id"] = f"{unrelated}::{item['metric_id']}"
                        # Source/run identifiers from the original pair cannot be carried
                        # into the deliberately unrelated evidence packet.
                        packet["provenance"] = {"workflow_a": provenance["workflow_a"],
                                                "workflow_b": provenance["workflow_b"],
                                                "run_id_a": f"{unrelated}::a", "run_id_b": f"{unrelated}::b"}
                        expected, required = INSUFFICIENT, []
                        reason = f"All supplied measurements concern {unrelated}, not requested pair {pair_id}."
                    public.append({
                        "case_id": case_id, "family": family, "origin": case_origin,
                        "source_origin": record["origin"], "condition_kind": condition_kind,
                        "evidence_packet_modified": family != "metric_scope",
                        "source_coordinates_modified": False,
                        "pair_id": pair_id, "system_id": record["system_id"],
                        "pair_group_id": record["group_id"], "split": record["split"],
                        "target": {"pair_id": pair_id, "metric_id": target_id, "operator": "<=",
                                   "threshold": float(threshold), "unit": "angstrom"},
                        "model_payload": {"claim": claim, "evidence_packet": packet},
                    })
                    gold.append({
                        "case_id": case_id, "family": family, "origin": case_origin,
                        "source_origin": record["origin"], "condition_kind": condition_kind,
                        "pair_id": pair_id, "pair_group_id": record["group_id"], "split": record["split"],
                        "expected": expected, "required_evidence_ids": required, "reason": reason,
                    })
                    if family == "metric_scope":
                        base_case_ids[target_id] = case_id
            if {"mobile_rmsd", "internal_rmsd"} <= eligible:
                mobile_supported = values["mobile_rmsd"] <= threshold
                internal_supported = values["internal_rmsd"] <= threshold
                if mobile_supported != internal_supported:
                    contrast_id = _case_id(seed, pair_id, threshold, "mobile_vs_internal", "contrast")
                    contrasts.append({"contrast_group_id": contrast_id, "pair_id": pair_id,
                                      "pair_group_id": record["group_id"], "split": record["split"],
                                      "origin": record["origin"], "threshold_A": float(threshold),
                                      "case_ids": [base_case_ids["mobile_rmsd"], base_case_ids["internal_rmsd"]]})
    contrast_by_case = {case_id: group["contrast_group_id"] for group in contrasts for case_id in group["case_ids"]}
    for item in gold:
        if item["case_id"] in contrast_by_case:
            item["contrast_group_id"] = contrast_by_case[item["case_id"]]
    if len({item["case_id"] for item in public}) != len(public):
        raise ValueError("case ID collision")
    order = list(range(len(public)))
    random.Random(seed).shuffle(order)
    public, gold = [public[i] for i in order], [gold[i] for i in order]
    by_family_label = defaultdict(Counter)
    for item in gold:
        by_family_label[item["family"]][item["expected"]] += 1
    summary = {
        "seed": seed, "thresholds_A": [float(value) for value in threshold_values], "margin_A": float(margin),
        "n_pair_records": len(pair_records), "n_cases": len(public),
        "by_family": dict(sorted(Counter(item["family"] for item in gold).items())),
        "by_label": dict(sorted(Counter(item["expected"] for item in gold).items())),
        "by_origin": dict(sorted(Counter(item["origin"] for item in gold).items())),
        "by_source_origin": dict(sorted(Counter(item["source_origin"] for item in gold).items())),
        "by_condition_kind": dict(sorted(Counter(item["condition_kind"] for item in gold).items())),
        "by_split": dict(sorted(Counter(item["split"] for item in gold).items())),
        "by_family_label": {key: dict(sorted(counts.items())) for key, counts in sorted(by_family_label.items())},
        "skipped_near_threshold": skipped, "n_contrast_groups": len(contrasts), "contrast_groups": contrasts,
        "model_input_field": "model_payload",
        "template_shortcut_risk": True,
        "template_shortcut_note": (
            "Phase 1 claims and evidence use explicit, systematically related metric descriptions. "
            "A deterministic metric selector and threshold checker may solve these templates; "
            "accuracy alone does not demonstrate scientific reasoning or benchmark novelty."
        ),
    }
    return public, gold, summary
