"""Analytic CPU fixtures for restart integrity; these are never research data."""
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import numpy as np
from ase import Atoms
from ase.calculators.calculator import Calculator, all_changes
from ase.constraints import FixAtoms
from ase.io import write

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import continue_phase1 as continuation
from geomscope import uma
from verify_results import verify


class ZeroForceCalculator(Calculator):
    implemented_properties = ["energy", "forces"]

    def calculate(self, atoms=None, properties=("energy", "forces"), system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        self.results = {"energy": 0.0, "forces": np.zeros((len(atoms), 3))}


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def xyz(atoms):
    handle = io.StringIO()
    write(handle, atoms, format="extxyz", write_results=False)
    return handle.getvalue().encode()


def fixture_zip(directory, *, extra_members=None, force_wrong=False):
    """Create a tiny, self-contained 20-system archived-parent fixture."""
    parent_id = "analytic_parent"
    prefix = "/analytic/swan/results/" + parent_id + "/"
    payload, selected, records = {}, [], []
    model = dict(model_name=uma.MODEL_NAME, repo_id=uma.MODEL_REPO, revision="a" * 40,
        cache_root="/analytic/modelcache/fairchem", files={
            role: dict(path=f"/analytic/modelcache/{role}", repo_path=name,
                       sha256="0" * 64, size_bytes=1) for role, name in uma.MODEL_FILES.items()})
    config = continuation.support.DEFAULTS.copy()
    settings = dict(seed=20261019, fmax_eV_A=0.05,
        force_criterion="mobile constrained fmax < threshold", steps_cap=300,
        smoke_systems=3, smoke_only=False, optimizer="ase.optimize.FIRE",
        optimizer_kwargs={"dt": 0.1, "maxstep": 0.2}, device="cuda", task_name="oc20",
        inference=dict(uma.INFERENCE_SETTINGS), required_fairchem_version="2.23.0")
    initial = Atoms("Cu3H3", positions=[[0, 0, 0], [1, 0, 0], [0, 1, 0],
        [0, 0, 2], [.6, 0, 2], [1.2, .1, 2]], cell=[20, 20, 20], pbc=True,
        tags=[0, 0, 0, 2, 2, 2], constraint=FixAtoms(indices=[0, 1, 2]))
    final = initial.copy()
    final.positions[3:] += [.4, 0, 0]
    for i in range(20):
        pair = f"analytic_{i}"
        input_member = f"inputs/{pair}.extxyz"
        payload[input_member] = xyz(initial)
        item = dict(pair_id=pair, system_id=f"system_{i}", group_id=f"system_{i}",
            config_id="rand0", initial_path=prefix + input_member,
            initial_sha256=sha(payload[input_member]), source_sha256="b" * 64,
            source_member=f"ase_val_inputs/{i}_1_1_rand0.traj", source_archive_sha256="c" * 64,
            mobile_indices=[3, 4, 5], adsorbate_indices=[3, 4, 5], anchor_indices=[0, 1, 2],
            adsorbate_bonds=[[3, 4], [4, 5]], topology_reviewed=False)
        selected.append(item)
        directory_member = f"relaxations/{i:016x}/{'d' * 16}/"
        artifacts = {}
        for role, filename, content in (("initial", "initial.extxyz", xyz(initial)),
                ("final", "final.extxyz", xyz(final)), ("optimizer_log", "optimizer.log", b"analytic log\n"),
                ("trajectory", "optimizer.traj", b"analytic trajectory fixture\n")):
            member = directory_member + filename
            payload[member] = content
            artifacts[role] = dict(path=prefix + member, sha256=sha(content))
        converged = i < 13
        record = dict(item, selection=item, source_initial_path=item["initial_path"],
            source_initial_sha256=item["initial_sha256"], artifacts=artifacts,
            converged=converged, status="converged" if converged else "nonconverged",
            final_fmax_eV_A=(0.01 if converged else 0.1), steps=100 if converged else 300,
            elapsed_seconds=1.0, error=None, settings=settings)
        record.update({role + "_path": value["path"] for role, value in artifacts.items()})
        records.append(record)
    prepared = [{"selection": item, "pair_id": item["pair_id"], "source": item["initial_path"],
                 "source_sha256": item["initial_sha256"]} for item in selected]
    hashes = dict(selection_sha256=continuation.canonical_hash(prepared),
        model_manifest_sha256=continuation.canonical_hash(model),
        settings_sha256=continuation.canonical_hash(settings))
    signature = continuation.canonical_hash(hashes)
    for record in records:
        record.update(**hashes, run_signature=signature)
        directory_member = continuation.parent_relative(record["final_path"], parent_id).rsplit("/", 1)[0]
        payload[directory_member + "/record.json"] = encoded(record)
    if force_wrong:
        records[-1]["converged"] = True
    payload.update({"selection.json": encoded(dict(selection=selected)),
        "model_manifest.json": encoded(model), "run_config.json": encoded(config),
        "code_sha256.json": encoded({"never_executed.py": "f" * 64}),
        "relaxation_records.json": encoded(records), "relaxation_results.json": encoded(records),
        "relaxation_protocol.json": encoded(dict(settings, **hashes, run_signature=signature)),
        "summary.json": encoded(dict(status="PARTIAL_NEEDS_REVIEW", phase2_ready=False)),
        "code_snapshot/never_executed.py": b"raise RuntimeError('DO NOT EXECUTE ARCHIVE SOURCE')\n"})
    payload["stage_prepare.json"] = encoded(dict(state="COMPLETE", prepared_artifact_sha256={
        name: sha(payload[name]) for name in ("selection.json", "model_manifest.json", "run_config.json", "code_sha256.json")}))
    if extra_members:
        payload.update(extra_members)
    checksums = {name: sha(data) for name, data in payload.items()}
    payload["SHA256SUMS.json"] = encoded(checksums)
    target = Path(directory) / "analytic_parent.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in payload.items():
            archive.writestr(parent_id + "/" + name, data)
    return target, sha(target.read_bytes())


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.zip_path, self.zip_hash = fixture_zip(self.folder)
        self.parent = continuation.verify_parent_archive(self.zip_path, _expected_sha256=self.zip_hash)
        self.out = self.folder / "results" / "continuation_fixture"
        self.out.mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def restore(self):
        continuation.restore_parent(self.parent, self.out)
        continuation._validate_structures(self.parent, self.out)

    def test_parent_pin_is_required(self):
        with self.assertRaisesRegex(ValueError, "SHA256"):
            continuation.verify_parent_archive(self.zip_path)

    def test_parent_code_not_extracted_or_executed(self):
        self.restore()
        self.assertFalse(any("code_snapshot" in path.parts for path in (self.out / "parent_run").rglob("*")))
        self.assertFalse((self.out / "parent_run" / "SHA256SUMS.json").exists())
        self.assertGreater(self.parent["verified_files"], len(self.parent["payload"]))

    def test_unsafe_path_rejected_even_when_rehashed(self):
        path, checksum = fixture_zip(self.folder, extra_members={"../escape.txt": b"unsafe"})
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            continuation.verify_parent_archive(path, _expected_sha256=checksum)

    def test_parent_labels_must_match_force(self):
        path, checksum = fixture_zip(self.folder, force_wrong=True)
        with self.assertRaisesRegex(ValueError, "force criterion"):
            continuation.verify_parent_archive(path, _expected_sha256=checksum)

    def test_restored_parent_is_immutable(self):
        self.restore()
        target = self.out / "parent_run" / "selection.json"
        target.write_text("{}")
        with self.assertRaisesRegex(ValueError, "changed"):
            continuation.restore_parent(self.parent, self.out)

    def test_exact_seven_inputs_are_saved_final_not_original_initial(self):
        self.restore()
        selection = continuation.continuation_selection(self.parent, self.out)
        self.assertEqual(len(selection), 7)
        for item in selection:
            original = self.parent["records_by_id"][item["pair_id"]]
            self.assertEqual(original["status"], "nonconverged")
            self.assertEqual(item["initial_sha256"], original["artifacts"]["final"]["sha256"])
            self.assertNotEqual(item["initial_sha256"], item["original_initial_sha256"])
            for key in ("mobile_indices", "adsorbate_indices", "anchor_indices", "adsorbate_bonds"):
                self.assertEqual(item[key], original["selection"][key])

    def test_collect_before_gpu_retains_twenty_and_makes_partial_report(self):
        result = continuation.collect(self.out, self.parent)
        self.assertEqual(result["original_selected_systems"], 20)
        self.assertEqual(result["measured_pairs"], 13)
        self.assertEqual(result["outcome_counts"], {"converged": 13, "nonconverged": 7})
        self.assertTrue(result["interrupted_or_incomplete"])

    def test_analytic_execution_preserves_thirteen_and_original_initials(self):
        factory = lambda: ZeroForceCalculator()
        with mock.patch.object(uma, "_check_model"), mock.patch.object(uma, "_create_runtime",
                return_value=(factory, {"device": "analytic_test_only"})) as runtime:
            result = continuation.execute(self.out, self.parent)
        self.assertEqual(runtime.call_count, 1)
        self.assertEqual(result["original_selected_systems"], 20)
        self.assertEqual(result["continued_converged"], 7)
        self.assertEqual(result["measured_pairs"], 20)
        merged = continuation.support.load_json(self.out / "relaxation_records.json")
        for item in merged:
            original = self.parent["records_by_id"][item["pair_id"]]
            self.assertEqual(continuation.support.digest(item["initial_path"]), original["selection"]["initial_sha256"])
            if original["converged"]:
                self.assertEqual(continuation.support.digest(item["final_path"]), original["artifacts"]["final"]["sha256"])
                self.assertEqual(item["additional_steps"], 0)
            else:
                self.assertEqual(item["restart_start_sha256"], original["artifacts"]["final"]["sha256"])
                self.assertNotEqual(item["initial_path"], item["restart_start_path"])
                self.assertLessEqual(item["total_steps"], 600)
        self.assertFalse((self.out / "parent_run" / "code_snapshot").exists())

    def test_complete_same_run_is_resumed_without_second_inference(self):
        with mock.patch.object(uma, "_check_model"), mock.patch.object(uma, "_create_runtime",
                return_value=(lambda: ZeroForceCalculator(), {"device": "analytic_test_only"})):
            continuation.execute(self.out, self.parent)
        with mock.patch.object(uma, "_check_model"), mock.patch.object(uma, "_create_runtime") as runtime:
            second = continuation.execute(self.out, self.parent)
        runtime.assert_not_called()
        self.assertEqual(second["continued_converged"], 7)

    def test_checkpoint_collect_survives_missing_batch_summary(self):
        with mock.patch.object(uma, "_check_model"), mock.patch.object(uma, "_create_runtime",
                return_value=(lambda: ZeroForceCalculator(), {"device": "analytic_test_only"})):
            continuation.execute(self.out, self.parent)
        (self.out / "continuation_stage" / "relaxation_records.json").unlink()
        continuation.support.stage(self.out, "continuation", "RUNNING")
        result = continuation.collect(self.out, self.parent)
        self.assertEqual(result["continuation_checkpoints"], 7)
        self.assertEqual(result["measured_pairs"], 20)
        self.assertTrue(result["interrupted_or_incomplete"])

    def test_checkpoint_tamper_is_rejected(self):
        with mock.patch.object(uma, "_check_model"), mock.patch.object(uma, "_create_runtime",
                return_value=(lambda: ZeroForceCalculator(), {"device": "analytic_test_only"})):
            continuation.execute(self.out, self.parent)
        path = next((self.out / "continuation_stage" / "relaxations").glob("*/*/final.extxyz"))
        path.write_text("tampered")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            continuation.collect(self.out, self.parent)

    def test_partial_checkpoint_collection_retains_twenty_systems(self):
        with mock.patch.object(uma, "_check_model"), mock.patch.object(uma, "_create_runtime",
                return_value=(lambda: ZeroForceCalculator(), {"device": "analytic_test_only"})):
            continuation.execute(self.out, self.parent)
        paths = sorted((self.out / "continuation_stage" / "relaxations").glob("*/*/record.json"))
        for path in paths[3:]:
            path.unlink()
        continuation.support.stage(self.out, "continuation", "RUNNING")
        result = continuation.collect(self.out, self.parent)
        self.assertEqual(result["continuation_checkpoints"], 3)
        self.assertEqual(result["original_selected_systems"], 20)
        self.assertEqual(result["outcome_counts"], {"converged": 16, "nonconverged": 4})
        self.assertTrue(result["interrupted_or_incomplete"])

    def test_collect_rejects_changed_code_snapshot(self):
        continuation.collect(self.out, self.parent)
        path = self.out / "code_sha256.json"
        hashes = continuation.support.load_json(path)
        hashes["continue_phase1.py"] = "0" * 64
        continuation.support.save_json(path, hashes)
        with self.assertRaisesRegex(ValueError, "code changed"):
            continuation.collect(self.out, self.parent)

    def test_checkpoint_restart_source_identity_is_checked(self):
        with mock.patch.object(uma, "_check_model"), mock.patch.object(uma, "_create_runtime",
                return_value=(lambda: ZeroForceCalculator(), {"device": "analytic_test_only"})):
            continuation.execute(self.out, self.parent)
        path = next((self.out / "continuation_stage" / "relaxations").glob("*/*/record.json"))
        record = continuation.support.load_json(path)
        record["source_initial_sha256"] = "0" * 64
        continuation.support.save_json(path, record)
        with self.assertRaisesRegex(ValueError, "restart source"):
            continuation.collect(self.out, self.parent)

    def test_new_return_archive_has_one_manifest_and_verifies(self):
        result = continuation.collect(self.out, self.parent)
        result.update(phase2_ready=False)
        continuation.support.save_json(self.out / "summary.json", result)
        target = continuation.support.archive(self.out, self.out.parent)
        checked = verify(target)
        self.assertEqual(checked["status"], "CONTINUATION_INTERRUPTED_OR_INCOMPLETE")
        self.assertGreater(checked["verified_files"], 100)

    def test_invalid_parent_cli_still_creates_diagnostic_zip(self):
        code = continuation.main(["run", "--parent-zip", str(self.zip_path),
            "--run-id", "pin_failure", "--output-root", str(self.out.parent)])
        self.assertEqual(code, 1)
        target = self.out.parent / "return_zips" / "pin_failure_phase1_results.zip"
        self.assertEqual(verify(target)["status"], "CONTINUATION_FAILED")


if __name__ == "__main__":
    unittest.main()
