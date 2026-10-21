# Phase 2: development comparison of language models

Phase 1 passed its pilot gate: all 20 selected structures converged and the geometric evidence and corrected labels were independently checked. This package uses that frozen evidence. It does not run UMA again.

## Run on Swan

Upload `geom_scope_phase2_pilot.zip` into the existing `geom_scope_phase1_uma` folder. Keep the reviewed continuation ZIP at its existing location in `results/return_zips/`, then run:

```bash
unzip geom_scope_phase2_pilot.zip
bash phase2_pilot/start_phase2.sh
```

One launcher submits five sequential jobs: CPU setup/data preparation/model download, Qwen GPU evaluation, Phi GPU evaluation, SmolLM GPU evaluation, and CPU collection. It prints all five IDs and the final ZIP path. Only one GPU is requested at a time. Model jobs and collection use `afterany` dependencies so failures remain collectable.

Upload the new results ZIP from:

```text
results_phase2/return_zips/phase2_pilot_RUNID_phase2_results.zip
```

The exact name is printed by the launcher and collector. It contains frozen cases and gold labels, raw model outputs, software/model/prompt hashes, per-case and summary scores, logs and diagnostics. Model weights and the environment remain on Swan. A partial ZIP is useful for review; it is not a completed evaluation.

This uses a separate environment at `phase2_pilot/.env`; the existing UMA environment supplies a known-working standard-library Python for diagnostic collection. The first download needs roughly 22 GB of model weights, plus several GB for software/cache. Allow at least about 35 GB of additional storage and check your account quota. Public models normally need no new access approval; preparation uses any existing Hugging Face authentication implicitly. Never put tokens in files or returned logs.

The CPU preparation job requests two hours. Each GPU job requests one L40S, four CPUs, 32 GB host memory and at most four hours. The collector requests one hour. These are scheduler limits, not measured runtime estimates. The first model batch checks actual loading/generation. Native Slurm execution, full downloads and these model runs still require Swan validation.

The launcher accepts an unchanged parent-ZIP path as its first argument and output directory as its second. `GEOMSCOPE_P2_MODEL_CACHE` can point to a shared model cache outside the results directory. Use a fresh run ID through the launcher for every new preparation. Preserve the original parent ZIP: its SHA256 is pinned, so a newly regenerated archive with different bytes requires review rather than silently changing evidence.

## What is evaluated

There are 160 base development cases from 20 source groups, each shown in structured and prose form: 320 variants. For each metric, controlled positive bounds at 0.75 and 1.25 times its measured value balance supported and contradicted claims; at-most and at-least comparators are counterbalanced. These are reasoning-task thresholds, not chemical accuracy tolerances. Claims remain a safe distance from their decision boundaries.

Each answerable packet includes the matching measurement plus same-unit, differently scoped or differently referenced distractors. Atom-set definitions remain explicit. In the prose presentation, measurement names and semantic field IDs are removed; definitions convey the quantity. Evidence order is shuffled deterministically. Both presentations preserve the same numerical facts and truth labels.

Missing-measurement controls remove every geometric value for the requested comparison while retaining definitions and unrelated-comparison distractors. Wrong-run controls supply only measurements for another neutral comparison ID. There is no assumption that merely removing one field makes a claim undecidable: related RMSDs can otherwise imply valid bounds.

The 320 variants contain 120 supported, 120 contradicted and 80 insufficient labels. All source IDs, transformations, class/family labels, expected answers and grouping information stay outside `model_payload`. Every request is independent, with no shared conversation history. Only `model_payload` and one fixed instruction are sent to a model.

## Models and controls

- [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507): a 4B non-thinking instruction model.
- [Phi-4-mini-instruct](https://huggingface.co/microsoft/Phi-4-mini-instruct): a 3.8B instruction model.
- [SmolLM3-3B](https://huggingface.co/HuggingFaceTB/SmolLM3-3B): a 3B model with extended thinking disabled for this controlled run.

Preparation freezes full model commit SHAs and hashes for native tokenizer/configuration/safetensors files. GPU jobs load only those local files with remote code disabled. Models use BF16 where supported, greedy decoding, a 160-token output cap and batch size two. Software is pinned to Python 3.12, PyTorch 2.13.0 CUDA 12.6, Transformers 5.3.0, Accelerate 1.12.0 and NumPy 2.3.5. The SmolLM chat-template date is frozen so prompts do not change across midnight.

Each model receives the same cases under two fixed prompts: a neutral assessment and an explicit scope checklist. This is 640 requests per model, 1,920 total. Input exceeding 6,144 tokens produces a visible error rather than silent truncation. Raw outputs, malformed JSON, truncation and generation failures are retained; there is no automatic answer repair or retry.

The payload-only scope checker is a transparent control, not a demonstrated novel method. It must match every gold label and required citation before model downloads proceed. On these actual frozen measurements it scores 320/320; the first-number/unit baseline scores 156/320 and the structure-only baseline scores 200/320. A model that merely matches this engineered template control has not established a new scientific-reasoning capability.

## Scoring and the review gate

Responses must be one JSON object with exactly `verdict` and `evidence_ids`. Strict accuracy includes all expected cases; missing, malformed, failed or duplicate responses count as errors. Citation correctness, joint correctness, unsupported acceptance, excess abstention, macro F1 and completeness are reported separately. Paired threshold contrasts and structured/prose invariance are measured. Exploratory intervals resample whole source-system groups, keeping correlated variants together.

This is Phase 2's development checkpoint. All 20 systems remain development data. The next review will decide whether failures concern measurement scope, arithmetic, wording or output formatting, and whether the task needs further refinement. We will then freeze the method/protocol and prepare new protected system groups for the final Phase 3 test. This package does not evaluate a protected test set and never automatically authorizes Phase 3.

If setup or inference fails, let collection finish and return the diagnostic ZIP. The original Phase 1 Python environment lets the collector operate even if the new installation is incomplete. If Slurm submission itself fails, return the printed error and `phase2_pilot/logs/`.
