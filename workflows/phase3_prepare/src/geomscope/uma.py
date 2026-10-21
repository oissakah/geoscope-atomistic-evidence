"""Pinned UMA preparation and resumable, constrained ASE FIRE relaxations.

Model weights live in an explicit cache outside the results directory. Only
the three-file manifest, clean endpoint structures, optimizer logs, trajectories
and per-system audit records belong in a return archive. Production inference
always uses CUDA and the OC20 task; CPU calculators are injected only by tests
by patching the private ``_create_runtime`` boundary.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


MODEL_NAME = "uma-s-1p2p1"
MODEL_REPO = "facebook/UMA"
FAIRCHEM_VERSION = "2.23.0"
MODEL_FILES = {
    "checkpoint": "checkpoints/uma-s-1p2p1.pt",
    "atom_refs": "references/iso_atom_elem_refs.yaml",
    "form_elem_refs": "references/form_elem_refs.yaml",
}
INFERENCE_SETTINGS = {
    "tf32": False, "compile": False, "merge_mole": False,
    "activation_checkpointing": True, "execution_mode": "general",
    "internal_graph_gen_version": 2, "base_precision_dtype": "float32",
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    return value


def _hash_json(value: Any) -> str:
    data = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(_jsonable(value), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _versions() -> dict:
    result = {}
    for package in ("fairchem-core", "torch", "ase", "numpy", "scipy", "huggingface-hub", "nvalchemi-toolkit-ops"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    return result


def _outside_results(path: Path, results: Path) -> None:
    if path.resolve().is_relative_to(results.resolve()):
        raise ValueError("Model cache and weight files must be outside the results directory")


def prepare_model(cache_dir: Path, out_dir: Path, revision=None) -> dict:
    """Resolve a full Hub commit, download exactly three model files, hash them.

    Uses Hugging Face's existing login or HF_TOKEN implicitly; tokens are never
    accepted as arguments or included in a manifest. ``revision=None`` resolves
    main once, after which every download uses the resolved 40-character SHA.
    The returned manifest is also saved as out_dir/model_manifest.json. Request
    gated UMA access and authenticate before invoking this function.
    """
    cache_dir, out_dir = Path(cache_dir).resolve(), Path(out_dir).resolve()
    _outside_results(cache_dir, out_dir)
    from huggingface_hub import HfApi, hf_hub_download

    try:
        info = HfApi().model_info(MODEL_REPO, revision=revision or "main")
        frozen_revision = info.sha
        if not isinstance(frozen_revision, str) or re.fullmatch(r"[0-9a-fA-F]{40}", frozen_revision) is None:
            raise ValueError("Hub did not return a full commit SHA")
        files = {}
        for role, repo_path in MODEL_FILES.items():
            local = Path(hf_hub_download(repo_id=MODEL_REPO, filename=repo_path,
                                        revision=frozen_revision, cache_dir=str(cache_dir))).resolve()
            _outside_results(local, out_dir)
            files[role] = {"path": str(local), "repo_path": repo_path,
                           "sha256": _sha256(local), "size_bytes": local.stat().st_size}
    except Exception as exc:
        # HTTP errors can contain signed URLs or auth context; never archive them.
        raise RuntimeError(f"UMA preparation failed ({type(exc).__name__}); verify gated model access and connectivity") from None
    manifest = {
        "schema_version": 1, "model_name": MODEL_NAME, "repo_id": MODEL_REPO,
        "revision": frozen_revision.lower(), "files": files,
        "required_fairchem_version": FAIRCHEM_VERSION,
        "cache_root": str(cache_dir / "fairchem"),
        "preparation_package_versions": _versions(),
        "weights_in_results": False,
    }
    _write_json(out_dir / "model_manifest.json", manifest)
    return manifest


def _check_model(manifest: dict, out_dir: Path) -> None:
    if manifest.get("model_name") != MODEL_NAME or manifest.get("repo_id") != MODEL_REPO:
        raise ValueError("The model manifest must identify facebook/UMA uma-s-1p2p1")
    if re.fullmatch(r"[0-9a-fA-F]{40}", str(manifest.get("revision", ""))) is None:
        raise ValueError("Model manifest requires a full frozen commit SHA")
    if not manifest.get("cache_root"):
        raise ValueError("Model manifest requires an explicit cache_root")
    _outside_results(Path(manifest["cache_root"]), out_dir)
    for role, repo_path in MODEL_FILES.items():
        entry = manifest.get("files", {}).get(role, {})
        path = Path(entry.get("path", "")).resolve()
        _outside_results(path, out_dir)
        if entry.get("repo_path") != repo_path or not path.is_file():
            raise ValueError(f"Missing or invalid model file: {role}")
        if _sha256(path) != entry.get("sha256") or path.stat().st_size != entry.get("size_bytes"):
            raise ValueError(f"Model file integrity check failed: {role}")


def _create_runtime(manifest: dict, seed: int):
    """Production boundary; returns a fresh-calculator factory and GPU provenance."""
    if importlib.metadata.version("fairchem-core") != FAIRCHEM_VERSION:
        raise RuntimeError(f"This protocol requires fairchem-core=={FAIRCHEM_VERSION}")
    # fairchem reads this once during import and otherwise creates ~/.cache/fairchem.
    os.environ["FAIRCHEM_CACHE_DIR"] = str(Path(manifest["cache_root"]).resolve())
    import torch
    from omegaconf import OmegaConf
    from fairchem.core import FAIRChemCalculator, pretrained_mlip
    from fairchem.core.units.mlip_unit import InferenceSettings

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; this research protocol requires a GPU")
    files = manifest["files"]
    predictor = pretrained_mlip.load_predict_unit(
        files["checkpoint"]["path"], device="cuda", seed=seed,
        atom_refs=OmegaConf.load(files["atom_refs"]["path"]),
        form_elem_refs=OmegaConf.load(files["form_elem_refs"]["path"])["refs"],
        inference_settings=InferenceSettings(**INFERENCE_SETTINGS),
    )
    try:
        query = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                               capture_output=True, text=True, timeout=10, check=True)
        drivers = sorted(set(line.strip() for line in query.stdout.splitlines() if line.strip()))
    except (OSError, subprocess.SubprocessError):
        drivers = []
    runtime = {
        "python": sys.version, "platform": platform.platform(), "package_versions": _versions(),
        "device": "cuda", "device_name": torch.cuda.get_device_name(0),
        "device_capability": list(torch.cuda.get_device_capability(0)),
        "torch_cuda_runtime": torch.version.cuda, "cudnn_version": torch.backends.cudnn.version(),
        "nvidia_driver_versions": drivers,
    }
    runtime["runtime_sha256"] = _hash_json(runtime)
    return lambda: FAIRChemCalculator(predictor, task_name="oc20"), runtime


def _clean_atoms(atoms):
    clean = atoms.copy()
    clean.calc = None
    for key in ("energy", "free_energy", "forces", "stress", "magmom", "magmoms"):
        clean.info.pop(key, None)
        if key in clean.arrays:
            del clean.arrays[key]
    return clean


def _mobile_indices(atoms, selected: dict) -> list[int]:
    from ase.constraints import FixAtoms
    fixed = set()
    for constraint in atoms.constraints:
        if isinstance(constraint, FixAtoms):
            fixed.update(int(index) for index in constraint.get_indices())
    default = [index for index in range(len(atoms)) if index not in fixed]
    indices = selected.get("mobile_indices", default)
    if not isinstance(indices, (list, tuple)) or not indices:
        raise ValueError("At least one mobile atom is required")
    if any(isinstance(index, bool) or not isinstance(index, int) for index in indices):
        raise ValueError("mobile_indices must be integers")
    if len(set(indices)) != len(indices) or any(index < 0 or index >= len(atoms) for index in indices):
        raise ValueError("mobile_indices must be unique and in range")
    if set(indices) != set(default):
        raise ValueError("mobile_indices must match all atoms not fixed by FixAtoms")
    return list(indices)


def _safe_error(exc: Exception) -> str:
    message = re.sub(r"https?://\S+", "[URL omitted]", str(exc))
    message = re.sub(r"hf_[A-Za-z0-9]+", "[TOKEN REDACTED]", message)
    message = re.sub(r"(?i)(authorization|token|secret|password)\s*[:=]\s*\S+", r"\1=[REDACTED]", message)
    return f"{type(exc).__name__}: {message[:600]}"


def _resume_record(path: Path, signature: str, expected_hashes: dict, selected: dict) -> dict | None:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        # Phase 3 source preparation retains every finalized outcome. A saved
        # error is evidence, not permission to spend another optimization budget.
        completed = ("converged", "nonconverged", "error", "not_run_after_smoke_failure")
        if record.get("run_signature") != signature or record.get("status") not in completed:
            return None
        if any(record.get(key) != value for key, value in expected_hashes.items()):
            return None
        if _hash_json(record.get("settings")) != expected_hashes["settings_sha256"]:
            return None
        if record.get("pair_id") != selected["pair_id"] or record.get("source_initial_sha256") != selected["source_sha256"]:
            return None
        if record.get("selection") != selected["selection"]:
            return None
        required = ("initial", "final", "optimizer_log", "trajectory") if record["status"] in ("converged", "nonconverged") else ()
        artifacts = record.get("artifacts", {})
        if any(role not in artifacts for role in required):
            return None
        for role, artifact in artifacts.items():
            if role not in ("initial", "final", "optimizer_log", "trajectory"):
                return None
            artifact_path = Path(artifact.get("path", ""))
            if not artifact_path.is_file() or _sha256(artifact_path) != artifact.get("sha256"):
                return None
        record["resumed"] = True
        return record
    except (OSError, ValueError, TypeError):
        return None


def relax_selected(
    selection: list[dict], model_manifest: dict, out_dir: Path, seed: int = 20261019,
    fmax: float = 0.05, steps: int = 300, smoke_systems: int = 3, smoke_only: bool = False,
) -> list[dict]:
    """Relax frozen OC20 starts with ASE FIRE, returning every attempted outcome.

    Each selection item requires initial_path (or initial_structure_path), its
    frozen initial_sha256 (checked before any inference), and a
    pair_id or system_id. Identifiers/group metadata are inherited. Existing
    constraints are preserved. Optional mobile_indices must equal atoms not
    fixed by FixAtoms. Final fmax is the largest constrained force norm on that
    mobile set. Convergence uses a strict force < fmax criterion.

    Smoke systems run first. A computation error in that stage prevents the
    remainder from running and emits explicit not_run_after_smoke_failure
    records. A completed but nonconverged smoke relaxation is retained and does
    not abort the batch. smoke_only=True returns just the first smoke systems.

    Finalized checkpoints, including errors, resume only when the complete frozen
    selection (including source-file hashes), manifest and settings match and
    saved artifact hashes remain valid. Saved errors are not retried. Different signatures use
    separate subdirectories, preserving earlier attempts.
    """
    import numpy as np
    from ase.io import read, write
    from ase.optimize import FIRE

    out_dir = Path(out_dir).resolve()
    if not isinstance(selection, list) or any(not isinstance(item, dict) for item in selection):
        raise ValueError("selection must be a list of dictionaries")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if isinstance(fmax, bool) or not math.isfinite(float(fmax)) or fmax <= 0:
        raise ValueError("fmax must be positive and finite")
    # The prospectively bounded Phase 3 preparation budget is at most 600 FIRE
    # steps from each original selected start; no convergence-based replacement.
    if not isinstance(steps, int) or isinstance(steps, bool) or steps <= 0 or steps > 600:
        raise ValueError("steps must be an integer between 1 and the Phase 3 cap of 600")
    if not isinstance(smoke_systems, int) or isinstance(smoke_systems, bool) or smoke_systems <= 0:
        raise ValueError("smoke_systems must be positive")
    _check_model(model_manifest, out_dir)
    prepared, identities = [], set()
    for item in selection:
        selected = _jsonable(item)
        pair_id = str(selected.get("pair_id", selected.get("system_id", "")))
        if not pair_id or pair_id in identities:
            raise ValueError("Selection IDs must be nonempty and unique")
        identities.add(pair_id)
        source = Path(selected.get("initial_path", selected.get("initial_structure_path", ""))).resolve()
        if not source.is_file():
            raise ValueError(f"Missing initial structure for {pair_id}")
        frozen_hash = selected.get("initial_sha256")
        if not isinstance(frozen_hash, str) or re.fullmatch(r"[0-9a-fA-F]{64}", frozen_hash) is None:
            raise ValueError(f"Selection requires frozen initial_sha256 for {pair_id}")
        source_hash = _sha256(source)
        if source_hash != frozen_hash.lower():
            raise ValueError(f"Frozen initial_sha256 mismatch for {pair_id}; source changed after selection")
        prepared.append({"selection": selected, "pair_id": pair_id,
                         "source": str(source), "source_sha256": source_hash})
    settings = {
        "seed": seed, "fmax_eV_A": float(fmax), "force_criterion": "mobile constrained fmax < threshold",
        "steps_cap": steps, "smoke_systems": smoke_systems, "smoke_only": bool(smoke_only),
        "optimizer": "ase.optimize.FIRE", "optimizer_kwargs": {"dt": 0.1, "maxstep": 0.2},
        "device": "cuda", "task_name": "oc20", "inference": dict(INFERENCE_SETTINGS),
        "required_fairchem_version": FAIRCHEM_VERSION,
    }
    hashes = {"selection_sha256": _hash_json(prepared), "model_manifest_sha256": _hash_json(model_manifest),
              "settings_sha256": _hash_json(settings)}
    signature = _hash_json(hashes)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "relaxation_protocol.json", {**settings, **hashes, "run_signature": signature})
    active = prepared[:min(smoke_systems, len(prepared))] if smoke_only else prepared
    results, calculator_factory, runtime, model_error = [], None, None, None
    smoke_failed = False
    for index, item in enumerate(active):
        pair_id = item["pair_id"]
        slug = hashlib.sha256(pair_id.encode("utf-8")).hexdigest()[:16]
        directory = out_dir / "relaxations" / slug / signature[:16]
        checkpoint = directory / "record.json"
        existing = _resume_record(checkpoint, signature, hashes, item)
        if existing is not None:
            results.append(existing)
            if index < smoke_systems and existing["status"] == "error":
                smoke_failed = True
            continue
        if checkpoint.exists():
            raise ValueError("An existing finalized checkpoint failed identity or artifact verification; refusing an automatic retry")
        if directory.exists() and any(directory.iterdir()):
            raise ValueError("An interrupted attempt contains artifacts without a verified finalized record; preserve them for review rather than automatically retrying")
        directory.mkdir(parents=True, exist_ok=True)
        record = {
            **item["selection"],
            "selection": item["selection"],
            "pair_id": pair_id, "source_initial_path": item["source"], "source_initial_sha256": item["source_sha256"],
            "initial_path": None, "final_path": None, "converged": False,
            "final_fmax_eV_A": None, "steps": 0, "elapsed_seconds": 0.0,
            "status": "error", "error": None, "resumed": False, "settings": settings,
            **hashes, "run_signature": signature,
            "model_provenance": {"model_name": model_manifest["model_name"], "repo_id": model_manifest["repo_id"],
                                 "revision": model_manifest["revision"],
                                 "file_sha256": {role: entry["sha256"] for role, entry in model_manifest["files"].items()}},
        }
        if smoke_failed:
            record.update(status="not_run_after_smoke_failure", error="An earlier smoke computation failed; no relaxation attempted")
            _write_json(checkpoint, record)
            results.append(record)
            continue
        start, atoms, optimizer = time.perf_counter(), None, None
        try:
            atoms = _clean_atoms(read(item["source"]))
            mobile = _mobile_indices(atoms, item["selection"])
            initial_path = directory / "initial.extxyz"
            write(initial_path, atoms, format="extxyz", write_results=False)
            record["initial_path"] = str(initial_path)
            record["mobile_indices"] = mobile
            record["constraints"] = [_jsonable(c.todict()) for c in atoms.constraints]
            if calculator_factory is None and model_error is None:
                try:
                    calculator_factory, runtime = _create_runtime(model_manifest, seed)
                except Exception as exc:
                    model_error = exc
            if model_error is not None:
                raise RuntimeError(f"GPU model initialization failed: {_safe_error(model_error)}; verify CUDA, packages and pinned files")
            record["runtime"] = runtime
            atoms.calc = calculator_factory()
            optimizer = FIRE(atoms, trajectory=str(directory / "optimizer.traj"),
                             logfile=str(directory / "optimizer.log"), dt=0.1, maxstep=0.2)
            optimizer.run(fmax=float(fmax), steps=steps)
            forces = np.asarray(atoms.get_forces(apply_constraint=True), dtype=float)
            if forces.shape != (len(atoms), 3) or not np.isfinite(forces).all():
                raise ValueError("Calculator returned invalid or nonfinite forces")
            final_fmax = float(np.linalg.norm(forces[mobile], axis=1).max())
            converged = final_fmax < float(fmax)
            record.update(converged=converged, final_fmax_eV_A=final_fmax,
                          status="converged" if converged else "nonconverged")
        except Exception as exc:
            record.update(status="error", error=_safe_error(exc))
            if index < smoke_systems:
                smoke_failed = True
        finally:
            if optimizer is not None:
                record["steps"] = int(optimizer.nsteps)
                try:
                    optimizer.close()
                except Exception as exc:
                    record.update(status="error", converged=False, error=_safe_error(exc))
            if atoms is not None:
                final_path = directory / "final.extxyz"
                try:
                    write(final_path, _clean_atoms(atoms), format="extxyz", write_results=False)
                    record["final_path"] = str(final_path)
                except Exception as exc:
                    record.update(status="error", converged=False, error=_safe_error(exc))
            record["elapsed_seconds"] = time.perf_counter() - start
            record["optimizer_log_path"] = str(directory / "optimizer.log")
            record["trajectory_path"] = str(directory / "optimizer.traj")
            record["artifacts"] = {
                role: {"path": record[role + "_path"], "sha256": _sha256(Path(record[role + "_path"]))}
                for role in ("initial", "final", "optimizer_log", "trajectory")
                if record[role + "_path"] is not None and Path(record[role + "_path"]).is_file()
            }
            if record["status"] == "error" and index < smoke_systems:
                smoke_failed = True
            _write_json(checkpoint, record)
        results.append(record)
    _write_json(out_dir / "relaxation_records.json", results)
    return results
