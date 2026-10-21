"""Build a balanced development pilot and transparent payload-only baselines.

The thresholds are controlled task definitions derived from the development
measurements. They are not claims about acceptable chemical error. All cases
remain development data; variants of a source system are never independent.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any

METRICS = (
    ("mobile_rmsd", "mobile-atom coordinate RMSD"),
    ("adsorbate_frame_rmsd", "adsorbate RMSD in the specified surface frame"),
    ("internal_rmsd", "rigid-aligned internal adsorbate RMSD"),
)
FAMILIES = ("metric_scope", "unit_conversion", "missing_irrelevant_measurement")
VERDICTS = ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")
QUANTITY_CONVENTION = (
    "Each value is the square root of the mean squared coordinate-residual norm over its selected atoms, "
    "after the stated alignment and periodic handling."
)
_NAME_TO_METRIC = {name: metric for metric, name in METRICS}


def _hash(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()).hexdigest()[:24]


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite number")
    if value < 0:
        raise ValueError(f"{field} must be nonnegative")
    return float(value)


def _indices(value: Any, field: str) -> list[int]:
    if not isinstance(value, list) or not value or any(isinstance(i, bool) or not isinstance(i, int) or i < 0 for i in value):
        raise ValueError(f"{field} must be a nonempty atom-index list")
    if len(set(value)) != len(value):
        raise ValueError(f"{field} has repeated atom indices")
    return sorted(value)


def _definition(record: dict, metric: str) -> dict:
    definitions = record.get("metric_definitions", {})
    source = definitions.get(metric + "_A", definitions.get(metric))
    if not isinstance(source, dict):
        raise ValueError(f"{record['pair_id']}: missing definition {metric}")
    result = {
        "atom_indices": _indices(source.get("atom_indices", source.get("atom_subset")), metric + ".atom_indices"),
        "frame": source.get("frame"),
        "alignment": source.get("alignment"),
        "periodic_treatment": source.get("periodic_treatment"),
        "weighting": source.get("weighting"),
        "pbc": source.get("pbc"),
    }
    for key in ("frame", "alignment", "periodic_treatment", "weighting"):
        _id(result[key], metric + "." + key)
        if "\n" in result[key] or "\r" in result[key]:
            raise ValueError("Definition text must stay on one line")
    if not isinstance(result["pbc"], list) or len(result["pbc"]) != 3 or any(type(v) is not bool for v in result["pbc"]):
        raise ValueError("Definition pbc must be three booleans")
    return copy.deepcopy(result)


def _atom_sets(record: dict) -> dict:
    definitions = record.get("metric_definitions", {})
    anchor = definitions.get("anchor_rmsd_A", definitions.get("anchor_rmsd"))
    if not isinstance(anchor, dict):
        raise ValueError(f"{record['pair_id']}: missing anchor definition")
    sets = {
        "mobile": _definition(record, "mobile_rmsd")["atom_indices"],
        "adsorbate": _definition(record, "adsorbate_frame_rmsd")["atom_indices"],
        "anchors": _indices(anchor.get("atom_indices", anchor.get("atom_subset")), "anchors"),
    }
    if not set(sets["adsorbate"]).issubset(sets["mobile"]):
        raise ValueError("Adsorbate mask must be a subset of the mobile mask")
    if set(sets["anchors"]) & set(sets["mobile"]):
        raise ValueError("Anchor and mobile masks must be disjoint")
    if _definition(record, "internal_rmsd")["atom_indices"] != sets["adsorbate"]:
        raise ValueError("Internal RMSD must use the adsorbate atom mask")
    return sets


def _render_report(packet: dict) -> str:
    sets = packet["atom_sets"]
    lines = [
        packet["quantity_convention"],
        "Atom sets used in this packet:",
        "Mobile atom indices: " + json.dumps(sets["mobile"]) + ".",
        "Adsorbate atom indices: " + json.dumps(sets["adsorbate"]) + ".",
        "Fixed anchor atom indices: " + json.dumps(sets["anchors"]) + ".",
        "The following records are supplied independently; use their endpoint-pair identifiers.",
    ]
    for item in packet["measurements"]:
        d = item["definition"]
        lines.append(
            f"Evidence ID: {item['evidence_id']}. Endpoint pair: {item['pair_id']}. "
            f"Value: {format(item['value'], '.17g')} {item['unit']}. "
            f"Selected atom indices: {json.dumps(d['atom_indices'])}. "
            f"Coordinate frame: {json.dumps(d['frame'])}. "
            f"Alignment: {json.dumps(d['alignment'])}. "
            f"Periodic treatment: {json.dumps(d['periodic_treatment'])}. "
            f"Periodic axes: {json.dumps(d['pbc'])}. "
            f"Weighting: {json.dumps(d['weighting'])}."
        )
    if packet.get("measurement_definitions"):
        lines.append("Definitions for the requested endpoint pair are supplied without measured values:")
        for d in packet["measurement_definitions"]:
            lines.append(
                f"Endpoint pair: {packet['requested_pair_id']}. "
                f"Selected atom indices: {json.dumps(d['atom_indices'])}. "
                f"Coordinate frame: {json.dumps(d['frame'])}. "
                f"Alignment: {json.dumps(d['alignment'])}. "
                f"Periodic treatment: {json.dumps(d['periodic_treatment'])}. "
                f"Periodic axes: {json.dumps(d['pbc'])}. "
                f"Weighting: {json.dumps(d['weighting'])}."
            )
    return "\n".join(lines)


_CLAIM_RE = re.compile(
    r"For endpoint pair (P_[0-9a-f]{24}), the (.+), with equal atom weights and the supplied atom sets, "
    r"is (at most|at least) ([0-9.eE+\-]+) angstrom\."
)
_REPORT_RECORD_RE = re.compile(
    r'Evidence ID: (E_[0-9a-f]{24})\. Endpoint pair: (P_[0-9a-f]{24})\. '
    r'Value: ([0-9.eE+\-]+) (angstrom|nm)\. '
    r'Selected atom indices: (\[[^\n]*?\])\. '
    r'Coordinate frame: ("(?:[^"\\]|\\.)*")\. '
    r'Alignment: ("(?:[^"\\]|\\.)*")\. '
    r'Periodic treatment: ("(?:[^"\\]|\\.)*")\. '
    r'Periodic axes: (\[[^\n]*?\])\. '
    r'Weighting: ("(?:[^"\\]|\\.)*")\.'
)


def parse_payload(payload: dict) -> dict:
    """Parse the public pilot format without accessing public audit or gold fields."""
    if not isinstance(payload, dict):
        raise ValueError("Model payload must be a dictionary")
    match = _CLAIM_RE.fullmatch(payload.get("claim", ""))
    if not match or match.group(2) not in _NAME_TO_METRIC:
        raise ValueError("Unrecognized development claim format")
    pair, display, operator, threshold = match.groups()
    if "evidence_packet" in payload:
        packet = copy.deepcopy(payload["evidence_packet"])
    elif "evidence_report" in payload:
        report = payload["evidence_report"]
        sets = {}
        for key, prefix in (("mobile", "Mobile"), ("adsorbate", "Adsorbate"), ("anchors", "Fixed anchor")):
            m = re.search(r"^" + prefix + r" atom indices: (\[[^\n]*?\])\.$", report, re.MULTILINE)
            if not m:
                raise ValueError("Report lacks the declared atom sets")
            sets[key] = json.loads(m.group(1))
        measurements = []
        for m in _REPORT_RECORD_RE.finditer(report):
            evidence_id, measurement_pair, value, unit, indices, frame, alignment, periodic, pbc, weighting = m.groups()
            measurements.append({
                "evidence_id": evidence_id, "pair_id": measurement_pair,
                "value": float(value), "unit": unit,
                "definition": {"atom_indices": json.loads(indices), "frame": json.loads(frame),
                               "alignment": json.loads(alignment), "periodic_treatment": json.loads(periodic),
                               "pbc": json.loads(pbc), "weighting": json.loads(weighting)},
            })
        if len(measurements) != len(re.findall(r"Evidence ID:", report)):
            raise ValueError("A report measurement could not be parsed")
        packet = {"atom_sets": sets, "measurements": measurements}
    else:
        raise ValueError("Payload lacks evidence")
    return {"pair_id": pair, "metric_id": _NAME_TO_METRIC[display],
            "operator": "<=" if operator == "at most" else ">=",
            "threshold_A": Decimal(threshold), "atom_sets": packet["atom_sets"],
            "measurements": packet["measurements"]}


def _matches_definition(item: dict, target: str, atom_sets: dict) -> bool:
    d = item.get("definition", {})
    mask = atom_sets["mobile"] if target == "mobile_rmsd" else atom_sets["adsorbate"]
    if sorted(d.get("atom_indices", [])) != sorted(mask) or d.get("weighting") != "equal weight per selected atom":
        return False
    if not isinstance(d.get("pbc"), list) or len(d["pbc"]) != 3 or any(type(x) is not bool for x in d["pbc"]):
        return False
    if target == "internal_rmsd":
        return (d.get("frame") == "independent molecular centroids"
                and d.get("alignment") == "proper Kabsch rotation plus translation; no reflection"
                and d.get("periodic_treatment") == "connected bond-graph unwrapping before alignment; no MIC on fitted residuals")
    return (d.get("frame") == "shared stored slab coordinate frame"
            and d.get("alignment") == "none"
            and d.get("periodic_treatment") == "minimum-image displacement independently per matched atom")


def _verdict(value: Any, unit: str, threshold: Decimal, operator: str) -> str:
    if unit not in ("angstrom", "nm"):
        raise ValueError("Unsupported unit")
    observed = Decimal(str(_finite(value, "measurement value"))) * (Decimal(10) if unit == "nm" else Decimal(1))
    truth = observed <= threshold if operator == "<=" else observed >= threshold
    return "SUPPORTED" if truth else "CONTRADICTED"


def baseline(case_model_payload: dict, method: str = "scope") -> dict:
    """Run a deterministic development baseline using only the supplied payload.

    ``scope`` binds pair, mask, frame, alignment, periodic rules and weights.
    ``value_only`` uses the first visible number regardless of its scope.
    ``structure`` checks for any record of the requested pair, then always
    predicts contradiction. These controls deliberately have different limits.
    """
    if method not in ("scope", "value_only", "structure"):
        raise ValueError("Unknown baseline method")
    parsed = parse_payload(case_model_payload)
    rows = parsed["measurements"]
    if method == "value_only":
        candidates = rows[:1]
    elif method == "structure":
        candidates = [x for x in rows if x["pair_id"] == parsed["pair_id"]]
        return {"verdict": "CONTRADICTED" if candidates else "INSUFFICIENT_EVIDENCE", "evidence_ids": []}
    else:
        candidates = [x for x in rows if x["pair_id"] == parsed["pair_id"]
                      and _matches_definition(x, parsed["metric_id"], parsed["atom_sets"])]
    if len(candidates) != 1:
        return {"verdict": "INSUFFICIENT_EVIDENCE", "evidence_ids": []}
    item = candidates[0]
    return {"verdict": _verdict(item["value"], item["unit"], parsed["threshold_A"], parsed["operator"]),
            "evidence_ids": [item["evidence_id"]]}


def build_benchmark(pair_records: list[dict], seed: int = 20261020) -> tuple[list[dict], list[dict], dict]:
    """Produce 8 base cases x 2 presentations for every real/control group.

    Each real group contributes two decisive thresholds for each of three
    metrics, plus one all-values-removed and one wrong-pair case. Thresholds
    are 0.75/1.25 times the real measured value. A stable hash chooses <= or >=.
    Each target therefore has one supported and one contradicted decisive
    case. No holdout is created or implied by this development constructor.
    """
    if not isinstance(pair_records, list) or not pair_records:
        raise ValueError("pair_records must be a nonempty list")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    grouped = defaultdict(dict)
    seen = set()
    for raw in pair_records:
        if not isinstance(raw, dict):
            raise ValueError("Every source record must be a dictionary")
        record = copy.deepcopy(raw)
        pair = _id(record.get("pair_id"), "pair_id")
        group = _id(record.get("group_id"), "group_id")
        if pair in seen:
            raise ValueError("Repeated source pair")
        seen.add(pair)
        if record.get("split") != "pilot_development":
            raise ValueError("This constructor accepts only pilot_development sources")
        origin = record.get("origin")
        if origin not in ("measured_endpoint_pair", "synthetic_control") or origin in grouped[group]:
            raise ValueError("Each group requires exactly one measured pair and one synthetic control")
        record["_atom_sets"] = _atom_sets(record)
        for metric, _ in METRICS:
            value = _finite(record.get("measurements", {}).get(metric + "_A"), pair + "." + metric)
            if origin == "measured_endpoint_pair" and value <= 1e-6:
                raise ValueError(f"{pair}: real {metric} must exceed 1e-6 angstrom; no replacement permitted")
            _definition(record, metric)
        grouped[group][origin] = record
    if any(set(items) != {"measured_endpoint_pair", "synthetic_control"} for items in grouped.values()):
        raise ValueError("Each group requires both a real pair and its synthetic control")
    public, gold = [], []
    for group_index, (group, sources) in enumerate(sorted(grouped.items())):
        real, control = sources["measured_endpoint_pair"], sources["synthetic_control"]
        if real["_atom_sets"] != control["_atom_sets"]:
            raise ValueError("Control must preserve all declared atom sets")
        for metric, _ in METRICS:
            if _definition(real, metric) != _definition(control, metric):
                raise ValueError("Control and real measurement definitions must match")
        base_specs = []
        for metric_index, (metric, _) in enumerate(METRICS):
            operator = "<=" if int(_hash(seed, group, metric, "operator"), 16) % 2 == 0 else ">="
            family = FAMILIES[(group_index + metric_index) % 3]
            value = real["measurements"][metric + "_A"]
            for threshold_kind, factor in (("below", 0.75), ("above", 1.25)):
                base_specs.append((metric, operator, value * factor, family, threshold_kind))
        for family in ("missing_measurements", "wrong_run"):
            metric = METRICS[int(_hash(seed, group, family, "target"), 16) % 3][0]
            operator = "<=" if int(_hash(seed, group, family, "operator"), 16) % 2 == 0 else ">="
            base_specs.append((metric, operator, real["measurements"][metric + "_A"] * 0.75, family, "unavailable"))
        for metric, operator, threshold, family, threshold_kind in base_specs:
            base_id = "b_" + _hash(seed, group, metric, operator, family, threshold_kind)
            contrast = "c_" + _hash(seed, group, metric, operator, "threshold_contrast") if family in FAMILIES else None
            for presentation in ("structured", "report"):
                case_id = "p2_" + _hash(seed, base_id, presentation)
                aliases = {role: "P_" + _hash(case_id, role) for role in ("requested", "other")}
                measurements = []
                for role, record in (("requested", real), ("other", control)):
                    for row_metric, display in METRICS:
                        if role == "requested" and family in ("missing_measurements", "wrong_run"):
                            continue
                        if role == "requested" and family == "missing_irrelevant_measurement":
                            remove = METRICS[(next(i for i, x in enumerate(METRICS) if x[0] == metric) + 1) % 3][0]
                            if row_metric == remove:
                                continue
                        value = float(record["measurements"][row_metric + "_A"])
                        if family == "unit_conversion":
                            value /= 10
                        measurements.append({
                            "evidence_id": "E_" + _hash(case_id, role, row_metric),
                            "pair_id": aliases[role], "metric_id": row_metric, "display_name": display,
                            "value": value, "unit": "nm" if family == "unit_conversion" else "angstrom",
                            "definition": _definition(record, row_metric),
                        })
                # Match the row ordering across presentations while changing all IDs.
                order = list(range(len(measurements)))
                random.Random(int(_hash(seed, base_id, "row_order"), 16)).shuffle(order)
                measurements = [measurements[i] for i in order]
                packet = {"requested_pair_id": aliases["requested"], "quantity_convention": QUANTITY_CONVENTION,
                          "atom_sets": copy.deepcopy(real["_atom_sets"]),
                          "measurements": measurements}
                if family == "missing_measurements":
                    packet["measurement_definitions"] = [_definition(real, m) for m, _ in METRICS]
                display = next(name for m, name in METRICS if m == metric)
                threshold_text = format(threshold, ".17g")
                words = "at most" if operator == "<=" else "at least"
                claim = (f"For endpoint pair {aliases['requested']}, the {display}, with equal atom weights and the supplied "
                         f"atom sets, is {words} {threshold_text} angstrom.")
                payload = {"claim": claim}
                payload["evidence_packet" if presentation == "structured" else "evidence_report"] = packet if presentation == "structured" else _render_report(packet)
                expected = "INSUFFICIENT_EVIDENCE"
                required = []
                if family in FAMILIES:
                    relevant = next(x for x in measurements if x["pair_id"] == aliases["requested"] and x["metric_id"] == metric)
                    expected = _verdict(relevant["value"], relevant["unit"], Decimal(threshold_text), operator)
                    required = [relevant["evidence_id"]]
                public.append({
                    "case_schema_version": "phase2_development_v1", "case_id": case_id,
                    "base_case_id": base_id, "contrast_group_id": contrast,
                    "group_id": group, "pair_group_id": group,
                    "split": "pilot_development", "presentation": presentation,
                    "family": family, "target_metric": metric, "operator": operator,
                    "source_pair_id": real["pair_id"], "model_payload": payload,
                })
                gold.append({
                    "case_id": case_id, "base_case_id": base_id, "contrast_group_id": contrast,
                    "group_id": group, "pair_group_id": group, "split": "pilot_development",
                    "presentation": presentation, "family": family, "target_metric": metric,
                    "expected": expected, "required_evidence_ids": required,
                })
    ordered = list(range(len(public)))
    random.Random(seed).shuffle(ordered)
    public, gold = [public[i] for i in ordered], [gold[i] for i in ordered]
    if len({x["case_id"] for x in public}) != len(public):
        raise ValueError("Case identifier collision")
    by_family_label = defaultdict(Counter)
    for item in gold:
        by_family_label[item["family"]][item["expected"]] += 1
    expected_per_label = {"SUPPORTED": len(grouped) * 6, "CONTRADICTED": len(grouped) * 6,
                          "INSUFFICIENT_EVIDENCE": len(grouped) * 4}
    if dict(Counter(g["expected"] for g in gold)) != expected_per_label:
        raise ValueError("Construction did not preserve its declared label balance")
    for p, g in zip(public, gold):
        checked = baseline(p["model_payload"], "scope")
        if checked["verdict"] != g["expected"] or checked["evidence_ids"] != g["required_evidence_ids"]:
            raise ValueError("Source definitions do not satisfy the declared development task")
    audit = {
        "schema_version": "phase2_development_v1", "seed": seed,
        "n_source_groups": len(grouped), "n_source_pairs": len(pair_records),
        "n_base_cases": len(grouped) * 8, "n_cases": len(public),
        "by_label": dict(sorted(Counter(g["expected"] for g in gold).items())),
        "by_family": dict(sorted(Counter(g["family"] for g in gold).items())),
        "by_presentation": dict(sorted(Counter(g["presentation"] for g in gold).items())),
        "by_family_label": {f: dict(sorted(c.items())) for f, c in sorted(by_family_label.items())},
        "by_operator": dict(sorted(Counter(p["operator"] for p in public if p["family"] in FAMILIES).items())),
        "model_input_field": "model_payload", "all_pilot_development": True,
        "evaluation_protocol": "One independent request per case; no cross-case history",
        "threshold_protocol": "0.75 and 1.25 times each real metric, with one hash-selected operator per source/metric; task definitions, not chemical accuracy criteria",
        "structured_selector_accuracy": 1.0,
        "limitations": [
            "This is a balanced development pilot, not a final novelty or generalization benchmark.",
            "Both presentations remain generated templates; the scope selector intentionally solves them exactly.",
            "One real and one rigid-control source per system; all variants remain correlated.",
            "No DFT-accuracy, chemisorption, catalyst-quality or global-minimum claim is tested.",
        ],
    }
    return public, gold, audit
