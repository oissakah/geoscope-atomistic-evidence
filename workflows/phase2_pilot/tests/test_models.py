"""CPU-only tests for the model protocol. No checkpoint download or inference."""
import copy
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from phase2 import models


class FakeBackend:
    def __init__(self, fail=False, long=False, truncated=False):
        self.metadata = {"mock": True, "dtype": "mock", "gpu_name": "synthetic-test"}
        self.fail, self.long, self.truncated = fail, long, truncated
        self.calls = []

    def format_prompt(self, payload, condition):
        return json.dumps(models._messages(payload, condition), sort_keys=True)

    def count_tokens(self, text):
        return 7000 if self.long else 100

    def generate(self, prompts, max_new_tokens):
        self.calls.append((prompts, max_new_tokens))
        if self.fail:
            raise RuntimeError("OOM https://example.test/?token=hf_SECRET123 token=hidden")
        return [dict(raw_output='{"verdict":"SUPPORTED","evidence_ids":["E1"]}',
                     token_count=20, truncated=self.truncated, elapsed_seconds=.01) for _ in prompts]


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        folder = self.base / "checkpoint"
        folder.mkdir()
        (folder / "config.json").write_text("{}")
        files = [dict(path="config.json", sha256=models._file_digest(folder / "config.json"), bytes=2)]
        self.manifest = {"schema_version": 1, "models": {
            key: dict(repo_id=spec["repo_id"], revision="a" * 40, local_path=str(folder), files=copy.deepcopy(files))
            for key, spec in models.MODEL_SPECS.items()}}
        self.cases = [dict(case_id="opaque-one", gold="DO NOT SEND", family="DO NOT SEND",
                           model_payload=dict(claim="Measure is below threshold", evidence_packet=[{"id": "E1", "value": .2}])),
                      dict(case_id="opaque-two", model_payload=dict(claim="Other claim", evidence_report="E2 states 0.3 A"))]
        self.out = self.base / "results"

    def run_fake(self, fake=None, **kwargs):
        fake = fake or FakeBackend()
        with patch.object(models, "_load_backend", return_value=fake):
            rows = models.run_model("qwen", self.manifest, self.cases, self.out, **kwargs)
        return rows, fake

    def test_allowlist_excludes_unsafe_and_duplicate_weights(self):
        names = {"config.json", "tokenizer_config.json", "tokenizer.json", "model.safetensors.index.json",
                 "model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors",
                 "model.safetensors", "consolidated.safetensors", "pytorch_model.bin", "modeling_custom.py"}
        selected = models._select_files(names, {"weight_map": {"a": "model-00001-of-00002.safetensors",
                                                               "b": "model-00002-of-00002.safetensors"}})
        self.assertIn("model-00001-of-00002.safetensors", selected)
        self.assertFalse({"model.safetensors", "consolidated.safetensors", "pytorch_model.bin", "modeling_custom.py"} & set(selected))
        with self.assertRaises(ValueError):
            models._select_files(names, {"weight_map": {"a": "../outside.safetensors"}})

    def test_missing_shard_is_rejected(self):
        with self.assertRaises(ValueError):
            models._select_files(["config.json", "tokenizer_config.json", "model.safetensors.index.json"],
                                 {"weight_map": {"x": "absent.safetensors"}})

    def test_single_safetensors_supported(self):
        self.assertEqual(models._select_files(["config.json", "tokenizer_config.json", "model.safetensors", "evil.py"]),
                         ["config.json", "model.safetensors", "tokenizer_config.json"])

    def test_payload_only_and_separate_context(self):
        rows, fake = self.run_fake()
        self.assertEqual(len(rows), 4)
        prompts = [prompt for batch, _ in fake.calls for prompt in batch]
        self.assertTrue(all("DO NOT SEND" not in prompt for prompt in prompts))
        for prompt in prompts:
            messages = json.loads(prompt)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]["role"], "user")
        self.assertNotIn("Other claim", prompts[0])
        self.assertNotIn("Measure is below threshold", prompts[2])
        self.assertEqual({row["condition"] for row in rows}, set(models.CONDITIONS))
        self.assertTrue(all(row["status"] == "ok" for row in rows))
        self.assertTrue(all(row["model_key"] == "qwen" for row in rows))
        self.assertTrue(all("prompt" not in row for row in rows))

    def test_payload_leakage_is_rejected(self):
        self.cases[0]["model_payload"]["gold"] = "SUPPORTED"
        with self.assertRaisesRegex(ValueError, "Only claim"):
            self.run_fake()

    def test_resume_does_not_regenerate(self):
        rows, _ = self.run_fake()
        resumed, fake = self.run_fake()
        self.assertEqual(rows, resumed)
        self.assertFalse(fake.calls)

    def test_resume_rejects_payload_prompt_setting_or_revision_changes(self):
        self.run_fake()
        with self.assertRaisesRegex(ValueError, "Resume refused"):
            self.run_fake(seed=42)
        self.cases[0]["model_payload"]["claim"] = "Changed"
        with self.assertRaisesRegex(ValueError, "Resume refused"):
            self.run_fake()

    def test_resume_rejects_duplicate_record(self):
        self.run_fake()
        file = self.out / "predictions_qwen.jsonl"
        first = file.read_text().splitlines()[0]
        with file.open("a") as stream:
            stream.write(first + "\n")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.run_fake()

    def test_overlength_is_logged_without_generation(self):
        rows, fake = self.run_fake(FakeBackend(long=True))
        self.assertFalse(fake.calls)
        self.assertTrue(all(row["status"] == "input_too_long" for row in rows))
        self.assertTrue(all(not row["truncated"] for row in rows))

    def test_truncated_output_is_preserved(self):
        rows, _ = self.run_fake(FakeBackend(truncated=True))
        self.assertTrue(all(row["status"] == "truncated" for row in rows))
        self.assertTrue(all(row["raw_output"] for row in rows))
        self.assertEqual(json.loads((self.out / "inference_qwen.json").read_text())["status"],
                         "COMPLETE_WITH_ERRORS")

    def test_generation_failure_is_durable_and_sanitized(self):
        with self.assertRaisesRegex(RuntimeError, "Generation failed"):
            self.run_fake(FakeBackend(fail=True))
        text = (self.out / "predictions_qwen.jsonl").read_text()
        rows = [json.loads(line) for line in text.splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["status"] == "generation_failed" for row in rows))
        self.assertNotIn("hf_SECRET", text)
        self.assertNotIn("https://", text)
        self.assertNotIn("hidden", text)
        resumed, fake = self.run_fake()
        self.assertEqual(len(resumed), 4)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(sum(row["status"] == "generation_failed" for row in resumed), 2)

    def test_integrity_corruption_rejected(self):
        folder = Path(self.manifest["models"]["qwen"]["local_path"])
        (folder / "config.json").write_text("xx")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.run_fake()

    def test_commit_and_safe_paths_required(self):
        entry = copy.deepcopy(self.manifest["models"]["qwen"])
        entry["revision"] = "main"
        with self.assertRaises(ValueError):
            models._manifest_entry(entry, "qwen")
        for path in ("../evil", "C:/evil", "\\evil", "/absolute"):
            with self.assertRaises(ValueError):
                models._safe_member(path)

    def test_native_load_is_local_safetensors_sdpa_and_no_remote_code(self):
        torch = types.SimpleNamespace(
            manual_seed=Mock(), bfloat16="bf16", float16="fp16",
            cuda=types.SimpleNamespace(is_available=lambda: True, manual_seed_all=Mock(),
                                       is_bf16_supported=lambda: True, get_device_name=lambda n: "mock"),
            backends=types.SimpleNamespace(cuda=types.SimpleNamespace(matmul=types.SimpleNamespace()),
                                          cudnn=types.SimpleNamespace()),
            version=types.SimpleNamespace(cuda="mock"))
        tokenizer = Mock(pad_token_id=0, eos_token_id=1, chat_template="{{messages}}")
        hf = types.SimpleNamespace(AutoTokenizer=Mock(), AutoModelForCausalLM=Mock())
        hf.AutoTokenizer.from_pretrained.return_value = tokenizer
        hf.AutoModelForCausalLM.from_pretrained.return_value = Mock()
        with patch.dict(sys.modules, {"torch": torch, "transformers": hf}):
            backend = models._NativeBackend("smol", self.manifest["models"]["smol"], 1)
            backend.format_prompt(self.cases[0]["model_payload"], "direct")
        kwargs = hf.AutoModelForCausalLM.from_pretrained.call_args.kwargs
        self.assertEqual(kwargs["dtype"], "bf16")
        self.assertEqual(kwargs["attn_implementation"], "sdpa")
        self.assertEqual(kwargs["device_map"], {"": "cuda:0"})
        self.assertTrue(kwargs["use_safetensors"])
        self.assertTrue(kwargs["local_files_only"])
        self.assertFalse(kwargs["trust_remote_code"])
        self.assertFalse(tokenizer.apply_chat_template.call_args.kwargs["enable_thinking"])
        frozen_date = tokenizer.apply_chat_template.call_args.kwargs["strftime_now"]
        self.assertEqual(frozen_date("%d %B %Y"), "20 October 2026")
        with self.assertRaises(ValueError):
            frozen_date("%s")

    def test_prepare_pins_once_and_selects_only_needed_files(self):
        hf = types.SimpleNamespace(HfApi=Mock(), hf_hub_download=Mock(), snapshot_download=Mock())
        info = types.SimpleNamespace(sha="b" * 40, siblings=[types.SimpleNamespace(rfilename=name)
             for name in ["config.json", "tokenizer_config.json", "tokenizer.json", "model.safetensors", "evil.py", "pytorch_model.bin"]])
        hf.HfApi.return_value.model_info.return_value = info
        snapshot = self.base / "snapshot"
        snapshot.mkdir()
        for name in ("config.json", "tokenizer_config.json", "tokenizer.json", "model.safetensors"):
            (snapshot / name).write_text("{}")
        hf.snapshot_download.return_value = str(snapshot)
        with patch.dict(sys.modules, {"huggingface_hub": hf}):
            manifest = models.prepare_models(self.base / "cache", self.out)
            first_calls = list(hf.HfApi.return_value.model_info.call_args_list)
            manifest2 = models.prepare_models(self.base / "cache", self.out)
        self.assertEqual(manifest, manifest2)
        self.assertEqual(len(first_calls), 6)
        self.assertEqual(hf.HfApi.return_value.model_info.call_count, 6)
        for call in hf.snapshot_download.call_args_list:
            self.assertEqual(call.kwargs["revision"], "b" * 40)
            self.assertNotIn("evil.py", call.kwargs["allow_patterns"])
            self.assertNotIn("pytorch_model.bin", call.kwargs["allow_patterns"])
        self.assertEqual(len(manifest["models"]), 3)
        self.assertTrue((self.out / "model_manifest.json").is_file())

    def test_model_cache_must_not_be_in_result_tree(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            models.prepare_models(self.out / "cache", self.out)


if __name__ == "__main__":
    unittest.main()
