"""Pinned public OC20-Dense initial configurations; no LMDB or pickle loading.

The official 2023 validation ASE archive contains initial configurations, not
matched DFT final endpoints.  Filename-derived IDs identify a placement and its
adsorbate/surface group.  They do not establish independence across groups.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tarfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen

import numpy as np
from ase.constraints import FixAtoms
from ase.data import covalent_radii
from ase.geometry import find_mic
from ase.io import read, write
from ase.io.trajectory import Trajectory

from geomscope.geometry import analyze_pair


SOURCE_URL = (
    "https://dl.fbaipublicfiles.com/opencatalystproject/data/neurips_2023/"
    "oc20dense_is2re_val_ase.tar.gz"
)
ARCHIVE_NAME = "oc20dense_is2re_val_ase.tar.gz"
ARCHIVE_SHA256 = "f9b98c10865abc0641a93d4ae0a90bbb49ccae946cc9a6894d5b11d9647c1fad"
ARCHIVE_BYTES = 13_109_240
MAX_DOWNLOAD_BYTES = 30_000_000
MAX_EXTRACTED_BYTES = 100_000_000
MAX_MEMBERS = 20_000
_FILENAME = re.compile(r"(?P<system>\d+_\d+_\d+)_(?P<config>(?:rand|heur)\d+)\.traj")


class DataPreparationError(RuntimeError):
    """A diagnostic selection.json is retained when eligible systems run out."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _save_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _download_pinned_archive(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / ARCHIVE_NAME
    if destination.is_symlink():
        raise DataPreparationError("The cached archive must not be a symbolic link")
    if destination.exists():
        return destination
    partial = destination.with_name(destination.name + ".part")
    if partial.exists() or partial.is_symlink():
        raise DataPreparationError(f"An incomplete/concurrent download exists: {partial}")
    request = Request(SOURCE_URL, headers={"User-Agent": "GeomScope-Phase1/1.0"})
    owns_partial = False
    try:
        with urlopen(request, timeout=60) as response, partial.open("xb") as output:
            owns_partial = True
            supplied_length = response.headers.get("Content-Length")
            if supplied_length and int(supplied_length) > MAX_DOWNLOAD_BYTES:
                raise DataPreparationError("Official archive exceeds the 30 MB download limit")
            total = 0
            digest = hashlib.sha256()
            while True:
                chunk = response.read(min(1024 * 1024, MAX_DOWNLOAD_BYTES - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise DataPreparationError("Official archive exceeds the 30 MB download limit")
                output.write(chunk)
                digest.update(chunk)
            if total != ARCHIVE_BYTES or digest.hexdigest() != ARCHIVE_SHA256:
                raise DataPreparationError("Official archive size/SHA256 differs from the frozen source")
        os.replace(partial, destination)
    except BaseException:
        # Only this operation's exact partial file is removed, never a directory.
        if owns_partial and partial.is_file() and not partial.is_symlink():
            partial.unlink()
        raise
    return destination


def _safe_extract_archive(archive_path: Path, cache_dir: Path) -> list[dict]:
    """Extract regular .traj members under one fixed directory, with budgets.

    This format-validation helper does not certify origin; prepare_data checks
    the pinned source hash before calling it.  Tests may use synthetic archives
    directly without presenting them as official observations.
    """
    cache_dir = Path(cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    top = cache_dir / "ase_val_inputs"
    if top.is_symlink():
        raise ValueError("Archive destination ase_val_inputs must not be a symbolic link")
    top.mkdir(exist_ok=True)
    manifest = []
    seen = set()
    total = 0
    with tarfile.open(archive_path, mode="r|gz") as archive:
        for member_count, member in enumerate(archive, start=1):
            if member_count > MAX_MEMBERS:
                raise ValueError("Archive exceeds the 20,000-member limit")
            name = member.name
            parts = PurePosixPath(name).parts
            if "\\" in name or ":" in name or name.startswith("/") or ".." in parts:
                raise ValueError(f"Unsafe archive path: {name}")
            if member.isdir() and parts == ("ase_val_inputs",):
                if name in seen:
                    raise ValueError(f"Duplicate archive member: {name}")
                seen.add(name)
                continue
            if not member.isreg():
                raise ValueError(f"Only regular trajectory files are accepted: {name}")
            if len(parts) != 2 or parts[0] != "ase_val_inputs" or not _FILENAME.fullmatch(parts[1]):
                raise ValueError(f"Unexpected archive member layout: {name}")
            if name in seen:
                raise ValueError(f"Duplicate archive member: {name}")
            seen.add(name)
            if member.size < 0:
                raise ValueError("Archive member has a negative size")
            total += member.size
            if total > MAX_EXTRACTED_BYTES:
                raise ValueError("Archive exceeds the 100 MB decompressed limit")
            destination = top / parts[1]
            if destination.is_symlink() or destination.is_dir():
                raise ValueError(f"Unsafe existing extraction target: {destination}")
            if not destination.resolve().is_relative_to(cache_dir):
                raise ValueError(f"Extraction target escapes cache: {destination}")
            partial = destination.with_name(destination.name + ".part")
            if partial.exists() or partial.is_symlink():
                raise ValueError(f"Incomplete/concurrent extraction target: {partial}")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"Cannot read trajectory member: {name}")
            digest = hashlib.sha256()
            copied = 0
            owns_partial = False
            try:
                with stream, partial.open("xb") as output:
                    owns_partial = True
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        copied += len(chunk)
                        if copied > member.size:
                            raise ValueError(f"Member size mismatch: {name}")
                        output.write(chunk)
                        digest.update(chunk)
                if copied != member.size:
                    raise ValueError(f"Truncated trajectory member: {name}")
                os.replace(partial, destination)
            except BaseException:
                if owns_partial and partial.is_file() and not partial.is_symlink():
                    partial.unlink()
                raise
            match = _FILENAME.fullmatch(parts[1])
            manifest.append({
                "source_member": name,
                "path": str(destination),
                "source_sha256": digest.hexdigest(),
                "bytes": copied,
                "system_id": match["system"],
                "config_id": match["config"],
            })
    if not manifest:
        raise ValueError("Archive contains no supported ASE trajectories")
    return manifest


def _rank(seed: int, *identifiers: str) -> str:
    return hashlib.sha256(json.dumps([seed, *identifiers], separators=(",", ":")).encode()).hexdigest()


def _initial_structure(member: dict, max_atoms: int, min_adsorbate_atoms: int):
    path = Path(member["path"])
    if path.is_symlink() or _sha256(path) != member["source_sha256"]:
        raise ValueError("Cached trajectory no longer matches its archive-member hash")
    with Trajectory(str(path), mode="r") as trajectory:
        if len(trajectory) != 1:
            raise ValueError("Initial-configuration archive member must contain exactly one frame")
        atoms = trajectory[0]
    if len(atoms) > max_atoms:
        raise ValueError(f"Atom count {len(atoms)} exceeds max_atoms={max_atoms}")
    tags = atoms.get_tags()
    if not set(map(int, tags)) <= {0, 1, 2}:
        raise ValueError("Unsupported atom tags; expected 0=subsurface,1=surface,2=adsorbate")
    adsorbate = np.where(tags == 2)[0].tolist()
    mobile = np.where(tags != 0)[0].tolist()
    anchors = np.where(tags == 0)[0].tolist()
    if len(adsorbate) < min_adsorbate_atoms:
        raise ValueError(f"Only {len(adsorbate)} adsorbate atoms; need {min_adsorbate_atoms}")
    fixed = set()
    if not atoms.constraints:
        raise ValueError("Explicit FixAtoms constraints are required")
    for constraint in atoms.constraints:
        if not isinstance(constraint, FixAtoms):
            raise ValueError("Only FixAtoms constraints are supported")
        fixed.update(map(int, constraint.get_indices()))
    if fixed != set(anchors):
        raise ValueError("FixAtoms indices must exactly match tag-0 anchors")
    bonds = []
    for offset, i in enumerate(adsorbate):
        for j in adsorbate[offset + 1:]:
            delta = find_mic(atoms.positions[j] - atoms.positions[i], atoms.cell, atoms.pbc)[0]
            distance = float(np.linalg.norm(delta))
            cutoff = 1.25 * (covalent_radii[atoms.numbers[i]] + covalent_radii[atoms.numbers[j]])
            if 0.25 < distance < cutoff:
                bonds.append([i, j])
    # Uses the same fail-closed frame/image/topology validation as later pairs.
    # This checks connected geometry, not a chemically proven bond graph.
    analyze_pair(atoms, atoms, mobile, adsorbate, anchors, bonds)
    return atoms, mobile, adsorbate, anchors, bonds


def _select_initials(
    members: list[dict], out_dir: Path, systems: int, seed: int,
    max_atoms: int, min_adsorbate_atoms: int, dataset: dict,
) -> list[dict]:
    """Selection helper; dataset explicitly identifies official or test origins."""
    out_dir = Path(out_dir).resolve()
    input_dir = out_dir / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    grouped = defaultdict(list)
    for member in members:
        grouped[member["system_id"]].append(member)
    selected, rejected = [], []
    for system in sorted(grouped, key=lambda key: _rank(seed, key)):
        for member in sorted(grouped[system], key=lambda item: _rank(seed, system, item["config_id"])):
            try:
                atoms, mobile, adsorbate, anchors, bonds = _initial_structure(member, max_atoms, min_adsorbate_atoms)
                clean = atoms.copy()
                clean.calc = None
                clean.info = {}
                for key in list(clean.arrays):
                    if key not in {"numbers", "positions", "tags"}:
                        del clean.arrays[key]
                filename = f"{system}_{member['config_id']}.extxyz"
                target = input_dir / filename
                if target.is_symlink():
                    raise ValueError("Selected coordinate destination must not be a symlink")
                write(str(target), clean, format="extxyz", write_results=False)
                reread = read(str(target), format="extxyz", index=0)
                # Ensure the exported input preserves the fixed mask exactly.
                roundtrip_fixed = set()
                for constraint in reread.constraints:
                    if not isinstance(constraint, FixAtoms):
                        raise ValueError("Unexpected constraint after coordinate round trip")
                    roundtrip_fixed.update(map(int, constraint.get_indices()))
                if roundtrip_fixed != set(anchors) or not np.array_equal(reread.get_tags(), clean.get_tags()):
                    raise ValueError("Coordinate export did not preserve tags/FixAtoms")
                selected.append({
                    "pair_id": f"oc20dense_{system}_{member['config_id']}",
                    "system_id": system, "group_id": system, "config_id": member["config_id"],
                    "initial_path": str(target), "initial_sha256": _sha256(target),
                    "source_member": member["source_member"],
                    "source_sha256": member["source_sha256"],
                    "source_archive_sha256": dataset["source_archive_sha256"],
                    "data_origin": dataset["origin"],
                    "mobile_indices": mobile, "adsorbate_indices": adsorbate,
                    "anchor_indices": anchors, "adsorbate_bonds": bonds,
                    "topology_reviewed": False,
                    "topology_basis": "Initial-only MIC edges below 1.25 times sum of covalent radii; unwrapping aid, not established chemical bond truth",
                    "mapping_basis": "Official archive member filename: <system_id>_<config_id>.traj; fixed atom order retained in selected export",
                    "fixed_mask_verified_against_tags": True,
                    "atom_count": len(atoms),
                })
                break
            except Exception as exc:
                rejected.append({"source_member": member["source_member"], "system_id": system, "reason": str(exc)})
        if len(selected) >= systems:
            break
    status = "COMPLETE" if len(selected) == systems else "INSUFFICIENT_ELIGIBLE_SYSTEMS"
    _save_json(out_dir / "selection.json", {
        "schema_version": "1.0", "status": status, "dataset": dataset,
        "selection_parameters": {"systems": systems, "seed": seed, "max_atoms": max_atoms,
                                 "min_adsorbate_atoms": min_adsorbate_atoms},
        "available_systems": len(grouped), "selected_systems": len(selected),
        "selection": selected, "candidate_rejections": rejected,
        "new_physical_calculations_run": False,
        "DFT_reference_endpoints_supplied": False,
        "limitations": [
            "One selected initial placement per system; not a global-minimum search.",
            "Molecular topology is an initial distance-based unwrapping hypothesis requiring human review.",
            "System IDs group a slab/adsorbate combination; broader chemical-family independence is not asserted.",
            "The initial-coordinate source supplies no matched DFT final endpoints or new model-accuracy evidence.",
        ],
    })
    if status != "COMPLETE":
        raise DataPreparationError(
            f"Only {len(selected)}/{systems} eligible systems found; diagnostic selection retained at {out_dir / 'selection.json'}"
        )
    return selected


def prepare_data(
    cache_dir: Path, out_dir: Path, systems: int = 20, seed: int = 20261019,
    max_atoms: int = 180, min_adsorbate_atoms: int = 3, archive_path=None,
) -> list[dict]:
    """Verify the pinned official archive and freeze eligible initial inputs."""
    for name, value, minimum in (("systems", systems, 1), ("max_atoms", max_atoms, 4),
                                 ("min_adsorbate_atoms", min_adsorbate_atoms, 2)):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    cache_dir, out_dir = Path(cache_dir).resolve(), Path(out_dir).resolve()
    archive_path = _download_pinned_archive(cache_dir) if archive_path is None else Path(archive_path).resolve()
    if not archive_path.is_file():
        raise DataPreparationError(f"Official archive is not a readable regular file: {archive_path}")
    if archive_path.stat().st_size != ARCHIVE_BYTES or _sha256(archive_path) != ARCHIVE_SHA256:
        raise DataPreparationError("Archive does not match the frozen official source size/SHA256")
    members = _safe_extract_archive(archive_path, cache_dir)
    if len(members) != 15_256 or len({item["system_id"] for item in members}) != 200:
        raise DataPreparationError("Pinned archive layout does not match 15,256 configurations / 200 systems")
    return _select_initials(members, out_dir, systems, seed, max_atoms, min_adsorbate_atoms, {
        "name": "OC20-Dense 2023 OOD validation ASE initial configurations",
        "origin": "official_oc20dense_initial_configuration",
        "source_url": SOURCE_URL, "documentation_url": "https://opencatalystproject.org/challenge.html",
        "source_archive_sha256": ARCHIVE_SHA256, "source_archive_bytes": ARCHIVE_BYTES,
        "checksum_basis": "SHA256 frozen from the retrieved official public archive; not claimed to be an upstream signed checksum",
        "license": "CC-BY-4.0", "configuration_count": 15_256, "system_count": 200,
        "archive_member_mapping": "ase_val_inputs/<three-part numeric system_id>_<rand|heur placement id>.traj",
    })
