"""Bounded extraction and selection tests use clearly synthetic coordinates."""

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from ase import Atoms
from ase.constraints import FixAtoms
from ase.io import read, write

from geomscope.data import (
    ARCHIVE_NAME, DataPreparationError, _download_pinned_archive, _initial_structure, _safe_extract_archive,
    _select_initials, prepare_data,
)


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.atoms = Atoms(
            "Cu3CHO", positions=[[0, 0, 0], [2, 0, 0], [0, 2, 0],
                                 [4, 4, 3], [5, 4, 3], [4, 5.2, 3]],
            cell=[20, 20, 20], pbc=[True, True, False],
            tags=[0, 0, 0, 2, 2, 2], constraint=FixAtoms(indices=[0, 1, 2]),
        )
        self.dataset = {
            "name": "Synthetic software-test fixtures, not OC20 observations",
            "origin": "synthetic_test_fixture",
            "source_archive_sha256": "synthetic-test-only",
        }

    def tearDown(self):
        self.temp.cleanup()

    def trajectory_bytes(self, atoms=None):
        target = self.root / "fixture.traj"
        write(target, self.atoms if atoms is None else atoms, format="traj")
        return target.read_bytes()

    def archive(self, entries):
        target = self.root / "synthetic.tar.gz"
        with tarfile.open(target, "w:gz") as archive:
            for name, payload in entries:
                if isinstance(payload, tarfile.TarInfo):
                    payload.name = name
                    archive.addfile(payload)
                else:
                    info = tarfile.TarInfo(name)
                    info.size = len(payload)
                    archive.addfile(info, io.BytesIO(payload))
        return target

    def fixtures(self):
        data = self.trajectory_bytes()
        entries = [(f"ase_val_inputs/{group}_1_1_{config}.traj", data)
                   for group in range(1, 4) for config in ("rand1", "heur2")]
        return _safe_extract_archive(self.archive(entries), self.root / "cache")

    def test_regular_trajectory_extraction_has_hash_and_filename_ids(self):
        payload = self.trajectory_bytes()
        records = _safe_extract_archive(
            self.archive([("ase_val_inputs/6_1511_60_rand49.traj", payload)]), self.root / "cache"
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["system_id"], "6_1511_60")
        self.assertEqual(records[0]["config_id"], "rand49")
        self.assertEqual(records[0]["source_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(Path(records[0]["path"]).read_bytes(), payload)

    def test_traversal_absolute_nested_and_windows_paths_are_rejected(self):
        for name in ("../outside.traj", "/ase_val_inputs/1_1_1_rand1.traj",
                     "ase_val_inputs/../outside.traj", "ase_val_inputs/nested/1_1_1_rand1.traj",
                     "ase_val_inputs\\1_1_1_rand1.traj", "C:/ase_val_inputs/1_1_1_rand1.traj"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                _safe_extract_archive(self.archive([(name, b"x")]), self.root / "cache")
        self.assertFalse((self.root / "outside.traj").exists())

    def test_links_and_duplicate_targets_are_rejected(self):
        for link_type in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            info = tarfile.TarInfo()
            info.type, info.linkname = link_type, "../outside"
            with self.subTest(link_type=link_type), self.assertRaisesRegex(ValueError, "regular"):
                _safe_extract_archive(self.archive([("ase_val_inputs/1_1_1_rand1.traj", info)]), self.root / "cache")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            _safe_extract_archive(self.archive([("ase_val_inputs/1_1_1_rand1.traj", b"x")] * 2), self.root / "cache")

    def test_archive_expansion_and_member_count_budgets(self):
        archive = self.archive([("ase_val_inputs/1_1_1_rand1.traj", b"12345")])
        with patch("geomscope.data.MAX_EXTRACTED_BYTES", 4), self.assertRaisesRegex(ValueError, "decompressed"):
            _safe_extract_archive(archive, self.root / "cache")
        with patch("geomscope.data.MAX_MEMBERS", 0), self.assertRaisesRegex(ValueError, "member"):
            _safe_extract_archive(archive, self.root / "cache")

    def test_initial_tags_fixatoms_and_graph_are_preserved(self):
        member = self.fixtures()[0]
        atoms, mobile, ads, anchors, bonds = _initial_structure(member, 180, 3)
        self.assertEqual(mobile, [3, 4, 5])
        self.assertEqual(ads, [3, 4, 5])
        self.assertEqual(anchors, [0, 1, 2])
        self.assertEqual(bonds, [[3, 4], [3, 5]])
        np.testing.assert_array_equal(atoms.get_tags(), [0, 0, 0, 2, 2, 2])

    def test_atom_budget_constraint_mismatch_and_disconnected_adsorbate(self):
        member = self.fixtures()[0]
        with self.assertRaisesRegex(ValueError, "max_atoms"):
            _initial_structure(member, 5, 3)
        for mode in ("constraint", "disconnected"):
            atoms = self.atoms.copy()
            if mode == "constraint":
                atoms.set_constraint(FixAtoms(indices=[0, 1]))
            else:
                atoms.positions[5] += [5, 0, 0]
            payload = self.trajectory_bytes(atoms)
            records = _safe_extract_archive(self.archive([("ase_val_inputs/4_1_1_rand1.traj", payload)]), self.root / "cache")
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                _initial_structure(records[0], 180, 3)

    def test_selection_is_deterministic_and_uses_distinct_systems(self):
        members = self.fixtures()
        first = _select_initials(members, self.root / "first", 2, 101, 180, 3, self.dataset)
        second = _select_initials(list(reversed(members)), self.root / "second", 2, 101, 180, 3, self.dataset)
        ids = lambda records: [(r["system_id"], r["config_id"]) for r in records]
        self.assertEqual(ids(first), ids(second))
        self.assertEqual(len({r["system_id"] for r in first}), 2)
        for record in first:
            self.assertFalse(record["topology_reviewed"])
            self.assertEqual(record["data_origin"], "synthetic_test_fixture")
            self.assertEqual(record["initial_sha256"], hashlib.sha256(Path(record["initial_path"]).read_bytes()).hexdigest())
            exported = read(record["initial_path"])
            self.assertIsNone(exported.calc)
            self.assertEqual(exported.constraints[0].get_indices().tolist(), [0, 1, 2])
        frozen = json.loads((self.root / "first/selection.json").read_text())
        self.assertEqual(frozen["selection"], first)
        self.assertEqual(frozen["status"], "COMPLETE")
        self.assertFalse(frozen["DFT_reference_endpoints_supplied"])

    def test_insufficient_selection_raises_and_retains_diagnostic(self):
        with self.assertRaisesRegex(DataPreparationError, "3/4"):
            _select_initials(self.fixtures(), self.root / "partial", 4, 101, 180, 3, self.dataset)
        diagnostic = json.loads((self.root / "partial/selection.json").read_text())
        self.assertEqual(diagnostic["status"], "INSUFFICIENT_ELIGIBLE_SYSTEMS")
        self.assertEqual(diagnostic["selected_systems"], 3)

    def test_official_entrypoint_rejects_unpinned_fixture_archive(self):
        archive = self.archive([("ase_val_inputs/1_1_1_rand1.traj", self.trajectory_bytes())])
        with self.assertRaisesRegex(DataPreparationError, "frozen official source"):
            prepare_data(self.root / "cache", self.root / "output", systems=1, archive_path=archive)
        self.assertFalse((self.root / "output/selection.json").exists())

    def test_cached_trajectory_tampering_is_rejected(self):
        member = self.fixtures()[0]
        Path(member["path"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "hash"):
            _initial_structure(member, 180, 3)

    def test_download_is_atomic_and_checks_the_pinned_bytes(self):
        # This tests the byte-transfer mechanism only, never dataset selection.
        payload = b"synthetic transport fixture"
        response = io.BytesIO(payload)
        response.headers = {"Content-Length": str(len(payload))}
        with patch("geomscope.data.urlopen", return_value=response), \
             patch("geomscope.data.ARCHIVE_BYTES", len(payload)), \
             patch("geomscope.data.ARCHIVE_SHA256", hashlib.sha256(payload).hexdigest()):
            result = _download_pinned_archive(self.root / "download")
        self.assertEqual(result.read_bytes(), payload)
        self.assertFalse(result.with_name(result.name + ".part").exists())

    def test_download_budget_removes_only_its_own_partial(self):
        response = io.BytesIO(b"12345")
        response.headers = {}
        cache = self.root / "download"
        with patch("geomscope.data.urlopen", return_value=response), \
             patch("geomscope.data.MAX_DOWNLOAD_BYTES", 4), \
             self.assertRaisesRegex(DataPreparationError, "download limit"):
            _download_pinned_archive(cache)
        self.assertFalse((cache / ARCHIVE_NAME).exists())
        self.assertFalse((cache / (ARCHIVE_NAME + ".part")).exists())

    def test_concurrent_download_partial_is_not_deleted(self):
        cache = self.root / "download"
        def competing_download(*args, **kwargs):
            (cache / (ARCHIVE_NAME + ".part")).write_bytes(b"another operation")
            response = io.BytesIO(b"not consumed")
            response.headers = {}
            return response
        with patch("geomscope.data.urlopen", side_effect=competing_download), self.assertRaises(FileExistsError):
            _download_pinned_archive(cache)
        self.assertEqual((cache / (ARCHIVE_NAME + ".part")).read_bytes(), b"another operation")


if __name__ == "__main__":
    unittest.main()
