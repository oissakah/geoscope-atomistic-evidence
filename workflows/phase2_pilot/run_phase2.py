#!/usr/bin/env python3
"""Run a frozen Phase 2 development diagnostic, never a protected test."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import re
import stat
import sys
import time
import traceback
import unittest
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import phase2_support as support

PARENT_SHA256 = "f99604ad0d7a29dfbb123b4845a7078b84d7ca45ed1b01a09ecdf8a1fe51c326"
MODEL_KEYS = ("qwen", "phi", "smol")
CONDITIONS = ("direct", "scope_checklist")
DEFAULT_CONFIG = dict(seed=20261020, max_new_tokens=160, batch_size=2,
                      max_input_tokens=6144, bootstrap_samples=1000)


def read_jsonl(path, *, allow_partial_last=False):
    data = Path(path).read_text(encoding="utf-8")
    lines, result = data.splitlines(), []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            if allow_partial_last and index == len(lines) - 1 and not data.endswith("\n"):
                return result, "Discarded one incomplete final JSONL record after interruption"
            raise
    return result, None


def load_config(path):
    config = support.load_json(path)
    if set(config) != set(DEFAULT_CONFIG):
        raise ValueError("Configuration must match the supplied schema; credentials never belong in it")
    for name, low, high in (("seed", 0, 2**32-1), ("max_new_tokens", 32, 512),
                           ("batch_size", 1, 4), ("max_input_tokens", 2048, 16384),
                           ("bootstrap_samples", 100, 5000)):
        if type(config[name]) is not int or not low <= config[name] <= high:
            raise ValueError(f"Invalid integer configuration: {name}")
    return config


def parent_data(path, *, _expected_sha256=PARENT_SHA256):
    """Verify the reviewed data archive without executing its archived sources."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("Reviewed Phase 1 continuation ZIP missing or too large")
    if support.digest(path) != _expected_sha256:
        raise ValueError("Phase 1 continuation ZIP differs from the reviewed archive")
    with zipfile.ZipFile(path) as z:
        infos, names = z.infolist(), z.namelist()
        if len(names) > 1000 or len(names) != len(set(names)) or sum(i.file_size for i in infos) > 128*1024*1024:
            raise ValueError("Unexpected archive size or duplicate members")
        for info in infos:
            p, mode = PurePosixPath(info.filename), info.external_attr >> 16
            if (p.is_absolute() or ".." in p.parts or "\\" in info.filename or ":" in info.filename
                    or info.is_dir() or stat.S_ISLNK(mode)):
                raise ValueError("Unsafe parent archive member")
        manifests = [name for name in names if name.endswith("/SHA256SUMS.json")]
        if len(manifests) != 1:
            raise ValueError("Expected exactly one reviewed checksum manifest")
        prefix = manifests[0].removesuffix("SHA256SUMS.json")
        hashes = json.loads(z.read(manifests[0]))
        if {prefix+k for k in hashes} | {manifests[0]} != set(names):
            raise ValueError("Missing or untracked parent archive members")
        for name, expected in hashes.items():
            if hashlib.sha256(z.read(prefix+name)).hexdigest() != expected:
                raise ValueError(f"Parent checksum mismatch: {name}")
        summary = json.loads(z.read(prefix+"summary.json"))
        if (summary.get("measured_pairs") != 20 or summary.get("rejected") != 0
                or summary.get("outcome_counts") != {"converged": 20}):
            raise ValueError("Parent does not match the reviewed complete 20-system pilot")
        pairs = [json.loads(line) for line in z.read(prefix+"pair_measurements.jsonl").splitlines()]
        provenance = dict(parent_run_id=prefix.rstrip("/"), parent_archive_sha256=_expected_sha256,
            verified_files=len(hashes), parent_summary=summary,
            scientific_gate="Accepted as coordinate-measurement development pilot; not protected test data")
        return pairs, provenance


def build_data(out, parent_zip, config):
    from phase2.benchmark import build_benchmark, baseline
    pairs, provenance = parent_data(parent_zip)
    public, gold, audit = build_benchmark(pairs, seed=config["seed"])
    if len(public) != 320 or len(gold) != 320:
        raise ValueError("The declared development diagnostic requires exactly 320 variants")
    support.jsonl(out / "benchmark_public.jsonl", public)
    support.jsonl(out / "benchmark_gold_DO_NOT_SEND_TO_MODELS.jsonl", gold)
    support.save_json(out / "benchmark_audit.json", audit)
    support.jsonl(out / "source_pair_measurements.jsonl", pairs)
    support.save_json(out / "parent_provenance.json", provenance)
    baselines = []
    for method in ("scope", "value_only", "structure"):
        for case in public:
            answer = baseline(case["model_payload"], method=method)
            baselines.append(dict(case_id=case["case_id"], model_key=method+"_baseline", condition="baseline",
                raw_output=json.dumps(answer), status="ok"))
    gold_by_id = {item["case_id"]: item for item in gold}
    for record in baselines:
        if record["model_key"] == "scope_baseline":
            answer, expected = json.loads(record["raw_output"]), gold_by_id[record["case_id"]]
            if (answer["verdict"] != expected["expected"]
                    or set(answer["evidence_ids"]) != set(expected["required_evidence_ids"])):
                raise ValueError("Payload-only control disagrees with gold; GPU evaluation is blocked")
    support.jsonl(out / "baseline_predictions.jsonl", baselines)
    return public, gold


def freeze(out):
    names = ("run_config.json", "benchmark_public.jsonl", "benchmark_gold_DO_NOT_SEND_TO_MODELS.jsonl",
             "benchmark_audit.json", "baseline_predictions.jsonl", "model_manifest.json", "code_sha256.json")
    support.save_json(out / "prepared_sha256.json", {name: support.digest(out/name) for name in names})


def verify_frozen(out):
    for name, expected in support.load_json(out / "prepared_sha256.json").items():
        if support.digest(out/name) != expected:
            raise ValueError(f"Prepared input changed: {name}")
    current = {p.relative_to(ROOT).as_posix(): support.digest(p) for p in support.source_files()}
    if current != support.load_json(out / "code_sha256.json"):
        raise ValueError("Source changed after preparation; choose a new run ID")


def prepare(out, cache, parent_zip, config):
    from phase2.models import prepare_models
    support.snapshot(out)
    support.save_json(out / "environment_prepare.json", support.environment())
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover(str(ROOT/"tests")))
    support.save_json(out / "self_tests.json", dict(tests_run=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), success=result.wasSuccessful()))
    if not result.wasSuccessful():
        raise RuntimeError("Phase 2 self-tests failed; see prepare.log")
    build_data(out, parent_zip, config)
    prepare_models(cache, out)
    freeze(out)
    support.stage(out, "prepare", "COMPLETE")
    return dict(status="PREPARED_PENDING_MODELS", case_variants=320, source_groups=20)


def run(out, model_key, config):
    from phase2.models import run_model
    if not (out / "stage_prepare.json").exists() or support.load_json(out/"stage_prepare.json").get("state") != "COMPLETE":
        raise RuntimeError("Phase 2 preparation did not complete; collect diagnostics")
    verify_frozen(out)
    public, _ = read_jsonl(out / "benchmark_public.jsonl")
    manifest = support.load_json(out / "model_manifest.json")
    records = run_model(model_key, manifest, public, out, seed=config["seed"],
        max_new_tokens=config["max_new_tokens"], batch_size=config["batch_size"],
        max_input_tokens=config["max_input_tokens"])
    support.stage(out, model_key, "COMPLETE", recorded_requests=len(records))
    return dict(status="MODEL_JOB_FINISHED", model_key=model_key, recorded_requests=len(records))


def collect_logs(out):
    if not (out/"launcher_jobs.json").exists():
        return
    jobs = support.load_json(out/"launcher_jobs.json")
    folder = Path(jobs["logs_dir"])
    for key, stem in (("prepare_job_id", "prepare"), ("qwen_job_id", "model"),
                      ("phi_job_id", "model"), ("smol_job_id", "model"), ("collect_job_id", "collect")):
        number = str(jobs.get(key, ""))
        source = folder / f"{stem}-{number}.log"
        if number.isdigit() and source.is_file() and not source.is_symlink():
            target = out / "slurm_logs" / source.name
            target.parent.mkdir(exist_ok=True)
            with source.open("rb") as stream:
                stream.seek(max(0, source.stat().st_size-1024*1024))
                text = stream.read().decode("utf-8", errors="replace")
            target.write_text(support.safe_text(text), encoding="utf-8")


def collect(out, parent_zip, config):
    from phase2.evaluation import evaluate, write_reports
    collect_logs(out)
    if not (out/"prepared_sha256.json").exists():
        return dict(status="PREPARATION_FAILED_OR_INTERRUPTED", model_evaluation_complete=False,
                    action="Return this diagnostic ZIP; inspect preparation logs")
    verify_frozen(out)
    public, _ = read_jsonl(out/"benchmark_public.jsonl")
    gold, _ = read_jsonl(out/"benchmark_gold_DO_NOT_SEND_TO_MODELS.jsonl")
    predictions, _ = read_jsonl(out/"baseline_predictions.jsonl")
    warnings, successful = [], 0
    for key in MODEL_KEYS:
        path = out/f"predictions_{key}.jsonl"
        actual, warning = read_jsonl(path, allow_partial_last=True) if path.exists() else ([], None)
        if warning:
            warnings.append(dict(model_key=key, warning=warning))
        expected_keys = {(case["case_id"], condition) for case in public for condition in CONDITIONS}
        seen = {(r["case_id"], r["condition"]) for r in actual}
        if (len(seen) != len(actual) or not seen <= expected_keys
                or any(r.get("model_key") != key for r in actual)):
            raise ValueError("Unexpected case/condition, duplicate request or mismatched model in raw predictions")
        predictions.extend(actual)
        successful += sum(r.get("status") == "ok" for r in actual)
        for condition in CONDITIONS:
            for case in public:
                if (case["case_id"], condition) not in seen:
                    predictions.append(dict(case_id=case["case_id"], model_key=key, condition=condition,
                        status="missing", raw_output="", error="No completed record; job interrupted or unavailable"))
    result = evaluate(public, gold, predictions, seed=config["seed"], bootstrap_samples=config["bootstrap_samples"])
    write_reports(result, out)
    support.save_json(out/"collection_warnings.json", warnings)
    expected = len(public)*len(MODEL_KEYS)*len(CONDITIONS)
    return dict(status="READY_FOR_DEVELOPMENT_REVIEW" if successful == expected else "PARTIAL_MODEL_RESULTS",
        case_variants=len(public), source_groups=20, expected_model_requests=expected,
        successful_model_requests=successful, model_evaluation_complete=successful == expected,
        inference_errors_scored=True, protected_test_evaluated=False,
        next_action="Upload ZIP for Phase 2 development review; refine tasks before protected evaluation")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run", "collect"))
    parser.add_argument("--parent-zip", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT.parent/"results_phase2")
    parser.add_argument("--cache-dir", type=Path, default=ROOT.parent/"cache/llms_phase2")
    parser.add_argument("--config", type=Path, default=ROOT/"config/pilot.json")
    parser.add_argument("--model-key", choices=MODEL_KEYS)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", args.run_id):
        parser.error("Invalid run ID")
    output_root, cache = args.output_root.resolve(), args.cache_dir.resolve()
    if cache == output_root or output_root in cache.parents:
        parser.error("Model cache must be outside the results directory")
    out = output_root/args.run_id
    out.mkdir(parents=True, exist_ok=True)
    if args.mode == "prepare" and ((out/"stage_prepare.json").exists() or (out/"prepared_sha256.json").exists()):
        print("Preparation was already attempted. Start a new run ID to preserve frozen results.", file=sys.stderr)
        return 1
    code, stage_key = 0, args.model_key if args.mode == "run" else args.mode
    try:
        config = load_config(args.config)
        existing = out/"run_config.json"
        if existing.exists() and support.load_json(existing) != config:
            raise ValueError("Configuration changed for this run ID")
        if not existing.exists():
            support.save_json(existing, config)
        with (out/f"{stage_key}.log").open("a", encoding="utf-8") as log, \
             contextlib.redirect_stdout(support.Tee(sys.stdout, log)), contextlib.redirect_stderr(support.Tee(sys.stderr, log)):
            print(f"Phase 2 development diagnostic: {args.mode}, run={args.run_id}, model={args.model_key}", flush=True)
            if args.mode == "collect":
                result = collect(out, args.parent_zip, config)
            else:
                support.stage(out, stage_key, "RUNNING")
                if args.mode == "prepare":
                    result = prepare(out, cache, args.parent_zip, config)
                else:
                    if not args.model_key:
                        raise ValueError("run requires --model-key")
                    result = run(out, args.model_key, config)
    except Exception as exc:
        text = support.safe_text(traceback.format_exc())
        (out/f"{stage_key}_error.txt").write_text(text, encoding="utf-8")
        support.stage(out, stage_key, "FAILED", error=support.safe_text(exc))
        result = dict(status="FAILED", failed_stage=stage_key, error=support.safe_text(exc))
        print(text, file=sys.stderr)
        code = 1
    result.update(phase=2, checkpoint="development_diagnostic", phase2_complete=False, phase3_ready=False,
        run_id=args.run_id, all_systems_development=True, contains_model_weights=False, contains_credentials=False,
        limitation="20 correlated pilot groups; no confirmatory model ranking or unseen-chemistry claim")
    # Each stage has its own summary: sequential jobs cannot erase earlier failures.
    support.save_json(out/f"summary_{stage_key}.json", result)
    if args.mode != "run":
        support.save_json(out/"summary.json", result)
    if args.mode == "collect":
        try:
            support.archive(out, output_root)
        except Exception as exc:
            support.diagnostic_archive(out, output_root, exc)
            return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
