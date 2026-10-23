# GeoScope Phase 4 v1.7 — Four-model response token confidence

This is an additional confidence experiment with a predeclared scoring protocol. The original OC20 accuracy results are already known, so the confidence study is supplementary and not a new untouched holdout. It does not replace, tune, or revise the original Phase 4 v1.6 OC20 scientific experiment.

The earlier v1.6 results stored **only output strings and token counts**. They **did not store internal token probabilities**. This package repeats generation with `logprobs` enabled, comparing all outputs to immutable prior answers. No correct-answer labels or sealed proofs are supplied to the GPU.

All 1,536 public cases, all 6,144 previous output strings, and frozen hashes are embedded to support a standalone audit. The GPU reuses the already installed small/large model environments; no re-download needed. Do not train any model or adjust the prompt/seed/decoding settings.

Interpretation: high token probability is not equal to P(a scientifically sound answer). Evaluate per-model AUROC and selective accuracy first. Insufficient-evidence abstention is a separate outcome.

See `HPC_RUNBOOK.md`, `EXPERIMENT_PROTOCOL.md`, `hpc/analyze_confidence.py`.

## v1.7.1 startup repair
`hpc/check_environment.sh` no longer assumes every functioning installed Python runtime
reports `sys.prefix != sys.base_prefix`. The check still imports model loader libraries
through the exact v1.6-provided Python entrypoints and verifies the previously pinned
Transformers (small) and vLLM (large) versions. Both paths and both prefix values
are printed for diagnosis. No prompts, baselines, model runners, frozen hashes,
confidence definitions, or scientific scoring logic changed.

If the small and large Python environments already exist, **do not reinstall them**.
Install this ZIP over the existing folder, rerun `bash hpc/check_environment.sh`,
then proceed with the original submission commands.

## v1.7.2 test compatibility fix
On Swan, `/usr/bin/python3` may not provide `importlib.metadata`, which caused
`tests/test_environment_gate.py` to fail on Python 3.9. The regression test
now uses the same Python executable as the unit-test runner and simulates
`sys.prefix == sys.base_prefix` in a temporary wrapper. The production
`hpc/check_environment.sh` and all inference/scoring files are unchanged.
No reinstall or checkpoint download is required.


### v1.7.3 additive HPC recovery

Only the Qwen-32B pilot/remainder job submission and `Python.h` compiler preflight were added. The 3 completed small models, token scoring, frozen inputs, and original Qwen3-32B inference code are unchanged. See HPC_RUNBOOK.md. A successful Python import is not proof the CUDA compiler can find Python development headers.

### v1.7.4 repair: SLURM sourcing helper path

The previous pilot stopped with `hpc/require_python312_headers.sh: No such file or directory` even though that file was included in the ZIP. The `check_environment.sh` helper accidentally used the copied SLURM script's `$0` path while being sourced, changing its working directory. v1.7.4 repairs `BASH_SOURCE[0]` handling and uses absolute helper paths. The actual Python.h compiler check has **not yet run on Swan**; do not submit the remainder until a pilot succeeds. No scientific definitions or GPU model code were changed.
