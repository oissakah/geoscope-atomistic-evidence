"""Explicit-scope geometry comparisons; no energies, forces, or calculators.

Only fixed atom correspondence is supported.  A declared molecular bond graph
is used for periodic unwrapping; connectivity is never inferred from distance.
"""

from __future__ import annotations

from collections import deque
from numbers import Integral

import numpy as np
from ase import Atoms
from ase.geometry import find_mic


_CYCLE_ATOL_A = 1e-7
_RANK_ATOL_A = 1e-8


def _indices(value, name: str, size: int) -> list[int]:
    if isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a nonempty sequence of atom indices")
    try:
        result = list(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be a nonempty sequence of atom indices") from exc
    if not result:
        raise ValueError(f"{name} must be nonempty")
    if any(isinstance(i, (bool, np.bool_)) or not isinstance(i, Integral) for i in result):
        raise ValueError(f"{name} must contain integer indices, not booleans")
    result = [int(i) for i in result]
    if len(set(result)) != len(result):
        raise ValueError(f"{name} contains duplicate indices")
    if any(i < 0 or i >= size for i in result):
        raise ValueError(f"{name} contains an out-of-range atom index")
    return result


def _mic(vectors: np.ndarray, cell: np.ndarray, pbc: np.ndarray) -> np.ndarray:
    if not np.any(pbc):
        return np.array(vectors, dtype=float, copy=True)
    return np.asarray(find_mic(vectors, cell, pbc=pbc)[0], dtype=float)


def _rmsd(displacements: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.sum(displacements**2, axis=1))))


def _proper_kabsch(a: np.ndarray, b: np.ndarray) -> tuple[float, np.ndarray]:
    """Fit row-vector coordinates B onto A, allowing SO(3) rotations only."""
    x = a - np.mean(a, axis=0)
    y = b - np.mean(b, axis=0)
    u, _, vt = np.linalg.svd(y.T @ x)
    correction = np.eye(3)
    correction[-1, -1] = 1.0 if np.linalg.det(u @ vt) >= 0 else -1.0
    rotation = u @ correction @ vt
    return _rmsd(x - y @ rotation), rotation


def _bond_graph(bonds, adsorbate: list[int]) -> tuple[list[list[int]], dict[int, list[int]]]:
    try:
        declared = list(bonds)
    except TypeError as exc:
        raise ValueError("adsorbate_bonds must be an explicit sequence of index pairs") from exc
    allowed = set(adsorbate)
    edges: list[list[int]] = []
    seen = set()
    adjacency = {i: [] for i in adsorbate}
    for pair in declared:
        if isinstance(pair, (str, bytes)):
            raise ValueError("Each adsorbate bond must contain two global atom indices")
        try:
            edge = list(pair)
        except TypeError as exc:
            raise ValueError("Each adsorbate bond must contain two global atom indices") from exc
        if len(edge) != 2 or any(
            isinstance(i, (bool, np.bool_)) or not isinstance(i, Integral) for i in edge
        ):
            raise ValueError("Each adsorbate bond must contain two integer global atom indices")
        i, j = map(int, edge)
        if i == j or i not in allowed or j not in allowed:
            raise ValueError("Bond endpoints must be distinct members of adsorbate_indices")
        key = tuple(sorted((i, j)))
        if key in seen:
            raise ValueError("adsorbate_bonds contains a duplicate undirected edge")
        seen.add(key)
        edges.append([i, j])
        adjacency[i].append(j)
        adjacency[j].append(i)
    visited = {adsorbate[0]}
    queue = deque(visited)
    while queue:
        for j in adjacency[queue.popleft()]:
            if j not in visited:
                visited.add(j)
                queue.append(j)
    if visited != allowed:
        raise ValueError("adsorbate_bonds must form one connected molecular graph")
    return edges, adjacency


def _unwrap(
    positions: np.ndarray,
    adsorbate: list[int],
    edges: list[list[int]],
    adjacency: dict[int, list[int]],
    cell: np.ndarray,
    pbc: np.ndarray,
    unique_radius: float | None,
) -> tuple[np.ndarray, list[float]]:
    edge_vectors = {}
    bond_lengths = []
    for i, j in edges:
        vector = _mic(positions[j] - positions[i], cell, pbc)
        length = float(np.linalg.norm(vector))
        if length <= 1e-12:
            raise ValueError("Declared bond has coincident endpoints")
        if unique_radius is not None and length >= unique_radius - 1e-10:
            raise ValueError(
                "Declared bond is too long for conservative unique periodic unwrapping; "
                "a larger cell or an explicit image-aware topology is required"
            )
        edge_vectors[i, j] = vector
        edge_vectors[j, i] = -vector
        bond_lengths.append(length)
    root = adsorbate[0]
    unwrapped = {root: positions[root].copy()}
    queue = deque([root])
    while queue:
        i = queue.popleft()
        for j in sorted(adjacency[i]):
            proposed = unwrapped[i] + edge_vectors[i, j]
            if j not in unwrapped:
                unwrapped[j] = proposed
                queue.append(j)
            elif np.linalg.norm(proposed - unwrapped[j]) > _CYCLE_ATOL_A:
                raise ValueError("Bond graph has inconsistent periodic cycle winding")
    return np.asarray([unwrapped[i] for i in adsorbate]), bond_lengths


def analyze_pair(
    atoms_a: Atoms,
    atoms_b: Atoms,
    mobile_indices: list[int],
    adsorbate_indices: list[int],
    anchor_indices: list[int],
    adsorbate_bonds: list[list[int]],
    cell_atol: float = 1e-6,
) -> dict:
    """Return unweighted RMSDs in Angstrom under explicitly declared scopes.

    The first three metrics distinguish fixed-frame mobile atoms, fixed-frame
    adsorbate atoms, and rigid-aligned internal adsorbate geometry.  Anchors
    describe frame drift; callers must apply their own declared drift cutoff.
    No registration to the anchors is performed.  Changed atom correspondence,
    cell shape, chemistry, disconnected adsorbates, and reflection alignment are
    outside the protocol.  Invalid or ambiguous input raises ``ValueError``.

    Periodic bonds must be shorter than half the smallest singular value of the
    periodic cell-vector basis.  This is a conservative lower bound on half the
    shortest lattice translation, not an estimate of that translation.  It may
    reject otherwise valid bonds in small or highly skew cells.  Both endpoints
    must admit the declared topology; periodic polymers are unsupported.
    """
    if not isinstance(atoms_a, Atoms) or not isinstance(atoms_b, Atoms):
        raise ValueError("atoms_a and atoms_b must be ASE Atoms objects")
    if isinstance(cell_atol, (bool, np.bool_)):
        raise ValueError("cell_atol must be a finite nonnegative number")
    try:
        tolerance = float(cell_atol)
    except (TypeError, ValueError) as exc:
        raise ValueError("cell_atol must be a finite nonnegative number") from exc
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("cell_atol must be a finite nonnegative number")
    if len(atoms_a) != len(atoms_b) or not np.array_equal(atoms_a.numbers, atoms_b.numbers):
        raise ValueError("Endpoints must have the same symbols in the same atom order")
    a, b = atoms_a.get_positions(), atoms_b.get_positions()
    cell, other_cell = np.asarray(atoms_a.cell), np.asarray(atoms_b.cell)
    if not all(np.all(np.isfinite(array)) for array in (a, b, cell, other_cell)):
        raise ValueError("Coordinates and cells must be finite")
    if not np.allclose(cell, other_cell, atol=tolerance, rtol=0):
        raise ValueError("Endpoint cells differ beyond cell_atol; changing-cell comparisons unsupported")
    pbc = atoms_a.get_pbc()
    if not np.array_equal(pbc, atoms_b.get_pbc()):
        raise ValueError("Endpoints must have the same periodic boundary flags")
    unique_radius = None
    if np.any(pbc):
        singular_values = np.linalg.svd(cell[pbc], compute_uv=False)
        if singular_values[-1] <= 1e-12:
            raise ValueError("Periodic cell vectors must be nonzero and linearly independent")
        unique_radius = float(singular_values[-1] / 2)
    mobile = _indices(mobile_indices, "mobile_indices", len(atoms_a))
    adsorbate = _indices(adsorbate_indices, "adsorbate_indices", len(atoms_a))
    anchors = _indices(anchor_indices, "anchor_indices", len(atoms_a))
    if not set(adsorbate) <= set(mobile):
        raise ValueError("adsorbate_indices must be a subset of mobile_indices")
    if set(anchors) & set(adsorbate):
        raise ValueError("anchor_indices must be disjoint from adsorbate_indices")
    if len(anchors) < 3:
        raise ValueError("At least three noncollinear slab anchors are required")
    for positions in (a, b):
        relative = _mic(positions[anchors] - positions[anchors[0]], cell, pbc)
        if np.linalg.matrix_rank(relative - relative.mean(axis=0), tol=_RANK_ATOL_A) < 2:
            raise ValueError("Slab anchor positions must be noncollinear in both endpoints")
    edges, adjacency = _bond_graph(adsorbate_bonds, adsorbate)
    unwrapped_a, lengths_a = _unwrap(a, adsorbate, edges, adjacency, cell, pbc, unique_radius)
    unwrapped_b, lengths_b = _unwrap(b, adsorbate, edges, adjacency, cell, pbc, unique_radius)
    internal, rotation = _proper_kabsch(unwrapped_a, unwrapped_b)
    displacements = _mic(b - a, cell, pbc)
    anchor_lengths = np.linalg.norm(displacements[anchors], axis=1)
    common = {
        "units": "Angstrom",
        "weighting": "equal weight per selected atom",
        "correspondence": "fixed global atom indices; no permutation or symmetry matching",
        "cell_reference": "endpoint_a; endpoint_b must agree within cell_atol",
    }
    def definition(indices, alignment, frame, periodic):
        return {**common, "atom_indices": indices, "alignment": alignment, "frame": frame,
                "periodic_treatment": periodic}
    fixed_periodic = "minimum-image displacement independently per matched atom"
    return {
        "mobile_rmsd_A": _rmsd(displacements[mobile]),
        "adsorbate_frame_rmsd_A": _rmsd(displacements[adsorbate]),
        "internal_rmsd_A": internal,
        "anchor_rmsd_A": _rmsd(displacements[anchors]),
        "anchor_max_displacement_A": float(np.max(anchor_lengths)),
        "metric_definitions": {
            "mobile_rmsd_A": definition(mobile, "none", "shared stored slab coordinate frame", fixed_periodic),
            "adsorbate_frame_rmsd_A": definition(adsorbate, "none", "shared stored slab coordinate frame", fixed_periodic),
            "internal_rmsd_A": definition(adsorbate, "proper Kabsch rotation plus translation; no reflection", "independent molecular centroids", "connected bond-graph unwrapping before alignment; no MIC on fitted residuals"),
            "anchor_rmsd_A": definition(anchors, "none", "shared stored slab coordinate frame", fixed_periodic),
            "anchor_max_displacement_A": {**definition(anchors, "none", "shared stored slab coordinate frame", fixed_periodic), "reduction": "maximum displacement norm, not RMSD"},
        },
        "topology": {
            "adsorbate_bonds_global": edges,
            "connected": True,
            "unwrap_root_global_index": adsorbate[0],
            "cycle_consistency_atol_A": _CYCLE_ATOL_A,
            "periodic_unique_bond_radius_lower_bound_A": unique_radius,
            "bond_lengths_a_A": lengths_a,
            "bond_lengths_b_A": lengths_b,
            "kabsch_rotation_b_to_a": rotation.tolist(),
            "kabsch_rotation_determinant": float(np.linalg.det(rotation)),
        },
        "validation": {
            "cell_atol_A": tolerance,
            "anchor_rank_atol_A": _RANK_ATOL_A,
            "anchor_drift_cutoff_applied": False,
            "physical_accuracy_or_convergence_inferred": False,
            "limitations": [
                "Anchor positions are checked for noncollinearity, not aligned or declared immobile automatically.",
                "Minimum-image displacements do not determine continuous diffusion paths or image-crossing counts.",
                "Declared bond connectivity is not an independent chemical bond or atom-identity validation.",
                "No atom permutations, surface symmetry operations, cell deformation, periodic molecules, or reflections are fitted.",
            ],
        },
    }
