# Phase 3: qualify new physical source systems

Phase 2 development has passed its review. This is the first checkpoint within Phase 3: prepare fresh atomic-coordinate evidence before the final language-model test. It creates no final claims, gold labels or model scores. Read `PHASE2_REVIEW.md` for the development findings and their limits.

## Run on Swan

Upload `geom_scope_phase3_prepare.zip` into the existing `geom_scope_phase1_uma` folder, alongside `phase2_pilot/` and `phase2_refine/`, then run:

```bash
unzip geom_scope_phase3_prepare.zip
bash phase3_prepare/start_phase3.sh
```

The launcher submits five jobs: CPU source selection, three sequential UMA GPU batches of 20 systems, and CPU analysis/collection. Only one GPU is requested at a time. Dependencies use `afterany`, so failed calculations can still be collected. The exact return path is printed. Return the ZIP from:

```text
results_phase3_prepare/return_zips/
```

Keep both reviewed parent ZIPs at their existing locations:

```text
results_phase2_refine/return_zips/phase2_refine_20261020T201951Z_3900908_15370_phase2_results.zip
results/return_zips/uma_phase1_cont_20261020T151825Z_1912433_9416_phase1_results.zip
```

The launcher accepts those two ZIP paths as optional first and second arguments; its third argument overrides the output root. Archive SHA256 pins prevent silently switching inputs. The working UMA environment at `.env` and cached UMA files are reused, with no installation or new model download. The pinned 13 MB official initial-coordinate archive is reused from `cache/oc20dense/`, or downloaded if absent. Neither LLM weights nor the LLM environment are used for inference here.

Each GPU batch requests one L40S, four CPUs, 32 GB host memory and up to four hours; preparation requests two hours and collection one hour. These are limits, not measured completion estimates. Allow a few GB of additional space for full trajectories and diagnostics. Results are bounded at 512 MiB uncompressed; a small diagnostic ZIP is returned if packaging exceeds that limit, with full files preserved on Swan.

## Frozen source-selection rules

Use the same pinned official OC20-Dense 2023 validation ASE archive (200 system groups). Exclude all 20 development group IDs before seeded selection. Select exactly 60 new groups, one initial placement per group, using seed 20261021 and existing geometry-only eligibility rules: no more than 180 atoms, at least three adsorbate atoms, explicit fixed atoms consistent with OC20 tags, and a connected initial distance-based graph for unwrapping. No convergence, energy or model-answer result influences initial selection. If 60 eligible groups cannot be found, return diagnostics rather than silently reducing or replacing the sample.

Before UMA runs, save every candidate's membership/hash, selected identities, exclusions, diversity inventory, inputs, configuration, code hashes and split manifest. Each selected system gets one bounded FIRE attempt of at most 600 steps with the same pinned UMA checkpoint, constraints and strict mobile-force threshold below 0.05 eV/angstrom. A nonconverged or failed system is retained; no automatic continuation, replacement or retrial is allowed. Valid finalized outcomes may be reused unchanged. A nonempty interrupted attempt or corrupted checkpoint is preserved and refused rather than overwritten.

All 60 selections remain in the outcome denominator. Only converged endpoints passing the declared atom mapping, fixed-mask, anchor-frame, finiteness and unchanged heuristic-graph checks produce measurement pairs. Compare the original OC20 initial coordinates with the UMA endpoint. A separate labelled control translates the final adsorbate by 0.7 angstrom and recomputes its geometry, with no inherited forces, energy or convergence claim. The return ZIP includes coordinates, force/optimization logs, trajectories, per-system outcomes, metric definitions, measurements and rejections for review.

These are new source-group IDs within the same dataset. This does not establish new chemical families, independence from UMA training data, DFT accuracy, valid chemisorption or global minima. The distance graph is an unwrapping hypothesis, not independently established bonding. Descriptive diversity is reported without reranking the sample.

## Final-test boundary and failure recovery

The source pool is labelled `protected_candidate`. This checkpoint never runs language models and does not automatically enable the final test. Geometry-only quality review may occur first; final task construction, labels, prompts, parser, checker, comparisons and splits must then be independently checked and frozen before model outputs are generated. Record any development based on the new metric values honestly; do not call such tuned cases an untouched confirmatory test.

The final study needs run-only and full-definition validation controls, same-comparison quantity mismatches, explicit treatment of mathematical bounds, and separate acceptance/coverage reporting. The current checker is a transparent engineering candidate; zero unsupported acceptance in the development templates is not a novel reasoning result. The three-phase project plan remains intact.

If a job fails, allow the collector to finish and return its diagnostic ZIP. If a scheduler submission fails midway, the launcher attempts a recovery collector dependent on all accepted jobs. If that submission is also rejected, it prints a manual recovery command. After jobs finish, you can also run:

```bash
bash phase3_prepare/collect_now.sh /full/path/to/results_phase3_prepare/RUN_ID
```

The recovery script checks that this run's compute/collector jobs are no longer active. Preserve the run directory and cache. Do not rerun interrupted UMA attempts to force a complete dataset; return the partial result for review.
