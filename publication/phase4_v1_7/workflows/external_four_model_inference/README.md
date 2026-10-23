# GeoScope Phase 4 v1.6 — external OC20 4-model inference

This package stages exactly the **1,536 frozen public-only requests** from the completed OC20 external IS2RE/IS2RS source gate. It makes no new benchmark labels or definitions and uses the same pinned Qwen3-4B-Instruct-2507, Phi-4-mini-instruct, SmolLM3-3B, and Qwen3-32B-AWQ checkpoints as Phase 4 v1.2–v1.4.

**Science remains frozen.** We are repeating model inference on a separately sourced dataset, not changing what is considered a scientifically correct proof. The external source contains 48 atomic systems and 48 clearly labelled synthetic distractors. The deterministic proof engine will be evaluated separately after all four models finish.

The original gold is not included with this package; only a hash of its sealed file is included. The post-run collector can access the gold only in `GeoScope_Phase4_v1_5_OC20_external_gate/outputs/external_oc20_benchmark/SEAL_OFFLINE` and will verify its hash before archiving it for offline scoring.

**First run `bash hpc/prepare_external.sh`**. For the three small models run `bash hpc/submit_small.sh`. For Qwen 32B run `bash hpc/submit_large.sh`. Both submitters run their model-specific tokenizer preflight, fail closed on missing original environments/weights, and submit to `ock` only.

**No weights are downloaded or retrained.** Both original model environments remain unchanged. This package never writes into the original v1.5 project, original GitHub repository, or manuscript.

## v1.6.1 supplementary hotfix
The v1.6.0 Qwen3-32B GPU job failed before loading weights: `ModuleNotFoundError: No module named 'transformers'`. The 32B preflight wrote `Path(py).resolve()` into `outputs/large_environment.sh`. The virtualenv executable is a symlink; resolving it substituted the system Python, which lacks the model's packages. This release preserves the virtualenv Python path via `Path(py).absolute()` and checks the interpreter and imports on the compute node before inference. No scientific methods, prompts, shards, model checkpoint, generation parameters, or frozen output scoring are changed. Previously completed small-model predictions remain intact.
