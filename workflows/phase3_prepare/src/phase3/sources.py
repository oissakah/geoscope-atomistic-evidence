"""Freeze new OC20 source groups and prepare auditable UMA coordinate evidence.

This checkpoint creates candidate scientific inputs only. No LLM prompts,
benchmark claims, truth labels or model rankings are generated here.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from ase.constraints import FixAtoms
from ase.data import covalent_radii
from ase.geometry import find_mic
from ase.io import read, write

from geomscope import data
from geomscope import uma
from geomscope.geometry import analyze_pair
from geomscope.uma import relax_selected

BATCH_SIZE = 20
BATCH_COUNT = 3
SPLIT = "protected_candidate"
METRICS = ("mobile_rmsd_A", "adsorbate_frame_rmsd_A", "internal_rmsd_A")


def _save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _config(config):
    result = {"n_systems": 60, "seed": 20261021, "max_atoms": 180,
              "min_adsorbate_atoms": 3, "max_steps": 600, "fmax": .05,
              "anchor_max_displacement_A": .02}
    result.update({key: config[key] for key in result if key in config})
    for key, minimum, maximum in (("n_systems", 1, 60), ("seed", 0, 2**32-1),
                                  ("max_atoms", 4, 1000), ("min_adsorbate_atoms", 3, 100),
                                  ("max_steps", 1, 600)):
        if type(result[key]) is not int or not minimum <= result[key] <= maximum:
            raise ValueError("Invalid source preparation configuration: " + key)
    for key in ("fmax", "anchor_max_displacement_A"):
        if type(result[key]) not in (int, float) or not math.isfinite(result[key]) or result[key] <= 0:
            raise ValueError("Invalid source preparation configuration: " + key)
    return result


def _inventory(selection):
    rows = []
    for item in selection:
        atoms = read(item["initial_path"], format="extxyz", index=0)
        ads = item["adsorbate_indices"]
        tags = atoms.get_tags()
        rows.append(dict(system_id=item["system_id"], pair_id=item["pair_id"], atom_count=len(atoms),
                         adsorbate_formula=atoms[ads].get_chemical_formula(mode="hill"),
                         surface_elements=sorted(set(atoms[np.flatnonzero(tags == 1)].get_chemical_symbols())),
                         slab_elements=sorted(set(atoms[np.flatnonzero(tags != 2)].get_chemical_symbols()))))
    return dict(basis="Selected initial geometries only; descriptive, never used to rerank or replace systems",
                selected=rows, adsorbate_formula_counts=dict(Counter(x["adsorbate_formula"] for x in rows)),
                surface_element_occurrences=dict(Counter(e for x in rows for e in x["surface_elements"])))


def prepare_sources(cache: Path, out: Path, excluded_groups: set[str], config: dict) -> list[dict]:
    """Exclude development groups before seeded, geometry-only initial selection.

    The official archive's pinned bytes and 15,256-member/200-system layout are
    verified before selection. Failed eligibility and partial selections remain
    in selection.json; split_manifest.json is retained even on insufficiency.
    """
    config = _config(config)
    cache, out = Path(cache).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not isinstance(excluded_groups, set) or any(not isinstance(g, str) or not g for g in excluded_groups):
        raise ValueError("excluded_groups must be a set of nonempty system identifiers")
    archive = data._download_pinned_archive(cache)
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size != data.ARCHIVE_BYTES or data._sha256(archive) != data.ARCHIVE_SHA256:
        raise data.DataPreparationError("Archive does not match the pinned official size/SHA256")
    members = data._safe_extract_archive(archive, cache)
    groups = {row["system_id"] for row in members}
    if len(members) != 15_256 or len(groups) != 200:
        raise data.DataPreparationError("Pinned archive layout must contain 15,256 configurations and 200 systems")
    if not excluded_groups <= groups:
        raise ValueError("An excluded development group is absent from the pinned source archive")
    candidates = [row for row in members if row["system_id"] not in excluded_groups]
    membership = [dict(source_member=row["source_member"], source_sha256=row["source_sha256"],
                       system_id=row["system_id"], config_id=row["config_id"])
                  for row in sorted(candidates, key=lambda row: row["source_member"])]
    _save(out / "candidate_membership.json", membership)
    split = dict(schema_version=1, stage="SOURCE_PREPARATION_ONLY", split=SPLIT,
                 source_archive_sha256=data.ARCHIVE_SHA256, source_archive_bytes=data.ARCHIVE_BYTES,
                 source_configuration_count=len(members), source_system_count=len(groups),
                 excluded_groups=sorted(excluded_groups), excluded_before_selection=True,
                 candidate_groups=sorted(groups - excluded_groups), candidate_configuration_count=len(candidates),
                 candidate_membership_sha256=data._sha256(out / "candidate_membership.json"),
                 selection_parameters=config, selected_systems=0, selection_identity_sha256=None,
                 model_evaluation_started=False, benchmark_claims_created=False, gold_labels_created=False,
                 limitation="Same OC20-Dense source domain with disjoint slab/adsorbate system groups; chemical-family or unseen-training-data independence is not asserted")
    _save(out / "split_manifest.json", split)
    dataset = dict(name="OC20-Dense 2023 OOD validation ASE initial configurations",
                   origin="official_oc20dense_initial_configuration", source_url=data.SOURCE_URL,
                   source_archive_sha256=data.ARCHIVE_SHA256, source_archive_bytes=data.ARCHIVE_BYTES,
                   configuration_count=len(members), system_count=len(groups), license="CC-BY-4.0",
                   documentation_url="https://opencatalystproject.org/challenge.html",
                   checksum_basis="Locally frozen official public archive bytes; not an upstream signed checksum")
    try:
        selection = data._select_initials(candidates, out, config["n_systems"], config["seed"],
                                         config["max_atoms"], config["min_adsorbate_atoms"], dataset)
    except data.DataPreparationError:
        partial = _load(out / "selection.json")
        split.update(status="INSUFFICIENT_ELIGIBLE_SYSTEMS", selected_systems=partial["selected_systems"],
                     partial_selected_group_ids=[x["group_id"] for x in partial["selection"]])
        _save(out / "split_manifest.json", split)
        raise
    if any(row["group_id"] in excluded_groups for row in selection) or len({r["group_id"] for r in selection}) != len(selection):
        raise ValueError("Selection contains an excluded or duplicated group")
    for row in selection:
        row["split"] = SPLIT
    selection_file = _load(out / "selection.json")
    selection_file["selection"] = selection
    selection_file["split"] = SPLIT
    selection_file["excluded_groups"] = sorted(excluded_groups)
    _save(out / "selection.json", selection_file)
    identities = [dict(pair_id=x["pair_id"], group_id=x["group_id"], config_id=x["config_id"],
                       source_member=x["source_member"], source_sha256=x["source_sha256"],
                       initial_sha256=x["initial_sha256"]) for x in selection]
    split.update(status="FROZEN_PENDING_UMA", selected_systems=len(selection),
                 selected_group_ids=[x["group_id"] for x in selection],
                 selection_identity_sha256=_hash(identities), selected_identities=identities,
                 selection_file_sha256=data._sha256(out / "selection.json"))
    _save(out / "split_manifest.json", split)
    _save(out / "diversity_inventory.json", _inventory(selection))
    return selection


def _selection(out, config):
    document = _load(Path(out) / "selection.json")
    selection = document.get("selection")
    if document.get("status") != "COMPLETE" or not isinstance(selection, list) or len(selection) != config["n_systems"]:
        raise ValueError("Expected the complete frozen source selection")
    if len({x["pair_id"] for x in selection}) != len(selection) or len({x["group_id"] for x in selection}) != len(selection):
        raise ValueError("Frozen source selection has duplicate identities")
    return selection


def run_batch(out: Path, batch_index: int, config: dict) -> list[dict]:
    """Run fixed zero-based batch 0/1/2; never replace selected systems."""
    out, config = Path(out).resolve(), _config(config)
    if type(batch_index) is not int or not 0 <= batch_index < BATCH_COUNT:
        raise ValueError("batch_index must be zero-based 0, 1 or 2")
    selection = _selection(out, config)
    selected = selection[batch_index * BATCH_SIZE:(batch_index + 1) * BATCH_SIZE]
    if not selected:
        raise ValueError("Requested batch has no frozen selected sources")
    model = _load(out / "model_manifest.json")
    records = relax_selected(selected, model, out / "batches" / f"batch_{batch_index}",
                             seed=config["seed"], fmax=config["fmax"], steps=config["max_steps"],
                             smoke_systems=3, smoke_only=False)
    if [x.get("pair_id") for x in records] != [x["pair_id"] for x in selected]:
        raise ValueError("Relaxation outputs differ from the fixed batch membership")
    _save(out / f"batch_{batch_index}_records.json", records)
    return records


def _bonds(atoms, indices):
    edges = []
    for offset, i in enumerate(indices):
        for j in indices[offset + 1:]:
            distance = float(np.linalg.norm(find_mic(atoms.positions[j] - atoms.positions[i], atoms.cell, atoms.pbc)[0]))
            if .25 < distance < 1.25 * (covalent_radii[atoms.numbers[i]] + covalent_radii[atoms.numbers[j]]):
                edges.append(sorted([i, j]))
    return sorted(edges)


def _masks(atoms, selected):
    if not np.isfinite(atoms.positions).all() or not np.isfinite(atoms.cell.array).all():
        raise ValueError("Nonfinite geometry")
    tags = atoms.get_tags()
    if not set(map(int, tags)) <= {0, 1, 2}:
        raise ValueError("Unsupported coordinate tags; expected only 0, 1 or 2")
    for label, target in (("adsorbate_indices", np.flatnonzero(tags == 2)),
                          ("mobile_indices", np.flatnonzero(tags != 0)),
                          ("anchor_indices", np.flatnonzero(tags == 0))):
        if selected[label] != target.tolist():
            raise ValueError("Coordinate tags disagree with frozen " + label)
    fixed = set()
    for constraint in atoms.constraints:
        if not isinstance(constraint, FixAtoms):
            raise ValueError("Only fixed-atom constraints are supported")
        fixed.update(map(int, constraint.get_indices()))
    if fixed != set(selected["anchor_indices"]):
        raise ValueError("Fixed mask differs from frozen anchor set")


def _pair(entry, a, b, initial_path, final_path, config, *, synthetic=False):
    selected = entry["selection"]
    _masks(a, selected)
    _masks(b, selected)
    declared = sorted(sorted(edge) for edge in selected["adsorbate_bonds"])
    if _bonds(a, selected["adsorbate_indices"]) != declared or _bonds(b, selected["adsorbate_indices"]) != declared:
        raise ValueError("Initial/final heuristic bond graphs differ; topology requires scientific review")
    result = analyze_pair(a, b, selected["mobile_indices"], selected["adsorbate_indices"],
                          selected["anchor_indices"], selected["adsorbate_bonds"])
    if result["anchor_max_displacement_A"] > config["anchor_max_displacement_A"]:
        raise ValueError("Fixed slab anchor drift exceeds the frame tolerance")
    for definition in result["metric_definitions"].values():
        definition["atom_subset"] = definition["atom_indices"]
        definition["pbc"] = a.pbc.tolist()
    result["validation"].update(anchor_drift_cutoff_applied=True,
                                anchor_max_displacement_cutoff_A=config["anchor_max_displacement_A"])
    return dict(pair_id=entry["pair_id"] + ("_rigid_translation" if synthetic else ""),
                system_id=selected["system_id"], group_id=selected["group_id"], config_id=selected["config_id"],
                split=SPLIT, origin="synthetic_control" if synthetic else "measured_endpoint_pair",
                measurements={key: result[key] for key in METRICS}, metric_definitions=result["metric_definitions"],
                geometry_audit=result, atom_correspondence_confirmed=True, topology_reviewed=False,
                correspondence_basis="Inherited fixed atom order, without permutation or symmetry matching",
                topology_basis="Unreviewed initial distance-based connected graph; equal graph required at both endpoints",
                provenance=dict(workflow_a="UMA final coordinates" if synthetic else "official OC20-Dense initial placement",
                                workflow_b="synthetic adsorbate translation +0.7 A along stored x" if synthetic else "UMA oc20 FIRE endpoint",
                                source_hashes=dict(initial=data._sha256(initial_path), final=data._sha256(final_path)),
                                run_id_a=entry["pair_id"] + (":UMA" if synthetic else ":initial"),
                                run_id_b=entry["pair_id"] + (":synthetic" if synthetic else ":UMA"),
                                original_source_initial_sha256=selected["initial_sha256"],
                                original_archive_member=selected["source_member"],
                                original_archive_member_sha256=selected["source_sha256"],
                                relaxation_run_signature=entry.get("run_signature"),
                                model_provenance=entry.get("model_provenance")),
                energetic_or_convergence_claims_enabled=False,
                caveat="Synthetic controls have no evaluated energy, force or convergence" if synthetic else
                       "Coordinate measurements do not establish DFT accuracy or a global energy minimum")


def _verify_endpoint(entry, selected, out):
    if entry.get("selection") != selected:
        raise ValueError("Relaxation record differs from the frozen selected source")
    if entry.get("source_initial_sha256") != selected["initial_sha256"] or data._sha256(Path(selected["initial_path"])) != selected["initial_sha256"]:
        raise ValueError("Original selected reference hash changed")
    for role in ("initial", "final", "optimizer_log", "trajectory"):
        artifact = entry.get("artifacts", {}).get(role, {})
        supplied_path = Path(artifact.get("path", ""))
        path = supplied_path.resolve()
        if supplied_path.is_symlink() or not path.is_relative_to(out) or not path.is_file() or data._sha256(path) != artifact.get("sha256"):
            raise ValueError("Missing or changed relaxation artifact: " + role)
        if str(path) != str(Path(entry.get(role + "_path", "")).resolve()):
            raise ValueError("Artifact and coordinate path disagree: " + role)


def _recover_batch(out, index, selected, config):
    """Reuse finalized per-system evidence after an interrupted batch summary.

    Reconstruct the exact copied UMA identity without initializing a calculator.
    Missing/corrupt records remain unknown outcomes; no computation is retried.
    """
    model = _load(out / "model_manifest.json")
    prepared = []
    for row in selected:
        source = Path(row["initial_path"]).resolve()
        if not source.is_file() or data._sha256(source) != row["initial_sha256"]:
            raise ValueError("Cannot recover batch: frozen initial reference is missing or changed")
        prepared.append(dict(selection=row, pair_id=row["pair_id"], source=str(source),
                             source_sha256=row["initial_sha256"]))
    settings = dict(seed=config["seed"], fmax_eV_A=float(config["fmax"]),
                    force_criterion="mobile constrained fmax < threshold", steps_cap=config["max_steps"],
                    smoke_systems=3, smoke_only=False, optimizer="ase.optimize.FIRE",
                    optimizer_kwargs=dict(dt=.1,maxstep=.2), device="cuda", task_name="oc20",
                    inference=dict(uma.INFERENCE_SETTINGS), required_fairchem_version=uma.FAIRCHEM_VERSION)
    hashes = dict(selection_sha256=uma._hash_json(prepared), model_manifest_sha256=uma._hash_json(model),
                  settings_sha256=uma._hash_json(settings))
    signature = uma._hash_json(hashes)
    recovered = []
    for item in prepared:
        slug = hashlib.sha256(item["pair_id"].encode()).hexdigest()[:16]
        directory = out / "batches" / f"batch_{index}" / "relaxations" / slug / signature[:16]
        checkpoint = directory / "record.json"
        has_checkpoint = checkpoint.is_file()
        record = uma._resume_record(checkpoint, signature, hashes, item) if has_checkpoint else None
        if record is not None:
            record["recovered_from_finalized_checkpoint"] = True
            record["source_batch_summary_missing"] = True
        else:
            partial = directory.is_dir() and any(directory.iterdir())
            record = dict(**item["selection"], selection=item["selection"], converged=False,
                          status="unverified_finalized_record" if has_checkpoint else
                                 "interrupted_attempt_without_final_record" if partial else
                                 "missing_batch_summary_attempt_status_unknown",
                          source_batch_summary_missing=True,
                          recovery_note="No valid finalized checkpoint; retained without retry or replacement")
        recovered.append(record)
    return recovered


def measure_sources(out: Path, config: dict) -> dict:
    """Review geometry from all fixed sources, retaining every failed denominator."""
    out, config = Path(out).resolve(), _config(config)
    selection = _selection(out, config)
    records, rejections, pairs, per_system, recovery = [], [], [], [], []
    for index in range(BATCH_COUNT):
        wanted = selection[index*BATCH_SIZE:(index+1)*BATCH_SIZE]
        if not wanted:
            continue
        path = out / f"batch_{index}_records.json"
        if path.is_file():
            batch = _load(path)
            if not isinstance(batch, list) or [r.get("pair_id") for r in batch] != [r["pair_id"] for r in wanted]:
                raise ValueError("Batch record membership differs from frozen selection")
        else:
            batch = _recover_batch(out, index, wanted, config)
            recovery.append(dict(batch_index=index, batch_summary_missing=True,
                                 recovered_finalized_records=sum(r.get("recovered_from_finalized_checkpoint",False) for r in batch),
                                 outcomes=dict(Counter(r["status"] for r in batch))))
        records.extend(batch)
    for selected, entry in zip(selection, records):
        summary = dict(pair_id=selected["pair_id"], group_id=selected["group_id"],
                       status=entry.get("status", "unknown"), measured=False, measurements=None,
                       final_fmax_eV_A=entry.get("final_fmax_eV_A"), steps=entry.get("steps"), rejection=None)
        try:
            if entry.get("status") != "converged" or entry.get("converged") is not True:
                raise ValueError("No converged endpoint; selected source retained without replacement")
            force = entry.get("final_fmax_eV_A")
            if type(force) not in (int, float) or not math.isfinite(force) or not 0 <= force < config["fmax"]:
                raise ValueError("Invalid or nonconverged final force audit")
            if type(entry.get("steps")) is not int or not 0 <= entry["steps"] <= config["max_steps"]:
                raise ValueError("Relaxation step count exceeds the frozen budget")
            _verify_endpoint(entry, selected, out)
            original, a, b = (read(selected["initial_path"], format="extxyz", index=0),
                              read(entry["initial_path"], format="extxyz", index=0),
                              read(entry["final_path"], format="extxyz", index=0))
            _masks(original, selected)
            if (original.get_chemical_symbols() != a.get_chemical_symbols() or
                    not np.allclose(original.positions, a.positions, rtol=0, atol=1e-8) or
                    not np.allclose(original.cell.array, a.cell.array, rtol=0, atol=1e-8) or
                    not np.array_equal(original.pbc, a.pbc)):
                raise ValueError("Saved initial endpoint differs from the original selected reference")
            pair = _pair(entry, a, b, Path(entry["initial_path"]), Path(entry["final_path"]), config)
            pairs.append(pair)
            summary.update(measured=True, measurements=pair["measurements"])
        except Exception as exc:
            summary["rejection"] = str(exc)
            rejections.append(dict(pair_id=selected["pair_id"], group_id=selected["group_id"],
                                   kind="source_endpoint", status=entry.get("status"), reason=str(exc)))
            per_system.append(summary)
            continue
        per_system.append(summary)
        try:
            control = b.copy()
            control.calc, control.info = None, {}
            for key in list(control.arrays):
                if key not in {"numbers", "positions", "tags"}:
                    del control.arrays[key]
            control.positions[selected["adsorbate_indices"]] += [.7, 0., 0.]
            folder = out / "controls"
            folder.mkdir(exist_ok=True)
            target = folder / (entry["pair_id"] + "_translated.extxyz")
            write(target, control, format="extxyz", write_results=False)
            control = read(target, format="extxyz", index=0)
            pairs.append(_pair(entry, b, control, Path(entry["final_path"]), target, config, synthetic=True))
        except Exception as exc:
            rejections.append(dict(pair_id=selected["pair_id"] + "_rigid_translation", group_id=selected["group_id"],
                                   kind="synthetic_control", reason=str(exc)))
    with (out / "pair_measurements.jsonl").open("w", encoding="utf-8") as stream:
        for pair in pairs:
            stream.write(json.dumps(pair, allow_nan=False) + "\n")
    _save(out / "relaxation_results.json", records)
    _save(out / "measurement_rejections.json", rejections)
    _save(out / "source_metrics.json", per_system)
    _save(out / "batch_recovery_audit.json", recovery)
    with (out / "measurements.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["pair_id", "system_id", "origin", *METRICS])
        writer.writeheader()
        writer.writerows(dict(pair_id=p["pair_id"], system_id=p["system_id"], origin=p["origin"], **p["measurements"]) for p in pairs)
    measured = sum(row["measured"] for row in per_system)
    outcome_counts = dict(Counter(row.get("status", "unknown") for row in records))
    result = dict(status="READY_FOR_SOURCE_REVIEW" if measured == len(selection) else "PARTIAL_SOURCE_EVIDENCE",
                  selected_systems=len(selection), outcome_denominator=len(selection), outcome_counts=outcome_counts,
                  measured_pairs=measured, synthetic_pairs=len(pairs)-measured, rejected=len(rejections),
                  excluded_source_endpoints=len(selection)-measured, split=SPLIT,
                  no_selected_sources_replaced=True, model_evaluation_started=False,
                  benchmark_claims_created=False, gold_labels_created=False, phase3_complete=False,
                  topology_review_required=True,
                  limitation="Source preparation only; same-domain group disjointness and heuristic topology require review before a frozen final evaluation")
    _save(out / "source_measurement_summary.json", result)
    return result
