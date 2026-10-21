"""Coordinate-derived cases with explicit, mathematically licensed witnesses.

The design is fixed using the original development sources. Source-group
qualification is separate from this constructor. In particular no assertion
that aligned internal RMSD is bounded by per-atom MIC RMSD is made.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
from typing import Any

METRICS = (
    ("mobile_rmsd", "mobile-atom coordinate RMSD"),
    ("adsorbate_frame_rmsd", "adsorbate RMSD in the specified surface frame"),
    ("internal_rmsd", "rigid-aligned internal adsorbate RMSD"),
)
NAMES = dict(METRICS)
OPERATIONS = ("value", "mobile_lower", "adsorbate_upper", "none")
LABELS = ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")
QUANTITY_CONVENTION = (
    "Each value is the square root of the mean squared coordinate-residual norm over its selected atoms, "
    "after the stated alignment and periodic handling."
)
PERMITTED_RELATIONS = (
    "The mobile set contains the adsorbate set and at least one other atom. "
    "For shared-frame residuals with identical per-atom minimum-image handling and equal atom weights, "
    "the squared quantity for the mobile set times its atom count equals the corresponding adsorbate "
    "term plus a nonnegative squared-residual sum for the remaining mobile atoms. "
    "Thus an adsorbate value gives a mobile lower bound, and a mobile value gives an adsorbate upper bound. "
    "No bound involving independent-centroid rigid alignment or the fixed anchor set is licensed. "
    "Coordinates and numerical cell vectors are not supplied, and no additional geometry or physical constraints are assumed."
)
_SAME_FRAME = "shared stored slab coordinate frame"
_MIC = "minimum-image displacement independently per matched atom"
_INTERNAL_FRAME = "independent molecular centroids"
_INTERNAL_ALIGN = "proper Kabsch rotation plus translation; no reflection"
_INTERNAL_PERIODIC = "connected bond-graph unwrapping before alignment; no MIC on fitted residuals"
_WEIGHT = "equal weight per selected atom"
_EPS = Decimal("1e-8")


def _hash(*items: Any) -> str:
    return hashlib.sha256(json.dumps(items, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(field + " must be a nonempty unpadded string")
    return value


def _number(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(field + " must be a finite nonnegative number")
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError(field + " must be a finite nonnegative number")
    return result


def _indices(value: Any, field: str) -> list[int]:
    if not isinstance(value, list) or not value or any(type(i) is not int or i < 0 for i in value) or len(set(value)) != len(value):
        raise ValueError(field + " must contain unique nonnegative atom indices")
    return sorted(value)


def _pbc(value: Any) -> list[bool]:
    if not isinstance(value, list) or len(value) != 3 or any(type(v) is not bool for v in value):
        raise ValueError("pbc must contain three booleans")
    return list(value)


def _definition(record: dict, metric: str) -> dict:
    defs = record.get("metric_definitions", {})
    d = defs.get(metric + "_A", defs.get(metric))
    if not isinstance(d, dict):
        raise ValueError("Missing source metric definition: " + metric)
    result = dict(atom_indices=_indices(d.get("atom_indices", d.get("atom_subset")), metric),
                  frame=d.get("frame"), alignment=d.get("alignment"),
                  periodic_treatment=d.get("periodic_treatment"), weighting=d.get("weighting"),
                  pbc=_pbc(d.get("pbc")))
    for key in ("frame", "alignment", "periodic_treatment", "weighting"):
        _identifier(result[key], metric + "." + key)
        if "\n" in result[key] or "\r" in result[key]:
            raise ValueError("Definitions must stay on one line")
    return result


def _atom_sets(record: dict) -> dict:
    sets = {"mobile": _definition(record, "mobile_rmsd")["atom_indices"],
            "adsorbate": _definition(record, "adsorbate_frame_rmsd")["atom_indices"],
            "anchors": _definition(record, "anchor_rmsd")["atom_indices"]}
    _validate_sets(sets)
    if _definition(record, "internal_rmsd")["atom_indices"] != sets["adsorbate"]:
        raise ValueError("Internal metric must use the adsorbate set")
    return sets


def _validate_sets(sets: dict) -> None:
    if not isinstance(sets, dict) or set(sets) != {"mobile", "adsorbate", "anchors"}:
        raise ValueError("Exactly mobile, adsorbate and anchor atom sets are required")
    sets = {key: _indices(value, key) for key, value in sets.items()}
    if not set(sets["adsorbate"]) < set(sets["mobile"]):
        raise ValueError("The adsorbate must be a strict subset of the mobile set")
    if set(sets["anchors"]) & set(sets["mobile"]):
        raise ValueError("Anchor and mobile sets must be disjoint")


def _definition_is(parsed: dict, row: dict, metric: str) -> bool:
    d = row.get("definition", {})
    mask = parsed["atom_sets"]["mobile"] if metric == "mobile_rmsd" else parsed["atom_sets"]["adsorbate"]
    try:
        row_indices = _indices(d.get("atom_indices"), "measurement atom_indices")
        row_pbc = _pbc(d.get("pbc"))
    except ValueError:
        return False
    if (row_indices != sorted(mask) or d.get("weighting") != _WEIGHT
            or row_pbc != parsed["pbc"]):
        return False
    if metric == "internal_rmsd":
        return (d.get("frame") == _INTERNAL_FRAME and d.get("alignment") == _INTERNAL_ALIGN
                and d.get("periodic_treatment") == _INTERNAL_PERIODIC)
    return d.get("frame") == _SAME_FRAME and d.get("alignment") == "none" and d.get("periodic_treatment") == _MIC


def _scope_relation(parsed: dict, row: dict, operation: str) -> bool:
    target = parsed["target_metric"]
    if operation == "value":
        return _definition_is(parsed, row, target)
    if operation == "mobile_lower":
        return target == "mobile_rmsd" and _definition_is(parsed, row, "adsorbate_frame_rmsd")
    if operation == "adsorbate_upper":
        return target == "adsorbate_frame_rmsd" and _definition_is(parsed, row, "mobile_rmsd")
    return False


def licensed_relation(parsed: dict, row: dict, operation: str) -> bool:
    """Whether one measurement licenses this operation for the requested pair."""
    try:
        _validate_sets(parsed["atom_sets"])
        return row.get("pair_id") == parsed["pair_id"] and _scope_relation(parsed, row, operation)
    except (KeyError, TypeError, ValueError):
        return False


def interval_for(parsed: dict, row: dict, operation: str, validate_scope: bool = True,
                 validate_pair: bool = True) -> tuple[Decimal, Decimal | None]:
    """Return a licensed range, or raise for an invalid selected operation.

    Disabling scope validation is an intentionally weakened experimental control:
    it applies the chosen operation to the visible value without binding its
    physical definition or target type. Pair validation is independent.
    """
    _validate_sets(parsed["atom_sets"])
    if operation not in OPERATIONS[:-1]:
        raise ValueError("No numerical interval for this operation")
    if validate_pair and row.get("pair_id") != parsed["pair_id"]:
        raise ValueError("Selected record belongs to another endpoint pair")
    if validate_scope and not _scope_relation(parsed, row, operation):
        raise ValueError("Selected operation is not licensed by the physical definition")
    unit = row.get("unit")
    if unit not in ("angstrom", "nm"):
        raise ValueError("Unsupported length unit")
    value = _number(row.get("value"), "measurement") * (Decimal(10) if unit == "nm" else Decimal(1))
    if operation == "value":
        return value, value
    with localcontext() as context:
        context.prec = 50
        n_a = Decimal(len(parsed["atom_sets"]["adsorbate"]))
        n_m = Decimal(len(parsed["atom_sets"]["mobile"]))
        if operation == "mobile_lower":
            return value * (n_a / n_m).sqrt(), None
        return Decimal(0), value * (n_m / n_a).sqrt()


def judge_interval(lower: Decimal, upper: Decimal | None, threshold: Decimal,
                   operator: str) -> str | None:
    """Return an entailed decisive label; None means the interval straddles it."""
    lower, threshold = _number(lower, "lower"), _number(threshold, "threshold")
    upper = None if upper is None else _number(upper, "upper")
    if upper is not None and upper < lower:
        raise ValueError("Invalid interval")
    if operator == "<=":
        if upper is not None and upper <= threshold:
            return "SUPPORTED"
        if lower > threshold:
            return "CONTRADICTED"
    elif operator == ">=":
        if lower >= threshold:
            return "SUPPORTED"
        if upper is not None and upper < threshold:
            return "CONTRADICTED"
    else:
        raise ValueError("Only <= and >= are supported")
    return None


def enumerate_proofs(payload: dict) -> list[dict]:
    """Enumerate all conclusive single-record witnesses licensed by the packet."""
    parsed = parse_payload(payload)
    proofs = []
    for row in parsed["measurements"]:
        for operation in OPERATIONS[:-1]:
            if not licensed_relation(parsed, row, operation):
                continue
            lower, upper = interval_for(parsed, row, operation)
            verdict = judge_interval(lower, upper, parsed["threshold_A"], parsed["operator"])
            if verdict is not None:
                proofs.append(dict(verdict=verdict, evidence_ids=[row["evidence_id"]], operation=operation))
    if len({p["verdict"] for p in proofs}) > 1:
        raise ValueError("Supplied measurements yield conflicting licensed proofs")
    return sorted(proofs, key=lambda p: (OPERATIONS.index(p["operation"]), p["evidence_ids"]))


def oracle(payload: dict) -> dict:
    """Payload-only deterministic ceiling for this controlled case universe."""
    proofs = enumerate_proofs(payload)
    return proofs[0] if proofs else dict(verdict="INSUFFICIENT_EVIDENCE", evidence_ids=[], operation="none")


_CLAIM = re.compile(r"For endpoint pair (P_[a-f0-9]{8}), the (.+), with equal atom weights and the supplied atom sets, is (at most|at least) ([0-9.eE+\-]+) angstrom\.")
_ROW = re.compile(
    r'Evidence ID: (E_[0-9a-f]{8})\. Endpoint pair: (P_[0-9a-f]{8})\. '
    r'Value: ([0-9.eE+\-]+) (angstrom|nm)\. Selected atom indices: (\[[^\n]*?\])\. '
    r'Coordinate frame: ("(?:[^"\\]|\\.)*")\. Alignment: ("(?:[^"\\]|\\.)*")\. '
    r'Periodic treatment: ("(?:[^"\\]|\\.)*")\. Periodic axes: (\[[^\n]*?\])\. '
    r'Weighting: ("(?:[^"\\]|\\.)*")\.'
)


def _render_report(packet: dict) -> str:
    lines = [packet["quantity_convention"], packet["permitted_relations"],
             "Mobile atom indices: " + json.dumps(packet["atom_sets"]["mobile"]) + ".",
             "Adsorbate atom indices: " + json.dumps(packet["atom_sets"]["adsorbate"]) + ".",
             "Fixed anchor atom indices: " + json.dumps(packet["atom_sets"]["anchors"]) + ".",
             "Periodic axes for all records: " + json.dumps(packet["pbc"]) + "."]
    for row in packet["measurements"]:
        d = row["definition"]
        lines.append(f"Evidence ID: {row['evidence_id']}. Endpoint pair: {row['pair_id']}. "
                     f"Value: {format(row['value'], '.17g')} {row['unit']}. "
                     f"Selected atom indices: {json.dumps(d['atom_indices'])}. "
                     f"Coordinate frame: {json.dumps(d['frame'])}. Alignment: {json.dumps(d['alignment'])}. "
                     f"Periodic treatment: {json.dumps(d['periodic_treatment'])}. "
                     f"Periodic axes: {json.dumps(d['pbc'])}. Weighting: {json.dumps(d['weighting'])}.")
    return "\n".join(lines)


def parse_payload(payload: dict) -> dict:
    """Normalize the two transparent presentations without audit/gold metadata."""
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dictionary")
    m = _CLAIM.fullmatch(payload.get("claim", ""))
    if not m:
        raise ValueError("Unrecognized controlled claim")
    pair, display, operator, threshold = m.groups()
    target = next((key for key, name in METRICS if name == display), None)
    if target is None:
        raise ValueError("Unrecognized target")
    if "evidence_packet" in payload:
        packet = copy.deepcopy(payload["evidence_packet"])
    else:
        report = payload.get("evidence_report")
        if not isinstance(report, str):
            raise ValueError("Missing evidence")
        if not report.startswith(QUANTITY_CONVENTION + "\n" + PERMITTED_RELATIONS + "\n"):
            raise ValueError("Report does not declare the required quantity/relation conventions")
        sets = {}
        for key, prefix in (("mobile", "Mobile"), ("adsorbate", "Adsorbate"), ("anchors", "Fixed anchor")):
            found = re.search(r"^" + prefix + r" atom indices: (\[[^\n]*?\])\.$", report, re.MULTILINE)
            if not found:
                raise ValueError("Missing report atom set")
            sets[key] = json.loads(found.group(1))
        found = re.search(r"^Periodic axes for all records: (\[[^\n]*?\])\.$", report, re.MULTILINE)
        if not found:
            raise ValueError("Missing report periodic axes")
        rows = []
        for match in _ROW.finditer(report):
            eid, pid, value, unit, indices, frame, alignment, periodic, pbc, weighting = match.groups()
            rows.append(dict(evidence_id=eid, pair_id=pid, value=float(value), unit=unit,
                definition=dict(atom_indices=json.loads(indices), frame=json.loads(frame), alignment=json.loads(alignment),
                    periodic_treatment=json.loads(periodic), pbc=json.loads(pbc), weighting=json.loads(weighting))))
        if len(rows) != report.count("Evidence ID:"):
            raise ValueError("Unparsed report row")
        packet = dict(atom_sets=sets, pbc=json.loads(found.group(1)), measurements=rows,
                      quantity_convention=QUANTITY_CONVENTION, permitted_relations=PERMITTED_RELATIONS)
    if packet.get("quantity_convention") != QUANTITY_CONVENTION or packet.get("permitted_relations") != PERMITTED_RELATIONS:
        raise ValueError("Missing quantity/relation conventions")
    _validate_sets(packet.get("atom_sets"))
    pbc = _pbc(packet.get("pbc"))
    rows = packet.get("measurements")
    if not isinstance(rows, list) or len({r.get("evidence_id") for r in rows}) != len(rows):
        raise ValueError("Measurements require unique evidence identifiers")
    return dict(pair_id=pair, target_metric=target, operator="<=" if operator == "at most" else ">=",
                threshold_A=_number(Decimal(threshold), "threshold"), atom_sets=packet["atom_sets"],
                pbc=pbc, measurements=rows)


def _anchor_value(record: dict) -> Decimal:
    return _number(record.get("geometry_audit", {}).get("anchor_rmsd_A"), "anchor_rmsd_A")


def build_benchmark(pair_records: list, seed: int = 20261021,
                    split: str = "development") -> tuple[list, list, dict]:
    """Build 16 bases x two presentations per source, retaining explicit skips.

    Expected per-source counts are 5 supported, 5 contradicted and 6
    insufficient base cases. Near-zero real measurements cause specified cases
    to be skipped and reported, never replaced by another source group.
    """
    if type(seed) is not int or split not in ("development", "heldout"):
        raise ValueError("Invalid seed or final-study split")
    if not isinstance(pair_records, list) or not pair_records:
        raise ValueError("Nonempty source-pair records required")
    grouped = defaultdict(dict)
    seen_pairs = set()
    for raw in pair_records:
        record = copy.deepcopy(raw)
        pair = _identifier(record.get("pair_id"), "pair_id")
        group = _identifier(record.get("group_id"), "group_id")
        if pair in seen_pairs:
            raise ValueError("Duplicate source pair")
        seen_pairs.add(pair)
        origin = record.get("origin")
        if origin not in ("measured_endpoint_pair", "synthetic_control") or origin in grouped[group]:
            raise ValueError("Each group requires one real pair and one control")
        source_split = record.get("split")
        allowed = {"pilot_development", "development"} if split == "development" else {"protected_candidate", "heldout"}
        if source_split not in allowed:
            raise ValueError("Source split does not match the requested evaluation split")
        record["_sets"] = _atom_sets(record)
        record["_pbc"] = _definition(record, "mobile_rmsd")["pbc"]
        for metric, _ in METRICS:
            _number(record.get("measurements", {}).get(metric + "_A"), metric)
            _definition(record, metric)
        _anchor_value(record)
        grouped[group][origin] = record
    if any(set(g) != {"measured_endpoint_pair", "synthetic_control"} for g in grouped.values()):
        raise ValueError("A source group lacks its real/control pair")
    public, gold, skips = [], [], []
    used_pair_aliases, used_evidence_aliases = set(), set()
    def short_alias(case_id, role, prefix, used):
        counter = 0
        while True:
            candidate = prefix + _hash(case_id, role, counter)[:8]
            if candidate not in used:
                used.add(candidate)
                return candidate
            counter += 1
    for group_index, (group, sources) in enumerate(sorted(grouped.items())):
        real, control = sources["measured_endpoint_pair"], sources["synthetic_control"]
        if real["_sets"] != control["_sets"] or real["_pbc"] != control["_pbc"]:
            raise ValueError("Control changed atom sets or periodic axes")
        for metric, _ in METRICS:
            if _definition(real, metric) != _definition(control, metric):
                raise ValueError("Control changed a physical definition")
        specs = []
        # target,operator,threshold,family,key,requested_rows,expected,contrast
        for metric_index, (metric, _) in enumerate(METRICS):
            value = _number(real["measurements"][metric + "_A"], metric)
            if value <= _EPS:
                skips.append(dict(group_id=group, target_metric=metric, family="direct", skipped_base_cases=2, reason="real metric <=1e-8 angstrom"))
                continue
            operator = "<=" if int(_hash(seed, group, metric, "operator"), 16) % 2 == 0 else ">="
            family = "unit_conversion" if (group_index + metric_index) % 3 == 0 else "direct_scope"
            contrast = "cg_" + _hash(seed, group, metric, "direct")[:24]
            for name, factor in (("below", Decimal(".75")), ("above", Decimal("1.25"))):
                threshold = value * factor
                expected = "SUPPORTED" if (value <= threshold if operator == "<=" else value >= threshold) else "CONTRADICTED"
                specs.append((metric, operator, threshold, family, "direct_"+name, [m for m, _ in METRICS], expected, contrast))
        a = _number(real["measurements"]["adsorbate_frame_rmsd_A"], "adsorbate")
        m = _number(real["measurements"]["mobile_rmsd_A"], "mobile")
        with localcontext() as context:
            context.prec = 50
            n_a, n_m = Decimal(len(real["_sets"]["adsorbate"])), Decimal(len(real["_sets"]["mobile"]))
            lower, upper = a * (n_a / n_m).sqrt(), m * (n_m / n_a).sqrt()
        if a > _EPS:
            contrast = "cg_" + _hash(seed, group, "mobile_lower_positive")[:24]
            specs.extend([
                ("mobile_rmsd", ">=", lower*Decimal(".75"), "missing_mobile_bound", "lower_supported", ["adsorbate_frame_rmsd"], "SUPPORTED", contrast),
                ("mobile_rmsd", "<=", lower*Decimal(".75"), "missing_mobile_bound", "lower_contradicted", ["adsorbate_frame_rmsd"], "CONTRADICTED", contrast),
                ("mobile_rmsd", "<=", lower*Decimal("1.25"), "missing_mobile_ambiguous", "lower_unknown_le", ["adsorbate_frame_rmsd"], "INSUFFICIENT_EVIDENCE", None),
                ("mobile_rmsd", ">=", lower*Decimal("1.25"), "missing_mobile_ambiguous", "lower_unknown_ge", ["adsorbate_frame_rmsd"], "INSUFFICIENT_EVIDENCE", None),
            ])
        else:
            skips.append(dict(group_id=group, target_metric="mobile_rmsd", family="missing_mobile", skipped_base_cases=4, reason="visible adsorbate metric <=1e-8 angstrom"))
        if m > _EPS:
            contrast = "cg_" + _hash(seed, group, "adsorbate_upper_positive")[:24]
            specs.extend([
                ("adsorbate_frame_rmsd", "<=", upper*Decimal("1.25"), "missing_adsorbate_bound", "upper_supported", ["mobile_rmsd"], "SUPPORTED", contrast),
                ("adsorbate_frame_rmsd", ">=", upper*Decimal("1.25"), "missing_adsorbate_bound", "upper_contradicted", ["mobile_rmsd"], "CONTRADICTED", contrast),
                ("adsorbate_frame_rmsd", "<=", upper*Decimal(".75"), "missing_adsorbate_ambiguous", "upper_unknown_le", ["mobile_rmsd"], "INSUFFICIENT_EVIDENCE", None),
                ("adsorbate_frame_rmsd", ">=", upper*Decimal(".75"), "missing_adsorbate_ambiguous", "upper_unknown_ge", ["mobile_rmsd"], "INSUFFICIENT_EVIDENCE", None),
            ])
        else:
            skips.append(dict(group_id=group, target_metric="adsorbate_frame_rmsd", family="missing_adsorbate", skipped_base_cases=4, reason="visible mobile metric <=1e-8 angstrom"))
        i = _number(real["measurements"]["internal_rmsd_A"], "internal")
        specs.append(("internal_rmsd", "<=", max(i, Decimal(".001"))*Decimal(".75"),
                      "missing_internal_anchor_only", "internal_unknown", ["anchor_rmsd"], "INSUFFICIENT_EVIDENCE", None))
        wrong_metric = METRICS[int(_hash(seed, group, "wrong_pair_target"), 16) % 3][0]
        wrong_threshold = max(_number(real["measurements"][wrong_metric+"_A"],wrong_metric), Decimal(".001"))*Decimal(".75")
        specs.append((wrong_metric, "<=", wrong_threshold, "wrong_pair", "wrong_pair", [], "INSUFFICIENT_EVIDENCE", None))
        for metric, operator, threshold, family, kind, requested_rows, expected, contrast in specs:
            base_id = "base_" + _hash(seed, group, metric, operator, family, kind)[:24]
            for presentation in ("structured", "report"):
                case_id = "fs_" + _hash(seed, base_id, presentation)[:24]
                aliases = {role: short_alias(case_id, role, "P_", used_pair_aliases) for role in ("requested", "other")}
                if len(set(aliases.values())) != 2:
                    raise ValueError("Pair alias collision")
                rows = []
                for role, record, visible_metrics in (("requested",real,requested_rows),("other",control,[x for x,_ in METRICS])):
                    for row_metric in visible_metrics:
                        value = _anchor_value(record) if row_metric == "anchor_rmsd" else _number(record["measurements"][row_metric+"_A"],row_metric)
                        if family == "unit_conversion":
                            value /= Decimal(10)
                        rows.append(dict(evidence_id=short_alias(case_id,role+"::"+row_metric,"E_",used_evidence_aliases), pair_id=aliases[role],
                            value=float(value), unit="nm" if family=="unit_conversion" else "angstrom",
                            metric_id=row_metric, display_name=NAMES.get(row_metric,"fixed-anchor coordinate RMSD"),
                            definition=_definition(record,row_metric)))
                if len({r["evidence_id"] for r in rows}) != len(rows):
                    raise ValueError("Evidence alias collision")
                order = list(range(len(rows)))
                random.Random(int(_hash(seed,base_id,"order"),16)).shuffle(order)
                rows = [rows[index] for index in order]
                packet = dict(quantity_convention=QUANTITY_CONVENTION, permitted_relations=PERMITTED_RELATIONS,
                              atom_sets=copy.deepcopy(real["_sets"]), pbc=real["_pbc"], measurements=rows)
                text = format(threshold, "f").rstrip("0").rstrip(".") if threshold != threshold.to_integral() else format(threshold,"f")
                claim = (f"For endpoint pair {aliases['requested']}, the {NAMES[metric]}, with equal atom weights and the supplied atom sets, "
                         f"is {'at most' if operator=='<=' else 'at least'} {text} angstrom.")
                payload = dict(claim=claim)
                payload["evidence_packet" if presentation=="structured" else "evidence_report"] = packet if presentation=="structured" else _render_report(packet)
                proofs = enumerate_proofs(payload)
                if oracle(payload)["verdict"] != expected:
                    raise ValueError("Frozen mathematical construction and payload proofs disagree")
                if expected=="INSUFFICIENT_EVIDENCE":
                    witness = ({"lower":str(lower),"upper":None,"explanation":"Remaining mobile-atom squared-residual sum may be zero or positive; threshold strictly exceeds the attainable lower bound."}
                               if family=="missing_mobile_ambiguous" else
                               {"lower":"0","upper":str(upper),"explanation":"The mobile squared-residual sum may be apportioned between adsorbate and other mobile atoms; threshold lies strictly inside the feasible interval."}
                               if family=="missing_adsorbate_ambiguous" else
                               {"lower":"0","upper":None,"explanation":"No requested-pair measurement constrains the target; fixed-anchor values and unrelated-pair values do not bound it."})
                else:
                    witness = None
                metadata = dict(case_id=case_id,base_case_id=base_id,contrast_group_id=contrast,group_id=group,
                                pair_group_id=group,split=split,presentation=presentation,family=family,
                                target_metric=metric,operator=operator)
                public.append(dict(**metadata,model_payload=payload))
                gold.append(dict(**metadata,expected=expected,valid_proofs=proofs,
                                 required_evidence_ids=proofs[0]["evidence_ids"] if proofs else [],
                                 information_interval_witness=witness))
    order = list(range(len(public)))
    random.Random(seed).shuffle(order)
    public,gold = [public[i] for i in order],[gold[i] for i in order]
    if len({p["case_id"] for p in public}) != len(public):
        raise ValueError("Case identifier collision")
    by_family = defaultdict(Counter)
    for g in gold:
        by_family[g["family"]][g["expected"]] += 1
    audit = dict(schema_version="finalstudy_v1",seed=seed,split=split,n_source_groups=len(grouped),
        n_source_pairs=len(pair_records),expected_base_cases_without_skips=16*len(grouped),
        n_base_cases=len(public)//2,n_cases=len(public),skipped_cases=skips,
        skipped_base_cases=sum(s["skipped_base_cases"] for s in skips),
        by_label=dict(sorted(Counter(g["expected"] for g in gold).items())),
        by_family_label={f:dict(sorted(c.items())) for f,c in sorted(by_family.items())},
        by_presentation=dict(sorted(Counter(p["presentation"] for p in public).items())),
        retained_source_group_ids=sorted(grouped),model_input_field="model_payload",
        source_groups_replaced=False,all_valid_single_record_witnesses_enumerated=True,
        internal_from_mic_adsorbate_bound_enabled=False,
        threshold_policy="Prespecified .75/1.25 direct values or exact subset-sum bounds; mathematical task thresholds, not chemical tolerances",
        insufficiency_policy="Visible same-pair cross-metric ranges straddle the threshold, or only anchors/unrelated pairs are visible; no inference from merely deleting one field",
        evaluation_protocol="One independent request per case; preserve source groups and paired presentations in scoring",
        limitations=["Three controlled metric definitions; deterministic interval oracle is a mandatory ceiling.",
                     "Source-group disjointness does not imply chemical-family or training-data independence.",
                     "Operational rejection is not a scientific INSUFFICIENT_EVIDENCE verdict."])
    return public,gold,audit
