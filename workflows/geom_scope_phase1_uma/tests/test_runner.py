"""Exercise successful/failed result archives without GPU or network access."""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase1_runner", ROOT / "run_phase1.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
verify_spec = importlib.util.spec_from_file_location("phase1_zip_verify", ROOT / "verify_results.py")
verifier = importlib.util.module_from_spec(verify_spec)
verify_spec.loader.exec_module(verifier)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.results = self.root / "results"
        self.cache = self.root / "cache"
        self.config = self.root / "pilot.json"
        runner.save_json(self.config, runner.DEFAULTS)

    def command(self, mode, run_id):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return runner.main([mode, "--run-id", run_id, "--config", str(self.config),
                   "--output-root", str(self.results), "--cache-dir", str(self.cache)])

    def returned(self, run_id):
        path = self.results / "return_zips" / (run_id + "_phase1_results.zip")
        verified = verifier.verify(path)
        with zipfile.ZipFile(path) as z:
            summary = json.loads(z.read(run_id + "/summary.json"))
        return path, verified, summary

    def test_analytic_demo_is_checksum_verified_and_never_research(self):
        self.assertEqual(self.command("demo", "demo_test"), 0)
        path, verified, summary = self.returned("demo_test")
        self.assertEqual(verified["status"], "DEMO_ONLY")
        self.assertFalse(summary["phase2_ready"])
        self.assertEqual(summary["measured_pairs"], 0)
        self.assertGreater(summary["cases"], 0)
        with zipfile.ZipFile(path) as z:
            pairs = [json.loads(row) for row in z.read("demo_test/pair_measurements.jsonl").splitlines()]
            for pair in pairs:
                self.assertEqual(pair["origin"], "synthetic_control")
                self.assertAlmostEqual(pair["measurements"]["adsorbate_frame_rmsd_A"], 0.7, places=7)
                self.assertAlmostEqual(pair["measurements"]["internal_rmsd_A"], 0.0, places=7)
                self.assertFalse(pair["energetic_or_convergence_claims_enabled"])
            public = [json.loads(row) for row in z.read("demo_test/cases_public.jsonl").splitlines()]
            self.assertTrue(all(p["demo_only"] for p in public))
            self.assertTrue(all(set(p["model_payload"]) == {"claim", "evidence_packet"} for p in public))

    def test_missing_prepare_prevents_gpu_and_still_returns_diagnostic(self):
        with patch("geomscope.uma.relax_selected") as relax:
            self.assertEqual(self.command("run", "not_prepared"), 1)
            relax.assert_not_called()
        _, verified, summary = self.returned("not_prepared")
        self.assertEqual(verified["status"], "FAILED")
        self.assertEqual(summary["failed_stage"], "run")
        self.assertIn("Preparation did not complete", summary["error"])

    def test_prepared_run_joins_relaxation_records_and_excludes_nonconvergence(self):
        # All endpoints are explicitly synthetic fixtures, never model predictions.
        self.assertEqual(self.command("demo", "joined"), 0)
        out = self.results / "joined"
        folder = out / "demo_inputs"
        entry = dict(pair_id="synthetic_join_fixture", system_id="synthetic_join_fixture",
            group_id="synthetic_join_fixture", config_id="mock",
            initial_path=str(folder / "initial.extxyz"), final_path=str(folder / "final.extxyz"),
            mobile_indices=[4, 5, 6, 7], adsorbate_indices=[5, 6, 7], anchor_indices=[0, 1, 2, 3],
            adsorbate_bonds=[[5, 6], [5, 7]], converged=True)
        frozen = dict(entry, initial_sha256=runner.digest(entry["initial_path"]))
        runner.save_json(out / "selection.json", {"selection": [frozen]})
        runner.save_json(out / "model_manifest.json", {"mock_only": True})
        runner.snapshot(out)
        runner.freeze_inputs(out, 1)
        with patch("geomscope.uma.relax_selected", return_value=[entry]) as relax:
            self.assertEqual(self.command("run", "joined"), 0)
            self.assertEqual(relax.call_args.args[0], [frozen])
        _, _, summary = self.returned("joined")
        self.assertEqual(summary["measured_pairs"], 1)
        self.assertEqual(summary["synthetic_pairs"], 1)
        self.assertFalse(summary["phase2_ready"])
        capped = dict(entry, converged=False)
        with patch("geomscope.uma.relax_selected", return_value=[capped]):
            self.assertEqual(self.command("run", "joined"), 0)
        _, _, summary = self.returned("joined")
        self.assertEqual(summary["measured_pairs"], 0)
        self.assertEqual(summary["cases"], 0)
        self.assertEqual(summary["rejected"], 1)

    def test_prepared_manifest_change_prevents_inference(self):
        self.assertEqual(self.command("demo", "tampered"), 0)
        out = self.results / "tampered"
        runner.save_json(out / "selection.json", {"selection": []})
        runner.save_json(out / "model_manifest.json", {"mock_only": True})
        runner.snapshot(out)
        runner.freeze_inputs(out, 0)
        runner.save_json(out / "selection.json", {"selection": [], "changed_after_prepare": True})
        with patch("geomscope.uma.relax_selected") as relax:
            self.assertEqual(self.command("run", "tampered"), 1)
            relax.assert_not_called()
        _, _, summary = self.returned("tampered")
        self.assertIn("Frozen prepared artifact changed", summary["error"])

    def test_interrupted_gpu_collects_only_matching_logs_and_partial_records(self):
        out = self.results / "timeout"
        out.mkdir(parents=True)
        logs = self.root / "logs"
        logs.mkdir()
        (logs / "phase1-123.log").write_text("TIME LIMIT reached\n", encoding="utf-8")
        (logs / "phase1-999.log").write_text("unrelated job\n", encoding="utf-8")
        runner.save_json(out / "launcher_jobs.json", dict(gpu_job_id="123", logs_dir=str(logs)))
        runner.stage(out, "prepare", "COMPLETE")
        runner.stage(out, "run", "RUNNING")
        runner.save_json(out / "summary.json", dict(status="PREPARED_PENDING_GPU"))
        (out / "partial_record.json").write_text('{"converged":false}\n', encoding="utf-8")
        self.assertEqual(self.command("collect", "timeout"), 0)
        path, verified, summary = self.returned("timeout")
        self.assertEqual(verified["status"], "INTERRUPTED_OR_TIMEOUT")
        self.assertEqual(summary["interrupted_stage"], "run")
        with zipfile.ZipFile(path) as z:
            self.assertIn("timeout/partial_record.json", z.namelist())
            self.assertIn("timeout/slurm_logs/phase1-123.log", z.namelist())
            self.assertFalse(any("999" in name for name in z.namelist()))

    def test_configuration_change_cannot_reuse_frozen_run(self):
        self.assertEqual(self.command("demo", "frozen"), 0)
        config = runner.DEFAULTS.copy()
        config["fmax"] = 0.1
        runner.save_json(self.config, config)
        self.assertEqual(self.command("run", "frozen"), 1)
        _, _, summary = self.returned("frozen")
        self.assertIn("Configuration changed", summary["error"])

    def test_failed_data_preparation_is_returnable_without_model_access(self):
        out = self.results / "failed_data"
        out.mkdir(parents=True)
        runner.save_json(out / "selection.json", dict(status="INSUFFICIENT_ELIGIBLE_SYSTEMS", selection=[]))
        runner.stage(out, "prepare", "FAILED", error="No eligible systems")
        runner.save_json(out / "summary.json", dict(status="FAILED", failed_stage="prepare"))
        self.assertEqual(self.command("collect", "failed_data"), 0)
        _, verified, summary = self.returned("failed_data")
        self.assertEqual(verified["status"], "FAILED")
        self.assertEqual(summary["failed_stage"], "prepare")

    def test_corrupted_result_member_is_detected(self):
        self.assertEqual(self.command("demo", "corrupt"), 0)
        path, _, _ = self.returned("corrupt")
        damaged = self.root / "damaged.zip"
        with zipfile.ZipFile(path) as original, zipfile.ZipFile(damaged, "w") as dest:
            for name in original.namelist():
                data = original.read(name)
                dest.writestr(name, b"{}\n" if name.endswith("/case_audit.json") else data)
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            verifier.verify(damaged)

    def test_oversized_results_replace_older_zip_with_verified_diagnostic(self):
        self.assertEqual(self.command("demo", "oversized"), 0)
        out = self.results / "oversized"
        original = out / "large_artifact.bin"
        original.write_bytes(b"x" * 4096)
        with patch.object(runner, "RESULT_BYTES_LIMIT", 2048):
            self.assertEqual(self.command("collect", "oversized"), 2)
        path, verified, summary = self.returned("oversized")
        self.assertEqual(verified["status"], "PACKAGING_FAILED")
        self.assertEqual(summary["return_archive_kind"], "bounded_diagnostic")
        self.assertTrue(original.is_file())
        with zipfile.ZipFile(path) as z:
            self.assertIn("oversized/diagnostic_inventory.json", z.namelist())
            self.assertNotIn("oversized/large_artifact.bin", z.namelist())


if __name__ == "__main__":
    unittest.main()
