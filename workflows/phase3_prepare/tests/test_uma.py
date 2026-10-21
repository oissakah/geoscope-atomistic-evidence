"""CPU-only contract tests. The production CUDA factory is always mocked."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
from ase import Atoms
from ase.calculators.calculator import Calculator, all_changes
from ase.constraints import FixAtoms
from ase.io import read, write

from geomscope import uma


class HarmonicCalculator(Calculator):
    implemented_properties = ["energy", "forces"]

    def calculate(self, atoms=None, properties=("energy", "forces"), system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        positions = self.atoms.positions
        self.results = {"energy": float((positions * positions).sum() / 2), "forces": -positions.copy()}


class FailingCalculator(Calculator):
    implemented_properties = ["energy", "forces"]

    def calculate(self, atoms=None, properties=("energy", "forces"), system_changes=all_changes):
        raise RuntimeError("test failure with token=hf_DO_NOT_ARCHIVE at https://example.invalid/?secret=value")


class UMATests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / "model-cache"
        self.out = self.root / "results"
        self.cache.mkdir()
        files = {}
        for role, repo_path in uma.MODEL_FILES.items():
            path = self.cache / (role + ".test-fixture")
            path.write_bytes(("CPU test fixture: " + role).encode())
            files[role] = {"path": str(path), "repo_path": repo_path,
                           "sha256": uma._sha256(path), "size_bytes": path.stat().st_size}
        self.manifest = {"schema_version": 1, "model_name": uma.MODEL_NAME, "repo_id": uma.MODEL_REPO,
                         "revision": "a" * 40, "files": files, "required_fairchem_version": uma.FAIRCHEM_VERSION,
                         "cache_root": str(self.cache / "fairchem"),
                         "weights_in_results": False}
        self.runtime = {"device": "cpu", "test_only": True}
        self.runtime["runtime_sha256"] = uma._hash_json(self.runtime)

    def selection(self, count=1, displacement=0.3):
        selected = []
        for index in range(count):
            path = self.root / f"input-{index}.extxyz"
            atoms = Atoms("CuH", positions=[[5, 0, 0], [displacement, 0, 0]], cell=[12, 12, 12], pbc=False)
            atoms.set_constraint(FixAtoms(indices=[0]))
            write(path, atoms)
            selected.append({"pair_id": f"pair-{index}", "system_id": f"system-{index}",
                             "group_id": "group-one", "config_id": index, "initial_path": str(path),
                             "initial_sha256": uma._sha256(path),
                             "mobile_indices": [1], "arbitrary_source_metadata": {"partition": "test"}})
        return selected

    def mock_factory(self, calculator=HarmonicCalculator):
        return patch.object(uma, "_create_runtime", return_value=(calculator, self.runtime))

    def test_prepare_pins_every_file_and_does_not_archive_auth(self):
        downloads = []

        def download(**kwargs):
            downloads.append(kwargs)
            role = next(role for role, path in uma.MODEL_FILES.items() if path == kwargs["filename"])
            return self.manifest["files"][role]["path"]

        api = types.SimpleNamespace(model_info=lambda repo, revision: types.SimpleNamespace(sha="b" * 40))
        hub = types.SimpleNamespace(HfApi=lambda: api, hf_hub_download=download)
        with patch.dict("sys.modules", {"huggingface_hub": hub}), patch.dict("os.environ", {"HF_TOKEN": "hf_DO_NOT_ARCHIVE"}):
            manifest = uma.prepare_model(self.cache, self.out, revision="release")
        self.assertEqual(manifest["revision"], "b" * 40)
        self.assertEqual(manifest["cache_root"], str(self.cache / "fairchem"))
        self.assertEqual(len(downloads), 3)
        self.assertTrue(all(item["revision"] == "b" * 40 for item in downloads))
        self.assertTrue(all("token" not in item for item in downloads))
        archived = (self.out / "model_manifest.json").read_text()
        self.assertNotIn("hf_DO_NOT_ARCHIVE", archived)
        self.assertEqual(json.loads(archived), manifest)
        self.assertEqual(list(self.out.iterdir()), [self.out / "model_manifest.json"])

    def test_prepare_refuses_weights_inside_results(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            uma.prepare_model(self.out / "weights", self.out)

    def test_prepare_redacts_auth_exceptions(self):
        def fail(*args, **kwargs):
            raise RuntimeError("hf_DO_NOT_ARCHIVE https://signed.invalid/?token=SECRET")

        hub = types.SimpleNamespace(HfApi=lambda: types.SimpleNamespace(model_info=fail), hf_hub_download=fail)
        with patch.dict("sys.modules", {"huggingface_hub": hub}):
            with self.assertRaises(RuntimeError) as caught:
                uma.prepare_model(self.cache, self.out)
        self.assertNotIn("hf_DO_NOT_ARCHIVE", str(caught.exception))
        self.assertNotIn("SECRET", str(caught.exception))

    def test_real_fire_converges_and_preserves_constraints_clean_endpoints(self):
        selected = self.selection()
        with self.mock_factory() as factory:
            records = uma.relax_selected(selected, self.manifest, self.out, steps=200)
        record = records[0]
        self.assertEqual(record["status"], "converged")
        self.assertTrue(record["converged"])
        self.assertLess(record["final_fmax_eV_A"], 0.05)
        self.assertGreater(record["steps"], 0)
        self.assertEqual(record["selection"], selected[0])
        self.assertEqual(record["arbitrary_source_metadata"], selected[0]["arbitrary_source_metadata"])
        self.assertEqual(record["settings"]["device"], "cuda")
        self.assertEqual(record["settings"]["task_name"], "oc20")
        self.assertEqual(record["runtime"]["device"], "cpu")  # This is only a mocked test runtime.
        for role in ("initial", "final"):
            endpoint = read(record[role + "_path"])
            self.assertIsNone(endpoint.calc)
            self.assertTrue(np.allclose(endpoint.positions[0], [5, 0, 0]))
            self.assertEqual(endpoint.constraints[0].get_indices().tolist(), [0])
        self.assertEqual(set(record["artifacts"]), {"initial", "final", "trajectory", "optimizer_log"})
        protocol = json.loads((self.out / "relaxation_protocol.json").read_text())
        self.assertEqual(record["run_signature"], protocol["run_signature"])
        factory.assert_called_once()
        self.assertFalse(any(path.suffix in (".pt", ".test-fixture") for path in self.out.rglob("*")))

    def test_nonconvergence_is_retained_and_not_a_smoke_error(self):
        with self.mock_factory():
            records = uma.relax_selected(self.selection(3, displacement=2), self.manifest, self.out,
                                         fmax=1e-10, steps=1, smoke_systems=1)
        self.assertEqual(len(records), 3)
        self.assertTrue(all(record["status"] == "nonconverged" for record in records))
        self.assertTrue(all(record["steps"] == 1 and not record["converged"] for record in records))
        self.assertTrue(all(record["final_fmax_eV_A"] > 1e-10 for record in records))

    def test_smoke_error_is_recorded_and_remainder_explicitly_not_run(self):
        with self.mock_factory(FailingCalculator):
            records = uma.relax_selected(self.selection(3), self.manifest, self.out, smoke_systems=1)
        self.assertEqual([record["status"] for record in records],
                         ["error", "not_run_after_smoke_failure", "not_run_after_smoke_failure"])
        self.assertNotIn("hf_DO_NOT_ARCHIVE", json.dumps(records))
        self.assertNotIn("secret=value", json.dumps(records))
        self.assertFalse(any(record["converged"] for record in records))

    def test_smoke_only_limits_actual_attempts(self):
        with self.mock_factory():
            records = uma.relax_selected(self.selection(4), self.manifest, self.out,
                                         steps=1, smoke_systems=2, smoke_only=True)
        self.assertEqual(len(records), 2)

    def test_resume_does_not_load_predictor_but_changed_settings_rerun(self):
        selected = self.selection()
        with self.mock_factory():
            first = uma.relax_selected(selected, self.manifest, self.out, steps=2)
        with patch.object(uma, "_create_runtime", side_effect=AssertionError("must not load")):
            second = uma.relax_selected(selected, self.manifest, self.out, steps=2)
        self.assertTrue(second[0]["resumed"])
        self.assertEqual(first[0]["run_signature"], second[0]["run_signature"])
        with self.mock_factory() as factory:
            changed = uma.relax_selected(selected, self.manifest, self.out, steps=3)
        factory.assert_called_once()
        self.assertFalse(changed[0]["resumed"])
        self.assertNotEqual(first[0]["run_signature"], changed[0]["run_signature"])
        self.assertTrue(Path(first[0]["final_path"]).is_file())

    def test_resume_hashes_full_selection_model_and_source(self):
        selected = self.selection()
        with self.mock_factory():
            first = uma.relax_selected(selected, self.manifest, self.out, steps=1)
        edited = copy.deepcopy(selected)
        edited[0]["arbitrary_source_metadata"]["partition"] = "changed"
        with self.mock_factory():
            selection_change = uma.relax_selected(edited, self.manifest, self.out, steps=1)
        manifest = copy.deepcopy(self.manifest)
        manifest["revision"] = "c" * 40
        with self.mock_factory():
            model_change = uma.relax_selected(selected, manifest, self.out, steps=1)
        source = Path(selected[0]["initial_path"])
        source.write_text(source.read_text() + "\n")
        with self.mock_factory() as untouched:
            with self.assertRaisesRegex(ValueError, "Frozen initial_sha256 mismatch"):
                uma.relax_selected(selected, self.manifest, self.out, steps=1)
        untouched.assert_not_called()
        newly_frozen = copy.deepcopy(selected)
        newly_frozen[0]["initial_sha256"] = uma._sha256(source)
        with self.mock_factory():
            source_change = uma.relax_selected(newly_frozen, self.manifest, self.out, steps=1)
        signatures = {item[0]["run_signature"] for item in (first, selection_change, model_change, source_change)}
        self.assertEqual(len(signatures), 4)

    def test_tampered_artifact_is_preserved_and_corrupt_model_is_rejected(self):
        selected = self.selection()
        with self.mock_factory():
            first = uma.relax_selected(selected, self.manifest, self.out, steps=1)
        Path(first[0]["optimizer_log_path"]).write_text("tampered")
        with self.mock_factory() as factory:
            with self.assertRaisesRegex(ValueError,"refusing an automatic retry"):
                uma.relax_selected(selected, self.manifest, self.out, steps=1)
        factory.assert_not_called()
        self.assertEqual(Path(first[0]["optimizer_log_path"]).read_text(),"tampered")
        Path(self.manifest["files"]["checkpoint"]["path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "integrity"):
            uma.relax_selected(selected, self.manifest, self.out)

    def test_mobile_mask_mismatch_cannot_silently_change_force_criterion(self):
        selected = self.selection()
        selected[0]["mobile_indices"] = [0, 1]
        with self.mock_factory() as factory:
            records = uma.relax_selected(selected, self.manifest, self.out)
        self.assertEqual(records[0]["status"], "error")
        self.assertIn("match all atoms", records[0]["error"])
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
