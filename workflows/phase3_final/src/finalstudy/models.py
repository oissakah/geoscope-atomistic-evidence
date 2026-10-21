"""Pinned, local-only language-model inference for the final frozen study.

Only prepare_models accesses the network. No credentials, checkpoints, audit
labels, or model-generated executable code belong in the returned results.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import time
from pathlib import Path, PurePosixPath

from .protocol import (CONDITIONS, MODEL_KEYS, MODEL_SPECS, PROMPTS,
                       PROTOCOL_VERSION, TEMPLATE_DATE)

MANIFEST_SCHEMA = 1
RUNTIME_SCHEMA = 2
_SMALL_FILES = {
    "config.json", "generation_config.json", "tokenizer.json", "tokenizer_config.json",
    "special_tokens_map.json", "added_tokens.json", "chat_template.jinja",
    "tokenizer.model", "vocab.json", "vocab.txt", "merges.txt",
}


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _digest_value(value):
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(_json_bytes(value) + b"\n")
    temporary.replace(path)


def _safe_error(exc):
    text = str(exc)
    text = re.sub(r"hf_[A-Za-z0-9]+", "[REDACTED_HF_TOKEN]", text)
    text = re.sub(r"https?://[^\s\]\)\"']+", "[URL_REDACTED]", text)
    text = re.sub(r"(?i)(authorization|token|password)\s*[:=]\s*[^\s,;]+",
                  r"\1=[REDACTED]", text)
    return f"{type(exc).__name__}: {text[:1500]}"


def _safe_member(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe model repository filename")
    return name


def _select_files(names, index=None):
    """Permit native config/tokenizer assets and one safetensors weight set."""
    names = set(names)
    chosen = {name for name in names if name in _SMALL_FILES}
    chosen.update(name for name in names if re.fullmatch(r"chat_templates/[A-Za-z0-9_.-]+\.jinja", name))
    if "config.json" not in chosen or "tokenizer_config.json" not in chosen:
        raise ValueError("Pinned repository lacks native configuration/tokenizer configuration")
    if "model.safetensors.index.json" in names:
        if not isinstance(index, dict) or not isinstance(index.get("weight_map"), dict) or not index["weight_map"]:
            raise ValueError("Invalid safetensors shard index")
        shards = set(index["weight_map"].values())
        if any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+\.safetensors", name)
               for name in shards):
            raise ValueError("Unsafe or non-safetensors shard in model index")
        if not shards <= names:
            raise ValueError("Safetensors index names missing repository shards")
        chosen.update(shards)
        chosen.add("model.safetensors.index.json")
    elif "model.safetensors" in names:
        chosen.add("model.safetensors")
    else:
        raise ValueError("Pinned repository lacks supported native safetensors weights")
    return sorted(_safe_member(name) for name in chosen)


def _manifest_entry(entry, key, complete=True):
    if key not in MODEL_SPECS or entry.get("repo_id") != MODEL_SPECS[key]["repo_id"]:
        raise ValueError("Model manifest does not match the fixed pilot model set")
    if not re.fullmatch(r"[0-9a-f]{40}", str(entry.get("revision", ""))):
        raise ValueError("Model revision must be an immutable 40-character commit SHA")
    if complete and (not entry.get("local_path") or not entry.get("files")):
        raise ValueError("Model preparation is incomplete")
    for item in entry.get("files", []):
        _safe_member(item["path"])
        if not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")):
            raise ValueError("Invalid model file digest")
        if type(item.get("bytes")) is not int or item["bytes"] < 0:
            raise ValueError("Invalid model file size")


def _verify_files(entry):
    folder = Path(entry["local_path"])
    for item in entry["files"]:
        path = folder / _safe_member(item["path"])
        if not path.is_file() or path.stat().st_size != item["bytes"] or _file_digest(path) != item["sha256"]:
            raise ValueError(f"Pinned model file failed integrity verification: {item['path']}")


def prepare_models(cache_dir: Path, out_dir: Path) -> dict:
    """Resolve revisions once and download their native, safe serialization assets.

    The revision lock is also kept in cache so a restarted preparation cannot
    accidentally resolve a newer main branch. HF authentication is implicit.
    """
    cache_dir, out_dir = Path(cache_dir).resolve(), Path(out_dir).resolve()
    if cache_dir == out_dir or out_dir in cache_dir.parents:
        raise ValueError("Model cache must be outside the results folder")
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    lock_path, report_path = cache_dir / "phase2_model_manifest.json", out_dir / "model_manifest.json"
    try:
        from huggingface_hub import HfApi, hf_hub_download, snapshot_download
        if lock_path.is_file():
            manifest = json.loads(lock_path.read_text(encoding="utf-8"))
            if manifest.get("schema_version") != MANIFEST_SCHEMA or set(manifest.get("models", {})) != set(MODEL_KEYS):
                raise ValueError("Existing model revision lock has an incompatible schema")
        else:
            api = HfApi()
            entries = {}
            for key, spec in MODEL_SPECS.items():
                info = api.model_info(spec["repo_id"], revision="main", files_metadata=False)
                entries[key] = {**spec, "revision": info.sha, "local_path": None, "files": [],
                                "card_url": "https://huggingface.co/" + spec["repo_id"]}
                _manifest_entry(entries[key], key, complete=False)
            manifest = {"schema_version": MANIFEST_SCHEMA, "model_keys": list(MODEL_KEYS), "models": entries}
            _save_json(lock_path, manifest)
        _save_json(report_path, manifest)
        api = HfApi()
        for key in MODEL_KEYS:
            entry = manifest["models"][key]
            _manifest_entry(entry, key, complete=False)
            if entry.get("files"):
                _verify_files(entry)
                continue
            info = api.model_info(entry["repo_id"], revision=entry["revision"], files_metadata=False)
            if info.sha != entry["revision"]:
                raise ValueError("Hub returned a different revision than the frozen commit")
            names = [item.rfilename for item in info.siblings]
            index = None
            if "model.safetensors.index.json" in names:
                index_path = hf_hub_download(entry["repo_id"], "model.safetensors.index.json",
                                             revision=entry["revision"], cache_dir=str(cache_dir / "hub"))
                index = json.loads(Path(index_path).read_text(encoding="utf-8"))
            chosen = _select_files(names, index)
            snapshot = Path(snapshot_download(entry["repo_id"], revision=entry["revision"],
                                              cache_dir=str(cache_dir / "hub"), allow_patterns=chosen,
                                              max_workers=2))
            entry["local_path"] = str(snapshot.resolve())
            entry["files"] = [dict(path=name, bytes=(snapshot / name).stat().st_size,
                                    sha256=_file_digest(snapshot / name)) for name in chosen]
            _manifest_entry(entry, key)
            _save_json(lock_path, manifest)
            _save_json(report_path, manifest)
        return manifest
    except Exception as exc:
        raise RuntimeError("Model preparation failed. Check network, storage, and HF access. " + _safe_error(exc)) from None


def _payload(case):
    if not isinstance(case, dict) or not isinstance(case.get("case_id"), str) or not case["case_id"]:
        raise ValueError("Every public case needs a nonempty string case_id")
    payload = case.get("model_payload")
    if not isinstance(payload, dict):
        raise ValueError("Every public case needs a model_payload object")
    if set(payload) not in ({"claim", "evidence_packet"}, {"claim", "evidence_report"}):
        raise ValueError("Only claim and evidence_packet/evidence_report may enter a model payload")
    _json_bytes(payload)
    return payload


def _messages(payload, condition):
    if condition not in CONDITIONS:
        raise ValueError("Unknown prompt condition")
    return [{"role": "user", "content": PROMPTS[condition] + "\n\n" +
             _json_bytes(payload).decode("utf-8")}]


def _versions():
    versions = {}
    for name in ("torch", "transformers", "accelerate", "huggingface-hub", "safetensors", "tokenizers"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"python": platform.python_version(), "packages": versions}


def _fixed_template_time(format_string):
    # SmolLM3's official template otherwise inserts the current wall-clock date,
    # changing prompt hashes across a resumed or overnight job.
    if format_string != "%d %B %Y":
        raise ValueError("Unreviewed dynamic date format in pinned chat template")
    return TEMPLATE_DATE


class _NativeBackend:
    def __init__(self, key, entry, seed):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        if not torch.cuda.is_available():
            raise RuntimeError("A CUDA GPU allocation is required for Phase 2 model inference")
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        self.torch, self.key = torch, key
        self.dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        folder = entry["local_path"]
        self.tokenizer = AutoTokenizer.from_pretrained(folder, local_files_only=True,
                                                       trust_remote_code=False, padding_side="left")
        if self.tokenizer.pad_token_id is None:
            if self.tokenizer.eos_token_id is None:
                raise ValueError("Tokenizer has no usable padding or end token")
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "left"
        self.model = AutoModelForCausalLM.from_pretrained(
            folder, local_files_only=True, trust_remote_code=False, use_safetensors=True,
            dtype=self.dtype, attn_implementation="sdpa", device_map={"": "cuda:0"})
        self.model.eval()
        self.metadata = {
            **_versions(), "gpu_name": torch.cuda.get_device_name(0), "cuda_runtime": torch.version.cuda,
            "dtype": str(self.dtype), "attention_implementation": "sdpa",
            "model_class": type(self.model).__name__, "tokenizer_class": type(self.tokenizer).__name__,
            "chat_template_sha256": _digest_value(self.tokenizer.chat_template),
            "template_date": TEMPLATE_DATE,
            "token_identity": "SHA256 of canonical JSON of unpadded input token IDs with add_special_tokens=False",
            "tf32": False, "cudnn_benchmark": False, "extended_thinking": False,
            "determinism": "Greedy decoding with seeded torch; exact cross-hardware equality is not guaranteed.",
        }

    def format_prompt(self, payload, condition):
        kwargs = {"tokenize": False, "add_generation_prompt": True}
        if self.key == "smol":
            kwargs["enable_thinking"] = False
            kwargs["strftime_now"] = _fixed_template_time
        return self.tokenizer.apply_chat_template(_messages(payload, condition), **kwargs)

    def count_tokens(self, text):
        return len(self.tokenizer(text, add_special_tokens=False)["input_ids"])

    def token_fingerprint(self, text):
        ids = self.tokenizer(text, add_special_tokens=False)["input_ids"]
        return {"input_token_count": len(ids), "input_ids_sha256": _digest_value(ids)}

    def generate(self, prompts, max_new_tokens):
        started = time.monotonic()
        inputs = self.tokenizer(prompts, padding=True, add_special_tokens=False,
                                truncation=False, return_tensors="pt").to("cuda:0")
        prompt_width = inputs["input_ids"].shape[1]
        with self.torch.inference_mode():
            outputs = self.model.generate(
                **inputs, max_new_tokens=max_new_tokens, do_sample=False, num_beams=1,
                use_cache=True, pad_token_id=self.tokenizer.pad_token_id)
        self.torch.cuda.synchronize()
        duration = time.monotonic() - started
        eos = self.model.generation_config.eos_token_id
        eos = set(eos if isinstance(eos, (tuple, list)) else [eos]) if eos is not None else set()
        records = []
        for row in outputs:
            ids = row[prompt_width:].tolist()
            eos_index = next((i for i, token in enumerate(ids) if token in eos), None)
            used = ids[:eos_index + 1] if eos_index is not None else ids
            records.append({"raw_output": self.tokenizer.decode(used, skip_special_tokens=True),
                            "token_count": len(used),
                            "truncated": eos_index is None and len(used) >= max_new_tokens,
                            "elapsed_seconds": duration / len(prompts),
                            "batch_elapsed_seconds": duration})
        return records


def _load_backend(key, entry, seed):
    return _NativeBackend(key, entry, seed)


def _append_records(path, rows):
    with Path(path).open("a", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(_json_bytes(row).decode("utf-8") + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _read_records(path):
    if not Path(path).is_file():
        return []
    rows = []
    # Never silently discard a partial write: it needs an explicit operator review.
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            raise ValueError(f"Prediction file has an incomplete/invalid record at line {number}") from None
    return rows


def run_model(model_key, manifest, public_cases: list[dict], out_dir, seed=20261021,
              max_new_tokens=160, batch_size=2, max_input_tokens=6144):
    """Run each independent case under both frozen prompt conditions, resumably."""
    if model_key not in MODEL_KEYS:
        raise ValueError("Unknown pilot model key")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError("Unsupported model manifest schema")
    entry = manifest.get("models", {}).get(model_key, {})
    _manifest_entry(entry, model_key)
    for name, value, high in (("seed", seed, 2**32 - 1), ("max_new_tokens", max_new_tokens, 2048),
                             ("batch_size", batch_size, 16), ("max_input_tokens", max_input_tokens, 32768)):
        if type(value) is not int or not (0 if name == "seed" else 1) <= value <= high:
            raise ValueError("Invalid inference setting: " + name)
    ids = [case.get("case_id") for case in public_cases]
    if not public_cases or len(set(ids)) != len(ids):
        raise ValueError("Cases must be nonempty with unique case IDs")
    payloads = [_payload(case) for case in public_cases]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / f"predictions_{model_key}.jsonl"
    meta_path = out_dir / f"inference_{model_key}.json"
    settings = dict(seed=seed, max_new_tokens=max_new_tokens, batch_size=batch_size,
                    max_input_tokens=max_input_tokens, do_sample=False, num_beams=1,
                    truncation=False, use_cache=True, conditions=list(CONDITIONS))
    identity = {"schema_version": RUNTIME_SCHEMA, "model_key": model_key,
                "model": entry, "settings": settings, "prompts": PROMPTS,
                "cases": [dict(case_id=case["case_id"], payload=payload)
                          for case, payload in zip(public_cases, payloads)], "versions": _versions()}
    run_signature = _digest_value(identity)
    previous = _read_records(result_path)
    if meta_path.is_file():
        prior_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if prior_meta.get("run_signature") != run_signature:
            raise ValueError("Resume refused: model, evidence, prompts, versions or settings changed")
    elif previous:
        raise ValueError("Resume refused: prediction file exists without its frozen inference manifest")
    else:
        prior_meta = None
    _verify_files(entry)
    try:
        backend = _load_backend(model_key, entry, seed)
    except Exception as exc:
        _save_json(meta_path, dict(schema_version=RUNTIME_SCHEMA, run_signature=run_signature,
                                  settings=settings, status="MODEL_LOAD_FAILED", error=_safe_error(exc)))
        raise RuntimeError("Local model loading failed. " + _safe_error(exc)) from None
    if prior_meta and prior_meta.get("backend") and prior_meta["backend"] != backend.metadata:
        raise ValueError("Resume refused: hardware, model/tokenizer implementation or backend changed")
    metadata = dict(schema_version=RUNTIME_SCHEMA, model_key=model_key, run_signature=run_signature,
                    settings=settings, backend=backend.metadata, status="RUNNING", expected_records=len(ids) * len(CONDITIONS),
                    protocol_version=PROTOCOL_VERSION,
                    model_revision=entry["revision"], model_file_manifest_sha256=_digest_value(entry["files"]))
    _save_json(meta_path, metadata)
    requests = []
    for case, payload in zip(public_cases, payloads):
        for condition in CONDITIONS:
            prompt = backend.format_prompt(payload, condition)
            prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            tokens = backend.token_fingerprint(prompt)
            request_signature = _digest_value(dict(run_signature=run_signature, case_id=case["case_id"],
                                                   condition=condition, prompt_hash=prompt_hash,
                                                   input_ids_sha256=tokens["input_ids_sha256"]))
            requests.append(dict(case_id=case["case_id"], condition=condition,
                                 model_key=model_key,
                                 prompt_hash=prompt_hash, request_signature=request_signature,
                                 **tokens, prompt=prompt))
    expected = {request["request_signature"]: request for request in requests}
    seen = set()
    for row in previous:
        signature = row.get("request_signature")
        if signature not in expected or signature in seen:
            raise ValueError("Resume refused: duplicate or foreign prediction record")
        request = expected[signature]
        if any(row.get(key) != request[key] for key in ("case_id", "condition", "prompt_hash", "model_key",
                                                     "input_ids_sha256", "input_token_count")):
            raise ValueError("Resume refused: prediction identity mismatch")
        seen.add(signature)
    pending = [request for request in requests if request["request_signature"] not in seen]
    try:
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset:offset + batch_size]
            acceptable, written = [], []
            for request in batch:
                if request["input_token_count"] > max_input_tokens:
                    written.append({key: value for key, value in request.items() if key != "prompt"} |
                                   dict(status="input_too_long", error="Input exceeds protocol token limit; no truncation performed",
                                        raw_output="", token_count=0, truncated=False, elapsed_seconds=0.0))
                else:
                    acceptable.append(request)
            if acceptable:
                try:
                    generated = backend.generate([request["prompt"] for request in acceptable], max_new_tokens)
                    if len(generated) != len(acceptable):
                        raise ValueError("Backend returned wrong number of predictions")
                    for request, output in zip(acceptable, generated):
                        written.append({key: value for key, value in request.items() if key != "prompt"} |
                                       output | dict(status="truncated" if output["truncated"] else "ok"))
                except Exception as exc:
                    written.extend({key: value for key, value in request.items() if key != "prompt"} |
                                   dict(status="generation_failed", error=_safe_error(exc), raw_output="",
                                        token_count=0, truncated=False, elapsed_seconds=0.0)
                                   for request in acceptable)
                    _append_records(result_path, written)
                    metadata.update(status="GENERATION_FAILED", error=_safe_error(exc))
                    _save_json(meta_path, metadata)
                    # No automatic batch resizing or retry; preserve the failed requests.
                    raise RuntimeError("Generation failed; recorded diagnostics. " + _safe_error(exc)) from None
            _append_records(result_path, written)
            print(f"{model_key}: {len(previous) + offset + len(batch)}/{len(requests)} requests recorded", flush=True)
        rows = _read_records(result_path)
        metadata.update(status="COMPLETE", recorded_records=len(rows),
                        failed_records=sum(row["status"] not in {"ok", "truncated"} for row in rows),
                        truncated_records=sum(row["truncated"] for row in rows))
        if metadata["failed_records"] or metadata["truncated_records"]:
            metadata["status"] = "COMPLETE_WITH_ERRORS"
        _save_json(meta_path, metadata)
        rank = {request["request_signature"]: i for i, request in enumerate(requests)}
        return sorted(rows, key=lambda row: rank[row["request_signature"]])
    except Exception:
        # Existing durable predictions and inference metadata remain reviewable.
        raise
