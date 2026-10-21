#!/usr/bin/env python3
"""Prepare, run and collect a bounded UMA/OC20-Dense Phase 1 pilot."""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import shutil
import sys
import time
import traceback
import unittest
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
RESULT_BYTES_LIMIT = 512 * 1024 * 1024
DEFAULTS = dict(seed=20261019, n_systems=20, max_atoms=180,
                min_adsorbate_atoms=3, optimizer="FIRE", fmax=0.05,
                max_steps=300, model_name="uma-s-1p2p1", task_name="oc20",
                smoke_systems=3, smoke_only=False, thresholds_A=[0.1, 0.5],
                threshold_margin_A=0.005, anchor_max_displacement_A=0.02)


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def jsonl(path, records):
    Path(path).write_text("".join(json.dumps(r, allow_nan=False) + "\n" for r in records), encoding="utf-8")


def safe_text(value):
    return re.sub(r"hf_[A-Za-z0-9]{12,}", "[REDACTED_HF_TOKEN]", str(value))


class Tee:
    def __init__(self, terminal, log):
        self.terminal, self.log = terminal, log
    def write(self, text):
        self.terminal.write(text)
        self.log.write(safe_text(text))
        self.log.flush()
        return len(text)
    def flush(self):
        self.terminal.flush()
        self.log.flush()


def config_from(path):
    config = DEFAULTS.copy()
    supplied = load_json(path)
    if not isinstance(supplied, dict) or set(supplied) - set(config):
        raise ValueError("Configuration contains unknown keys; credentials never belong in configuration")
    config.update(supplied)
    for key, low, high in (("n_systems", 1, 100), ("max_atoms", 10, 1000),
                           ("min_adsorbate_atoms", 3, 100), ("max_steps", 1, 300),
                           ("smoke_systems", 1, 10), ("seed", 0, 2**32 - 1)):
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise ValueError(f"Invalid integer configuration: {key}")
    if config["model_name"] != "uma-s-1p2p1" or config["task_name"] != "oc20" or config["optimizer"] != "FIRE":
        raise ValueError("This pilot pins uma-s-1p2p1, oc20 and FIRE; changing them requires a reviewed protocol")
    for key in ("fmax", "threshold_margin_A", "anchor_max_displacement_A"):
        if type(config[key]) not in (int, float) or not math.isfinite(config[key]) or config[key] <= 0:
            raise ValueError(f"Invalid positive configuration: {key}")
    thresholds = config["thresholds_A"]
    if not isinstance(thresholds, list) or not thresholds:
        raise ValueError("thresholds_A must be a nonempty list")
    if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in thresholds):
        raise ValueError("Invalid thresholds_A")
    if len(thresholds) != len(set(thresholds)):
        raise ValueError("thresholds_A values must be distinct")
    if type(config["smoke_only"]) is not bool:
        raise ValueError("smoke_only must be boolean")
    return config


def environment():
    packages = {}
    for name in ("numpy", "ase", "scipy", "torch", "fairchem-core", "huggingface-hub"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                packages=packages, slurm={key: os.environ.get(key) for key in
                ("SLURM_JOB_ID", "SLURM_JOB_PARTITION", "SLURM_CPUS_PER_TASK")})


def source_files():
    files = [p for p in ROOT.iterdir() if p.is_file() and p.suffix in {".py", ".sh", ".sbatch", ".md"}]
    for folder in ("src", "tests"):
        files.extend(p for p in (ROOT / folder).rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(files)


def snapshot(out):
    hashes = {}
    for source in source_files():
        relative = source.relative_to(ROOT)
        target = out / "code_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[relative.as_posix()] = digest(source)
    save_json(out / "code_sha256.json", hashes)


def stage(out, mode, state, **extra):
    save_json(out / f"stage_{mode}.json", dict(stage=mode, state=state, time_unix=time.time(), **extra))


def freeze_inputs(out, selected_systems):
    names = ("selection.json", "model_manifest.json", "run_config.json", "code_sha256.json")
    stage(out, "prepare", "COMPLETE", selected_systems=selected_systems,
          prepared_artifact_sha256={name: digest(out / name) for name in names})


def prepare(out, cache, config):
    from geomscope.data import prepare_data
    from geomscope.uma import prepare_model
    snapshot(out)
    save_json(out / "environment_prepare.json", environment())
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    report = unittest.TextTestRunner(verbosity=1).run(suite)
    save_json(out / "self_tests.json", dict(tests_run=report.testsRun,
              failures=len(report.failures), errors=len(report.errors), success=report.wasSuccessful()))
    if not report.wasSuccessful():
        raise RuntimeError("Bundled self-tests failed; see self_tests.json and prepare.log")
    selected = prepare_data(cache / "oc20dense", out, systems=config["n_systems"],
                seed=config["seed"], max_atoms=config["max_atoms"],
                min_adsorbate_atoms=config["min_adsorbate_atoms"])
    print(f"Frozen {len(selected)} systems before UMA inference.")
    prepare_model(cache / "uma", out)
    freeze_inputs(out, len(selected))
    return dict(status="PREPARED_PENDING_GPU", selected_systems=len(selected))


def bonds(atoms, indices):
    """Distance-based graph hypothesis; scientific review is still required."""
    import numpy as np
    from ase.data import covalent_radii
    from ase.geometry import find_mic
    edges = []
    for n, i in enumerate(indices):
        for j in indices[n + 1:]:
            distance = float(np.linalg.norm(find_mic(atoms.positions[j] - atoms.positions[i], atoms.cell, atoms.pbc)[0]))
            if 0.25 < distance < 1.25 * (covalent_radii[atoms.numbers[i]] + covalent_radii[atoms.numbers[j]]):
                edges.append([i, j])
    return edges


def measured_record(entry, a, b, final_path, config, *, synthetic=False, pair_id=None):
    from geomscope.geometry import analyze_pair
    ads = entry["adsorbate_indices"]
    initial_bonds, final_bonds = bonds(a, ads), bonds(b, ads)
    declared = sorted(sorted(edge) for edge in entry["adsorbate_bonds"])
    if sorted(initial_bonds) != declared or sorted(final_bonds) != declared:
        raise ValueError("Initial/final distance-based bond graphs differ; topology needs explicit scientific review")
    result = analyze_pair(a, b, entry["mobile_indices"], ads, entry["anchor_indices"], entry["adsorbate_bonds"])
    if result["anchor_max_displacement_A"] > config["anchor_max_displacement_A"]:
        raise ValueError("Fixed slab anchor drift exceeds the configured frame tolerance")
    for definition in result["metric_definitions"].values():
        definition["atom_subset"] = definition["atom_indices"]
        definition["pbc"] = a.pbc.tolist()
    result["validation"].update(anchor_drift_cutoff_applied=True,
                anchor_max_displacement_cutoff_A=config["anchor_max_displacement_A"])
    return dict(pair_id=pair_id or entry["pair_id"], system_id=entry["system_id"],
        group_id=entry["group_id"], config_id=entry.get("config_id"), split="pilot_development",
        origin="synthetic_control" if synthetic else "measured_endpoint_pair",
        measurements={k: result[k] for k in ("mobile_rmsd_A", "adsorbate_frame_rmsd_A", "internal_rmsd_A")},
        metric_definitions=result["metric_definitions"], geometry_audit=result,
        atom_correspondence_confirmed=True, topology_reviewed=False,
        correspondence_basis="One inherited fixed atom order; no atom permutation or symmetry matching",
        topology_basis="Unreviewed distance-based connected graph; equal graph required across endpoints",
        provenance=dict(workflow_a="UMA final coordinates" if synthetic else "official OC20-Dense initial placement",
            workflow_b="synthetic adsorbate translation by +0.7 A along stored x" if synthetic else "UMA oc20 FIRE relaxation endpoint",
            source_hashes={"initial": digest(entry["initial_path"]), "final": digest(final_path)},
            run_id_a=entry["pair_id"] + (":UMA" if synthetic else ":initial"),
            run_id_b=entry["pair_id"] + (":synthetic" if synthetic else ":UMA")),
        energetic_or_convergence_claims_enabled=False,
        caveat="Synthetic controls have no evaluated energy, force or convergence" if synthetic else
               "Geometric measurements do not validate DFT accuracy or a global energy minimum")


def analyze(out, records, config, *, demo_only=False):
    import numpy as np
    from ase.io import read, write
    from geomscope.cases import build_cases
    pairs, rejected, metrics = [], [], []
    for entry in records:
        try:
            if not entry.get("converged") or not entry.get("final_path"):
                raise ValueError("No converged UMA endpoint; retained in relaxation_results.json, excluded from claim pilot")
            a, b = read(entry["initial_path"]), read(entry["final_path"])
            record = measured_record(entry, a, b, entry["final_path"], config)
            if demo_only:
                record.update(origin="synthetic_control", demo_only=True)
                record["provenance"].update(workflow_a="synthetic demonstration initial", workflow_b="synthetic demonstration translated endpoint")
            pairs.append(record)
            metrics.append(dict(pair_id=record["pair_id"], system_id=record["system_id"],
                origin=record["origin"], converged="not_applicable" if demo_only else True, **record["measurements"]))
        except Exception as exc:
            rejected.append(dict(pair_id=entry.get("pair_id"), reason=safe_text(exc)))
            continue
        # Separate, labelled causal control. No inherited calculator results.
        try:
            c = b.copy()
            c.calc = None
            c.info = {}
            c.positions[entry["adsorbate_indices"]] += np.array([0.7, 0.0, 0.0])
            control_dir = out / "controls"
            control_dir.mkdir(exist_ok=True)
            control_path = control_dir / (entry["pair_id"] + "_translated.extxyz")
            write(control_path, c, format="extxyz", write_results=False)
            control_entry = dict(entry, initial_path=entry["final_path"])
            control = measured_record(control_entry, b, c, control_path, config,
                                      synthetic=True, pair_id=entry["pair_id"] + "_rigid_translation")
            if demo_only:
                control["demo_only"] = True
                control["provenance"]["workflow_a"] = "synthetic demonstration endpoint"
            pairs.append(control)
            metrics.append(dict(pair_id=control["pair_id"], system_id=control["system_id"],
                origin=control["origin"], converged="not_applicable", **control["measurements"]))
        except Exception as exc:
            rejected.append(dict(pair_id=entry["pair_id"] + "_rigid_translation", reason=safe_text(exc)))
    public, gold, audit = build_cases(pairs, config["thresholds_A"],
            margin_A=config["threshold_margin_A"], seed=config["seed"])
    if demo_only:
        for record in public + gold:
            record["demo_only"] = True
    jsonl(out / "pair_measurements.jsonl", pairs)
    jsonl(out / "cases_public.jsonl", public)
    jsonl(out / "cases_gold_DO_NOT_SEND_TO_MODELS.jsonl", gold)
    save_json(out / "case_audit.json", audit)
    save_json(out / "measurement_rejections.json", rejected)
    fields = ["pair_id", "system_id", "origin", "converged", "mobile_rmsd_A", "adsorbate_frame_rmsd_A", "internal_rmsd_A"]
    with (out / "measurements.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(metrics)
    measured = sum(p["origin"] == "measured_endpoint_pair" for p in pairs)
    return dict(status="READY_FOR_SCIENTIFIC_REVIEW" if measured == config["n_systems"] else "PARTIAL_NEEDS_REVIEW",
        measured_pairs=measured, synthetic_pairs=len(pairs) - measured, cases=len(public), rejected=len(rejected),
        label_counts=dict(Counter(g["expected"] for g in gold)),
        review_required=["All heuristic adsorbate topologies", "Convergence and force logs", "Initial/final overlays",
                         "Metric definitions and selected atom masks", "Case shortcuts and class balance"],
        all_pilot_development=True, template_shortcut_risk=True)


def run(out, config):
    from geomscope.uma import relax_selected
    if not (out / "stage_prepare.json").exists() or load_json(out / "stage_prepare.json").get("state") != "COMPLETE":
        raise RuntimeError("Preparation did not complete. Return this diagnostic ZIP before using GPU inference")
    prepared = load_json(out / "stage_prepare.json").get("prepared_artifact_sha256", {})
    for name in ("selection.json", "model_manifest.json", "run_config.json", "code_sha256.json"):
        if prepared.get(name) != digest(out / name):
            raise RuntimeError(f"Frozen prepared artifact changed or is untracked: {name}")
    expected = load_json(out / "code_sha256.json")
    current = {p.relative_to(ROOT).as_posix(): digest(p) for p in source_files()}
    if current != expected:
        raise RuntimeError("Source code changed after data preparation; start a new run ID")
    save_json(out / "environment_run.json", environment())
    selected = load_json(out / "selection.json")["selection"]
    model = load_json(out / "model_manifest.json")
    records = relax_selected(selected, model, out, seed=config["seed"], fmax=config["fmax"],
                    steps=config["max_steps"], smoke_systems=config["smoke_systems"], smoke_only=config["smoke_only"])
    save_json(out / "relaxation_results.json", records)
    result = analyze(out, records, config)
    stage(out, "run", "COMPLETE", **result)
    return result


def demo(out, config):
    """Analytic coordinate fixture, explicitly excluded from research results."""
    from ase import Atoms
    from ase.constraints import FixAtoms
    from ase.io import write
    a = Atoms("Cu5COH", positions=[[1, 1, 1], [5, 1, 1], [1, 5, 1], [5, 5, 1],
            [3, 3, 2], [3, 3, 4], [4.2, 3, 4], [2.2, 3.5, 4]], cell=[15, 15, 15], pbc=True)
    a.set_tags([0, 0, 0, 0, 1, 2, 2, 2])
    a.set_constraint(FixAtoms(indices=[0, 1, 2, 3]))
    b = a.copy()
    b.positions[[5, 6, 7]] += [0.7, 0, 0]
    folder = out / "demo_inputs"
    folder.mkdir(exist_ok=True)
    initial, final = folder / "initial.extxyz", folder / "final.extxyz"
    write(initial, a, write_results=False)
    write(final, b, write_results=False)
    entry = dict(pair_id="SYNTHETIC_DEMO_ONLY", system_id="SYNTHETIC_DEMO_ONLY", group_id="SYNTHETIC_DEMO_ONLY",
        initial_path=str(initial), final_path=str(final), mobile_indices=[4, 5, 6, 7],
        adsorbate_indices=[5, 6, 7], anchor_indices=[0, 1, 2, 3], adsorbate_bonds=bonds(a, [5, 6, 7]), converged=True)
    result = analyze(out, [entry], config, demo_only=True)
    result.update(status="DEMO_ONLY", measured_pairs=0, research_results=False)
    stage(out, "demo", "COMPLETE", **result)
    return result


def collect_logs(out):
    metadata = out / "launcher_jobs.json"
    if not metadata.exists():
        return
    jobs = load_json(metadata)
    folder = Path(jobs.get("logs_dir", ROOT / "logs"))
    for key, stem in (("prepare_job_id", "prepare"), ("gpu_job_id", "phase1"), ("collect_job_id", "collect")):
        number = str(jobs.get(key, ""))
        if not number.isdigit():
            continue
        source = folder / f"{stem}-{number}.log"
        if source.is_file() and not source.is_symlink():
            target = out / "slurm_logs" / source.name
            target.parent.mkdir(exist_ok=True)
            with source.open("rb") as stream:
                stream.seek(max(0, source.stat().st_size - 5 * 1024 * 1024))
                text = stream.read().decode("utf-8", errors="replace")
            target.write_text(safe_text(text), encoding="utf-8")


def archive(out, output_root):
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS.json")
    if any(p.is_symlink() for p in files):
        raise ValueError("Result directory contains a symlink; refusing to follow it into the return ZIP")
    if sum(p.stat().st_size for p in files) > RESULT_BYTES_LIMIT:
        raise ValueError("Results exceed the 512 MiB bounded return size; preserve run directory and inspect logs")
    save_json(out / "SHA256SUMS.json", {p.relative_to(out).as_posix(): digest(p) for p in files})
    folder = output_root / "return_zips"
    folder.mkdir(exist_ok=True)
    target = folder / f"{out.name}_phase1_results.zip"
    temporary = target.with_suffix(".zip.part")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as z:
        for path in files + [out / "SHA256SUMS.json"]:
            z.write(path, (Path(out.name) / path.relative_to(out)).as_posix())
    temporary.replace(target)
    print(f"Return ZIP: {target}")
    return target


def diagnostic_archive(out, output_root, error):
    """Replace any earlier-stage ZIP with a bounded, explicitly failed artifact."""
    summary = load_json(out / "summary.json")
    summary.setdefault("scientific_status_before_packaging", summary.get("status"))
    summary.update(status="PACKAGING_FAILED", packaging_error=safe_text(error),
                   return_archive_kind="bounded_diagnostic", full_results_remain_on_disk=True)
    save_json(out / "summary.json", summary)
    payload = {}
    inventory = []
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(out).as_posix()
        inventory.append(dict(path=relative, bytes=path.stat().st_size, symlink=path.is_symlink()))
        if path.is_symlink() or path.name == "SHA256SUMS.json":
            continue
        allowed = path.parent == out and path.suffix in {".json", ".txt", ".log"}
        allowed = allowed or path.parent == out / "slurm_logs"
        if allowed and len(payload) < 50:
            with path.open("rb") as stream:
                # Logs are bounded tails; JSON manifests are included only whole.
                if path.stat().st_size > 512 * 1024:
                    if path.suffix != ".log":
                        continue
                    stream.seek(path.stat().st_size - 512 * 1024)
                payload[relative] = stream.read()
    payload["summary.json"] = (out / "summary.json").read_bytes()
    payload["diagnostic_inventory.json"] = json.dumps(dict(files=inventory[:2000],
        inventory_truncated=len(inventory) > 2000, full_file_count=len(inventory)), indent=2).encode()
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    payload["SHA256SUMS.json"] = json.dumps(hashes, indent=2).encode()
    folder = output_root / "return_zips"
    folder.mkdir(exist_ok=True)
    target = folder / f"{out.name}_phase1_results.zip"
    temporary = target.with_suffix(".zip.part")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as z:
        for relative, data in payload.items():
            z.writestr(f"{out.name}/{relative}", data)
    temporary.replace(target)
    print(f"Diagnostic return ZIP: {target}")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "run", "collect", "demo"])
    parser.add_argument("--config", type=Path, default=ROOT / "config/pilot.json")
    parser.add_argument("--output-root", type=Path, default=ROOT / "results")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "cache")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", args.run_id):
        parser.error("run-id must contain 1-80 letters, digits, underscores or hyphens")
    output_root, cache = args.output_root.resolve(), args.cache_dir.resolve()
    out = output_root / args.run_id
    if cache == output_root or output_root in cache.parents:
        parser.error("Cache must be outside results; model weights must never enter the return ZIP")
    out.mkdir(parents=True, exist_ok=True)
    result, code = {}, 0
    try:
        with (out / (args.mode + ".log")).open("a", encoding="utf-8") as log, \
             contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
            print(f"Phase 1 mode={args.mode}, run={args.run_id}")
            if args.mode == "collect":
                if (out / "summary.json").exists():
                    result = load_json(out / "summary.json")
                else:
                    result = dict(status="NO_COMPLETED_STAGE", error="No summary survived; inspect collected Slurm logs")
                for mode in ("run", "prepare"):
                    state_path = out / f"stage_{mode}.json"
                    if state_path.exists() and load_json(state_path).get("state") == "RUNNING":
                        result.update(status="INTERRUPTED_OR_TIMEOUT", interrupted_stage=mode)
                        break
                if result.get("status") == "PREPARED_PENDING_GPU":
                    result.update(status="GPU_STAGE_DID_NOT_COMPLETE")
                collect_logs(out)
            else:
                config = config_from(args.config)
                config_path = out / "run_config.json"
                if config_path.exists() and load_json(config_path) != config:
                    raise ValueError("Configuration changed for an existing run ID; choose a new run ID")
                if args.mode == "prepare" and (out / "stage_prepare.json").exists():
                    raise ValueError("Preparation was already attempted; use a new run ID")
                save_json(config_path, config)
                stage(out, args.mode, "RUNNING")
                if args.mode == "prepare":
                    result = prepare(out, cache, config)
                elif args.mode == "run":
                    result = run(out, config)
                else:
                    result = demo(out, config)
    except Exception as exc:
        message = safe_text(traceback.format_exc())
        (out / (args.mode + "_error.txt")).write_text(message, encoding="utf-8")
        stage(out, args.mode, "FAILED", error=safe_text(exc))
        result = dict(status="FAILED", failed_stage=args.mode, error=safe_text(exc))
        print(message, file=sys.stderr)
        code = 1
    result.update(phase=1, phase2_ready=False, run_id=args.run_id,
                  next_action="Upload the Phase 1 results ZIP here for review before Phase 2",
                  contains_model_weights=False, contains_credentials=False,
                  scientific_scope="Coordinate-derived measurement definitions; not a DFT-accuracy benchmark")
    save_json(out / "summary.json", result)
    try:
        archive(out, output_root)
    except Exception as exc:
        print(safe_text(traceback.format_exc()), file=sys.stderr)
        try:
            diagnostic_archive(out, output_root, exc)
        except Exception:
            print(safe_text(traceback.format_exc()), file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
