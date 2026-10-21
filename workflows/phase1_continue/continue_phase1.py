#!/usr/bin/env python3
"""Continue exactly seven unfinished Phase 1 relaxations; preserve all 20 systems.

Uploaded archives are read as data. Only this package's trusted Python is run.
The original 13 converged endpoints remain unchanged. The additional stage is
fresh ASE FIRE from the seven saved final coordinates, with 300 more steps and
the original 0.05 eV/A stopping criterion. No model download or data selection is
performed. Every final comparison uses the ORIGINAL OC20 initial coordinates.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import math
import re
import stat
import sys
import time
import traceback
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import phase1_support as support

PARENT_ZIP_SHA256 = "0c3a45d6ec1f91baae39831b7f0308a7a20cf2a5f6a0fb56e4052ee1f2e0e4c9"
MAX_PARENT_BYTES = 128 * 1024 * 1024
MAX_PARENT_FILES = 1000
PROTOCOL_VERSION = "phase1_continuation_1"
STAGE_SETTINGS = dict(seed=20261019, fmax=0.05, steps=300, smoke_systems=3, smoke_only=False)
METADATA = {
    "selection.json", "model_manifest.json", "run_config.json", "code_sha256.json",
    "stage_prepare.json", "stage_run.json", "summary.json", "relaxation_protocol.json",
    "relaxation_records.json", "relaxation_results.json", "environment_run.json",
    "environment_prepare.json", "self_tests.json",
}
ARTIFACT_ROLES = ("initial", "final", "optimizer_log", "trajectory")


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _safe_relative(name):
    path = PurePosixPath(name)
    if (not isinstance(name, str) or not name or "\\" in name or "\x00" in name
            or ":" in name or path.is_absolute() or any(p in ("", ".", "..") for p in name.split("/"))):
        raise ValueError("Unsafe or nonportable ZIP path")
    return path


def parent_relative(path, parent_id):
    """Map an archived absolute Swan path to its verified parent-run member."""
    if not isinstance(path, str) or "\\" in path or "\x00" in path:
        raise ValueError("Invalid parent artifact path")
    parts = PurePosixPath(path).parts
    if parts.count(parent_id) != 1:
        raise ValueError("Parent artifact path does not identify exactly one parent run")
    relative = "/".join(parts[parts.index(parent_id) + 1:])
    _safe_relative(relative)
    return relative


def _data_member(relative):
    return (relative in METADATA
            or re.fullmatch(r"inputs/[A-Za-z0-9_-]+\.extxyz", relative) is not None
            or re.fullmatch(r"relaxations/[0-9a-f]{16}/[0-9a-f]{16}/(?:record\.json|initial\.extxyz|final\.extxyz|optimizer\.log|optimizer\.traj)", relative) is not None)


def verify_parent_archive(path, *, _expected_sha256=PARENT_ZIP_SHA256):
    """Verify the whole pinned ZIP and every member before returning data bytes.

    The private expected-hash override exists only for analytic unit fixtures;
    there is deliberately no CLI option that weakens the reviewed parent pin.
    """
    path = Path(path).resolve()
    if not path.is_file() or path.stat().st_size > MAX_PARENT_BYTES:
        raise ValueError("Parent ZIP is missing or exceeds the 128 MiB limit")
    actual = support.digest(path)
    if actual != _expected_sha256:
        raise ValueError("Parent ZIP SHA256 does not match the reviewed Phase 1 result")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(infos) > MAX_PARENT_FILES or len(names) != len(set(names)):
            raise ValueError("Parent ZIP has too many or duplicate members")
        if sum(info.file_size for info in infos) > MAX_PARENT_BYTES:
            raise ValueError("Expanded parent ZIP exceeds 128 MiB")
        for info in infos:
            _safe_relative(info.filename)
            mode = info.external_attr >> 16
            if info.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not stat.S_ISREG(mode)):
                raise ValueError("Parent ZIP must contain ordinary files only")
        manifests = [name for name in names if name.endswith("/SHA256SUMS.json")]
        if len(manifests) != 1:
            raise ValueError("Expected exactly one parent checksum manifest")
        prefix = manifests[0].removesuffix("SHA256SUMS.json")
        parent_id = prefix.rstrip("/")
        if "/" in parent_id:
            raise ValueError("Parent ZIP must have exactly one top-level run folder")
        hashes = json.loads(archive.read(manifests[0]))
        if not isinstance(hashes, dict):
            raise ValueError("Parent checksum manifest is not a dictionary")
        for relative in hashes:
            _safe_relative(relative)
        if {prefix + name for name in hashes} | {manifests[0]} != set(names):
            raise ValueError("Parent ZIP has missing or untracked files")
        payload = {}
        for relative, expected in hashes.items():
            data = archive.read(prefix + relative)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f"Parent member checksum mismatch: {relative}")
            if _data_member(relative):
                payload[relative] = data
    def get(name):
        if name not in payload:
            raise ValueError(f"Missing required parent data: {name}")
        return json.loads(payload[name])
    parent = dict(parent_id=parent_id, archive_sha256=actual, verified_files=len(hashes),
                  all_member_hashes=hashes, payload=payload,
                  selection_manifest=get("selection.json"), records=get("relaxation_records.json"),
                  model=get("model_manifest.json"), config=get("run_config.json"),
                  protocol=get("relaxation_protocol.json"))
    _validate_parent(parent, get("stage_prepare.json"), get("relaxation_results.json"))
    return parent


def _validate_parent(parent, preparation, second_records):
    payload, config, protocol = parent["payload"], parent["config"], parent["protocol"]
    if preparation.get("state") != "COMPLETE":
        raise ValueError("Parent preparation did not complete")
    for name in ("selection.json", "model_manifest.json", "run_config.json", "code_sha256.json"):
        expected = preparation.get("prepared_artifact_sha256", {}).get(name)
        if hashlib.sha256(payload[name]).hexdigest() != expected:
            raise ValueError(f"Frozen prepared artifact changed: {name}")
    if (config.get("n_systems") != 20 or config.get("fmax") != 0.05
            or config.get("max_steps") != 300 or config.get("seed") != 20261019
            or config.get("optimizer") != "FIRE" or config.get("smoke_only") is not False):
        raise ValueError("Parent differs from the reviewed 20-system, 300-step protocol")
    selection = parent["selection_manifest"].get("selection", [])
    records = parent["records"]
    if not isinstance(selection, list) or not isinstance(records, list) or len(selection) != 20 or len(records) != 20:
        raise ValueError("Expected exactly 20 frozen selections and 20 outcomes")
    ids = [item.get("pair_id") for item in selection]
    groups = [item.get("group_id") for item in selection]
    if len(set(ids)) != 20 or len(set(groups)) != 20 or None in ids or None in groups:
        raise ValueError("Parent selection has missing or repeated system IDs")
    by_id = {item.get("pair_id"): item for item in records}
    if len(by_id) != 20 or set(by_id) != set(ids) or second_records != records:
        raise ValueError("Parent selection and outcome IDs do not join exactly")
    prepared = [{"selection": item, "pair_id": item["pair_id"], "source": item["initial_path"],
                 "source_sha256": item["initial_sha256"]} for item in selection]
    hash_keys = ("selection_sha256", "model_manifest_sha256", "settings_sha256")
    hashes = {key: protocol[key] for key in hash_keys}
    settings = {key: value for key, value in protocol.items() if key not in (*hash_keys, "run_signature")}
    if (canonical_hash(prepared) != hashes["selection_sha256"]
            or canonical_hash(parent["model"]) != hashes["model_manifest_sha256"]
            or canonical_hash(settings) != hashes["settings_sha256"]
            or canonical_hash(hashes) != protocol.get("run_signature")):
        raise ValueError("Parent protocol or model/selection signatures are inconsistent")
    counts = {"converged": 0, "nonconverged": 0}
    for item in selection:
        rec = by_id[item["pair_id"]]
        relative = parent_relative(item["initial_path"], parent["parent_id"])
        if (relative not in payload or hashlib.sha256(payload[relative]).hexdigest() != item["initial_sha256"]
                or rec.get("selection") != item or rec.get("source_initial_path") != item["initial_path"]
                or rec.get("source_initial_sha256") != item["initial_sha256"]):
            raise ValueError(f"Original frozen initial/selection mismatch: {item['pair_id']}")
        if rec.get("settings") != settings or any(rec.get(key) != val for key, val in hashes.items()):
            raise ValueError("Parent per-system protocol hashes differ")
        if rec.get("run_signature") != protocol["run_signature"]:
            raise ValueError("Parent record run signature mismatch")
        status, force = rec.get("status"), rec.get("final_fmax_eV_A")
        if status not in counts or type(force) not in (float, int) or not math.isfinite(force):
            raise ValueError("Expected finite-force converged/nonconverged parent outcomes only")
        if rec.get("converged") is not (status == "converged") or ((force < 0.05) != rec["converged"]):
            raise ValueError("Parent force criterion and convergence label disagree")
        if status == "nonconverged" and rec.get("steps") != 300:
            raise ValueError("Unfinished parent systems must have exhausted their 300-step cap")
        counts[status] += 1
        for role in ARTIFACT_ROLES:
            entry = rec.get("artifacts", {}).get(role, {})
            path = rec.get(role + "_path")
            if entry.get("path") != path:
                raise ValueError("Parent artifact path mismatch")
            member = parent_relative(path, parent["parent_id"])
            if member not in payload or hashlib.sha256(payload[member]).hexdigest() != entry.get("sha256"):
                raise ValueError(f"Parent endpoint/log integrity failure: {item['pair_id']} {role}")
    if counts != {"converged": 13, "nonconverged": 7}:
        raise ValueError("This continuation is restricted to the reviewed 13+7 parent outcome")
    parent["selection"] = selection
    parent["records_by_id"] = by_id


def _local_parent_path(parent, out, original):
    return out / "parent_run" / parent_relative(original, parent["parent_id"])


def restore_parent(parent, out):
    """Copy only verified data, refusing to replace changed immutable bytes."""
    for relative, data in parent["payload"].items():
        path = out / "parent_run" / relative
        if path.exists():
            if path.is_symlink() or path.read_bytes() != data:
                raise ValueError(f"Previously restored parent data changed: {relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    support.save_json(out / "parent_integrity.json", dict(
        parent_run_id=parent["parent_id"], parent_archive_sha256=parent["archive_sha256"],
        verified_files=parent["verified_files"], all_original_member_sha256=parent["all_member_hashes"],
        copied_data_members=sorted(parent["payload"]),
        source_code_from_parent_executed=False, parent_source_snapshot_extracted=False))


def _validate_structures(parent, out):
    import numpy as np
    from ase.constraints import FixAtoms
    from ase.io import read
    for selected in parent["selection"]:
        rec = parent["records_by_id"][selected["pair_id"]]
        source = read(_local_parent_path(parent, out, selected["initial_path"]))
        initial = read(_local_parent_path(parent, out, rec["initial_path"]))
        final = read(_local_parent_path(parent, out, rec["final_path"]))
        for atoms in (initial, final):
            if (len(atoms) != len(source) or not np.array_equal(atoms.numbers, source.numbers)
                    or not np.array_equal(atoms.get_tags(), source.get_tags())
                    or not np.array_equal(atoms.pbc, source.pbc)
                    or not np.allclose(atoms.cell, source.cell, rtol=0, atol=1e-10)
                    or [c.todict() for c in atoms.constraints] != [c.todict() for c in source.constraints]
                    or not np.isfinite(atoms.positions).all()):
                raise ValueError(f"Parent atom order, cell, tags, constraints or positions invalid: {selected['pair_id']}")
        if not np.allclose(source.positions, initial.positions, rtol=0, atol=1e-7):
            raise ValueError("Original input and saved optimizer initial coordinates differ")
        fixed = set()
        for constraint in source.constraints:
            if not isinstance(constraint, FixAtoms):
                raise ValueError("Only original FixAtoms constraints are permitted")
            fixed.update(map(int, constraint.get_indices()))
        if (fixed != set(selected["anchor_indices"])
                or set(selected["mobile_indices"]) != set(range(len(source))) - fixed
                or set(selected["adsorbate_indices"]) != set(np.flatnonzero(source.get_tags() == 2))):
            raise ValueError("Original masks do not match saved atom tags/constraints")
        if not np.allclose(source.positions[sorted(fixed)], final.positions[sorted(fixed)], rtol=0, atol=1e-7):
            raise ValueError("Fixed anchors moved in the original relaxation")


def continuation_selection(parent, out):
    """Freeze exactly seven restart inputs while preserving original masks."""
    selected = []
    for item in parent["selection"]:
        rec = parent["records_by_id"][item["pair_id"]]
        if rec["status"] != "nonconverged":
            continue
        restart = copy.deepcopy(item)
        restart.update(initial_path=str(_local_parent_path(parent, out, rec["final_path"])),
                       initial_sha256=rec["artifacts"]["final"]["sha256"],
                       continuation_parent_run_id=parent["parent_id"],
                       continuation_parent_archive_sha256=parent["archive_sha256"],
                       continuation_stage=1, original_initial_sha256=item["initial_sha256"],
                       original_pair_id=item["pair_id"])
        selected.append(restart)
    return selected


def _relocate_original_record(parent, out, rec):
    merged = copy.deepcopy(rec)
    for role in ARTIFACT_ROLES:
        local = str(_local_parent_path(parent, out, rec[role + "_path"]))
        merged[role + "_path"] = local
        merged["artifacts"][role]["path"] = local
    merged["source_initial_path"] = str(_local_parent_path(parent, out, rec["source_initial_path"]))
    merged["parent_record_preserved_at"] = str(_local_parent_path(parent, out,
        str(PurePosixPath(rec["final_path"]).with_name("record.json"))))
    return merged


def _valid_stage_records(parent, out):
    """Recover complete per-system checkpoints after success or scheduler kill."""
    stage_out = out / "continuation_stage"
    if not stage_out.exists():
        return []
    protocol_path = stage_out / "relaxation_protocol.json"
    if not protocol_path.is_file():
        return []
    protocol = support.load_json(protocol_path)
    selection = continuation_selection(parent, out)
    selected = {s["pair_id"]: s for s in selection}
    from geomscope.uma import INFERENCE_SETTINGS
    expected_settings = dict(seed=20261019, fmax_eV_A=0.05,
        force_criterion="mobile constrained fmax < threshold", steps_cap=300,
        smoke_systems=3, smoke_only=False, optimizer="ase.optimize.FIRE",
        optimizer_kwargs={"dt": 0.1, "maxstep": 0.2}, device="cuda", task_name="oc20",
        inference=dict(INFERENCE_SETTINGS), required_fairchem_version="2.23.0")
    prepared = [{"selection": item, "pair_id": item["pair_id"], "source": item["initial_path"],
                 "source_sha256": item["initial_sha256"]} for item in selection]
    expected_hashes = dict(selection_sha256=canonical_hash(prepared),
        model_manifest_sha256=canonical_hash(parent["model"]), settings_sha256=canonical_hash(expected_settings))
    expected_protocol = dict(expected_settings, **expected_hashes, run_signature=canonical_hash(expected_hashes))
    if protocol != expected_protocol:
        raise ValueError("Continuation stage protocol differs from the frozen seven-system protocol")
    records = []
    seen = set()
    for path in sorted((stage_out / "relaxations").glob("*/*/record.json")):
        rec = support.load_json(path)
        pair_id = rec.get("pair_id")
        if pair_id not in selected or pair_id in seen or rec.get("selection") != selected[pair_id]:
            raise ValueError("Unrecognized or duplicate continuation checkpoint")
        if (rec.get("source_initial_path") != selected[pair_id]["initial_path"]
                or rec.get("source_initial_sha256") != selected[pair_id]["initial_sha256"]):
            raise ValueError("Continuation checkpoint restart source differs from its frozen saved final")
        if any(rec.get(key) != protocol.get(key) for key in (
                "selection_sha256", "model_manifest_sha256", "settings_sha256", "run_signature")):
            raise ValueError("Continuation checkpoint protocol signature mismatch")
        if rec.get("settings") != expected_settings:
            raise ValueError("Continuation checkpoint stopping protocol changed")
        if rec.get("status") in ("converged", "nonconverged"):
            for role in ARTIFACT_ROLES:
                art = rec.get("artifacts", {}).get(role, {})
                artifact_path = Path(art.get("path", ""))
                if (not artifact_path.is_relative_to(stage_out) or not artifact_path.is_file()
                        or artifact_path.is_symlink() or support.digest(artifact_path) != art.get("sha256")
                        or str(artifact_path) != rec.get(role + "_path")):
                    raise ValueError("Continuation checkpoint artifact changed or left its stage directory")
            force = rec.get("final_fmax_eV_A")
            if (type(force) not in (float, int) or not math.isfinite(force)
                    or rec.get("converged") != (force < 0.05)
                    or rec["status"] != ("converged" if force < 0.05 else "nonconverged")
                    or not 0 <= rec.get("steps", -1) <= 300):
                raise ValueError("Invalid continuation convergence record")
        elif rec.get("status") not in ("error", "not_run_after_smoke_failure"):
            raise ValueError("Unrecognized continuation checkpoint status")
        seen.add(pair_id)
        records.append(rec)
    return records


def merge_records(parent, out, stage_records):
    """Join all 20 IDs; restore original initial for every scientific pair."""
    by_id = {}
    expected = {s["pair_id"] for s in continuation_selection(parent, out)}
    for rec in stage_records:
        pair_id = rec.get("pair_id")
        if pair_id not in expected or pair_id in by_id:
            raise ValueError("Continuation results do not match the frozen seven systems")
        by_id[pair_id] = rec
    combined = []
    for selected in parent["selection"]:
        original = parent["records_by_id"][selected["pair_id"]]
        base = _relocate_original_record(parent, out, original)
        new = by_id.get(selected["pair_id"])
        if original["status"] == "converged":
            base.update(continuation_action="preserved_parent_converged", additional_steps=0,
                        total_steps=original["steps"], parent_endpoint_sha256=original["artifacts"]["final"]["sha256"])
        elif new is None:
            base.update(continuation_action="not_completed_or_not_attempted", additional_steps=0,
                        total_steps=original["steps"], continuation_status="checkpoint_not_available")
        else:
            # Keep the complete stage-specific record separately; its "initial"
            # is the restart, whereas the scientific pair ALWAYS uses OC20 start.
            base.update(status=new["status"], converged=new.get("converged", False),
                final_fmax_eV_A=new.get("final_fmax_eV_A"), error=new.get("error"),
                continuation_action="continued_from_parent_final_fresh_FIRE",
                additional_steps=new.get("steps", 0), total_steps=original["steps"] + new.get("steps", 0),
                continuation_status=new["status"], continuation_stage_record=new,
                restart_start_path=str(_local_parent_path(parent, out, original["final_path"])),
                restart_start_sha256=original["artifacts"]["final"]["sha256"],
                restart_optimizer_state_available=False,
                continuation_run_signature=new.get("run_signature"))
            for role in ("final", "optimizer_log", "trajectory"):
                if new.get(role + "_path"):
                    base[role + "_path"] = new[role + "_path"]
                if role in new.get("artifacts", {}):
                    base["artifacts"][role] = new["artifacts"][role]
            base["steps"] = base["total_steps"]
            base["elapsed_seconds"] = original["elapsed_seconds"] + new.get("elapsed_seconds", 0.0)
        # This is the essential distinction between geometric evidence and an
        # optimizer restart: all merged records point at original initial bytes.
        base["initial_path"] = str(_local_parent_path(parent, out, selected["initial_path"]))
        base["artifacts"]["initial"] = {"path": base["initial_path"], "sha256": selected["initial_sha256"]}
        base["original_selection"] = selected
        base["selection"] = copy.deepcopy(selected)
        base["parent_run_id"] = parent["parent_id"]
        base["parent_archive_sha256"] = parent["archive_sha256"]
        base["record_schema"] = "combined_parent_and_continuation_v1"
        base["parent_run_signature"] = original["run_signature"]
        base["settings_and_signature_scope"] = "Parent stage; continuation stage has its own nested record and signature"
        combined.append(base)
    if len(combined) != 20 or len({r["pair_id"] for r in combined}) != 20:
        raise ValueError("Combined output lost original systems")
    return combined


def _freeze_protocol(parent, out):
    frozen = dict(protocol_version=PROTOCOL_VERSION, parent_run_id=parent["parent_id"],
        parent_archive_sha256=parent["archive_sha256"], original_systems=20,
        original_converged_preserved=13, continued_systems=7, additional_step_cap=300,
        total_step_cap=600, fmax_eV_A=0.05, optimizer="ase.optimize.FIRE",
        optimizer_state_restored=False, stage="One fresh FIRE stage from saved endpoints",
        selection_sha256=canonical_hash(continuation_selection(parent, out)),
        model_manifest_sha256=canonical_hash(parent["model"]), seed=20261019,
        no_new_data_selection=True, no_model_download=True,
        original_initial_used_for_measurements=True, allowed_further_automatic_extensions=0)
    path = out / "continuation_protocol.json"
    if path.exists() and support.load_json(path) != frozen:
        raise ValueError("This run ID already has a different frozen continuation protocol")
    support.save_json(path, frozen)
    return frozen


def _report(parent, out, stage_records, *, interrupted=False):
    combined = merge_records(parent, out, stage_records)
    support.save_json(out / "relaxation_records.json", combined)
    support.save_json(out / "relaxation_results.json", combined)
    report = support.analyze(out, combined, parent["config"])
    counts = {}
    for rec in combined:
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
    report.update(original_selected_systems=20, original_converged=13,
        original_nonconverged=7, continuation_checkpoints=len(stage_records),
        continued_converged=sum(r.get("converged", False) for r in stage_records),
        outcome_counts=counts, interrupted_or_incomplete=interrupted,
        continuation_protocol=PROTOCOL_VERSION, parent_run_id=parent["parent_id"],
        parent_archive_sha256=parent["archive_sha256"], unchanged_parent_endpoints=13,
        exclusions_kept_in_original_denominator=True, no_system_replacement=True,
        optimizer_state_restored=False, no_additional_automatic_extensions=True,
        evidence_pair="Original official OC20 initial -> accepted UMA endpoint",
        all_pilot_development=True,
        scientific_limitations=["UMA convergence is not DFT accuracy or a global minimum",
            "All heuristic topologies still need scientific review",
            "Nonconverged or topology-invalid endpoints remain excluded and reported",
            "Case templates are pilot material; Phase 2 requires shortcut review"])
    if interrupted:
        report["status"] = "CONTINUATION_INTERRUPTED_OR_INCOMPLETE"
    return report


def execute(out, parent):
    from geomscope.uma import relax_selected
    restore_parent(parent, out)
    _validate_structures(parent, out)
    _freeze_protocol(parent, out)
    selected = continuation_selection(parent, out)
    support.save_json(out / "continuation_selection.json", selected)
    support.save_json(out / "model_manifest.json", parent["model"])
    support.save_json(out / "run_config.json", parent["config"])
    _snapshot_or_check(out)
    support.save_json(out / "environment_run.json", support.environment())
    support.stage(out, "continuation", "RUNNING", selected_systems=7)
    print("Preserving 13 converged systems; continuing exactly 7 from saved endpoints.", flush=True)
    relax_selected(selected, parent["model"], out / "continuation_stage", **STAGE_SETTINGS)
    records = _valid_stage_records(parent, out)
    report = _report(parent, out, records, interrupted=len(records) != 7)
    support.stage(out, "continuation", "COMPLETE", selected_systems=7,
                  completed_checkpoints=len(records), **report)
    return report


def collect(out, parent):
    restore_parent(parent, out)
    _validate_structures(parent, out)
    _freeze_protocol(parent, out)
    _snapshot_or_check(out)
    records = _valid_stage_records(parent, out)
    state = support.load_json(out / "stage_continuation.json") if (out / "stage_continuation.json").exists() else {}
    report = _report(parent, out, records, interrupted=state.get("state") != "COMPLETE" or len(records) != 7)
    support.collect_logs(out)
    return report


def _snapshot_or_check(out):
    if (out / "code_sha256.json").exists():
        current = {p.relative_to(ROOT).as_posix(): support.digest(p) for p in support.source_files()}
        if current != support.load_json(out / "code_sha256.json"):
            raise ValueError("Continuation code changed for this run ID")
    else:
        support.snapshot(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "collect"))
    parser.add_argument("--parent-zip", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "results")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", args.run_id):
        parser.error("run-id must contain 1-80 letters, digits, underscores or hyphens")
    output_root = args.output_root.resolve()
    out = output_root / args.run_id
    out.mkdir(parents=True, exist_ok=True)
    code = 0
    try:
        with (out / f"{args.mode}.log").open("a", encoding="utf-8") as log, \
                contextlib.redirect_stdout(support.Tee(sys.stdout, log)), \
                contextlib.redirect_stderr(support.Tee(sys.stderr, log)):
            print(f"Phase 1 bounded continuation: {args.mode}, run={args.run_id}", flush=True)
            parent = verify_parent_archive(args.parent_zip)
            print(f"Verified reviewed parent ZIP and {parent['verified_files']} original checksums.", flush=True)
            if args.mode == "run":
                result = execute(out, parent)
            else:
                result = collect(out, parent)
    except Exception as exc:
        message = support.safe_text(traceback.format_exc())
        (out / f"{args.mode}_error.txt").write_text(message, encoding="utf-8")
        support.stage(out, "continuation", "FAILED", error=support.safe_text(exc))
        result = dict(status="CONTINUATION_FAILED", error=support.safe_text(exc), failed_stage=args.mode)
        print(message, file=sys.stderr)
        code = 1
    result.update(phase=1, phase2_ready=False, run_id=args.run_id,
        next_action="Upload this Phase 1 continuation return ZIP for review before Phase 2",
        contains_model_weights=False, contains_credentials=False,
        scientific_scope="Coordinate-derived evidence; not a DFT-accuracy benchmark")
    support.save_json(out / "summary.json", result)
    try:
        support.archive(out, output_root)
    except Exception as exc:
        try:
            support.diagnostic_archive(out, output_root, exc)
        except Exception:
            print(support.safe_text(traceback.format_exc()), file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
