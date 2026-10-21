# Final new-system model evaluation

The new physical-source review accepts 55 of the original 60 systems and their 55 translation controls. Two runs did not converge within 600 steps and three changed the initial molecular graph; all five exclusions remain recorded. No additional UMA calculations or replacement systems are needed. `SOURCE_REVIEW.md` records the full audit and chemical interpretation limits.

## Run once on Swan

Upload `geom_scope_phase3_final.zip` into the existing `geom_scope_phase1_uma` folder, alongside the previous phase folders, then run:

```bash
unzip geom_scope_phase3_final.zip
bash phase3_final/start_final.sh
```

Keep these reviewed input ZIPs in their existing locations:

```text
results_phase3_prepare/return_zips/phase3_prepare_20261020T211054Z_234814_30462_phase3_prepare_results.zip
results_phase2_refine/return_zips/phase2_refine_20261020T201951Z_3900908_15370_phase2_results.zip
```

The launcher accepts those source/development paths as its first two optional arguments; a third overrides the output root. `GEOMSCOPE_FINAL_CACHE` can record an external cache location. The actual model files are taken from the reviewed reserved manifest, not resolved from a changing Hub branch.

Five sequential jobs prepare/freeze the cases, run Qwen, Phi and SmolLM, then collect results. Only one GPU is requested at a time. Return the ZIP printed by the launcher from:

```text
results_phase3_final/return_zips/
```

This reuses `phase2_pilot/.env` and the exact existing model checkpoints. It installs nothing, downloads no weights and runs no UMA. Preparation/collection request two hours/one hour; each model requests one L40S, four CPUs, 32 GB host memory and at most four hours. Those are scheduler limits, not measured runtime estimates. Allow several GB for logs and outputs. The returned archive is bounded at 512 MiB uncompressed and excludes model weights and environments.

Run this final protocol once and return its outputs even if partial. Missing, malformed, duplicate, truncated and failed responses remain in the denominator. Do not change prompts or scoring after viewing results or start repeated runs to choose a favorable score. If a job fails, the collector still runs through `afterany`. If submission fails, the launcher attempts a recovery collector; if that is also rejected, it prints a command using `collect_now.sh`. Recovery checks that the recorded compute/collector jobs have finished before collecting. Existing final preparations are never overwritten.

## What the final study tests

There are 880 base cases shown in structured and prose forms: 1,760 variants from 55 new source groups. Labels are 550 supported, 550 contradicted and 660 insufficient. These are correlated reasoning cases, not 1,760 independent physical calculations. All 20 development groups are excluded. No new source groups, placements or chemical flags are substituted after qualification.

The revised constructor was checked on the original 20 development groups first. It includes direct-value comparisons, unit conversion, missing mobile/adsorbate measurements with valid subset bounds, genuinely unresolved bounds, internal-shape claims with only fixed-anchor evidence, and wrong-comparison distractors. Relations and conventions are stated in every request. No rule incorrectly bounds rigid-aligned internal shape by a per-atom minimum-image frame displacement.

Every model makes two independent requests per case: direct verdict/proof and measurement/operation selection. That is 3,520 requests per model, 10,560 total. Requests contain only the claim and supplied measurements; labels, groups, provenance, synthetic-control descriptions and previous answers are withheld. Evidence IDs are short neutral aliases. All valid single-record proofs are enumerated, so a valid alternative citation is accepted.

The same selected record and operation feed three controls:

- `arithmetic_only`: perform the chosen operation and comparison without checking comparison identity or physical definition.
- `run_only`: additionally require the correct endpoint-pair identity.
- `full_definition`: additionally require the requested atom set, frame, alignment, periodic convention, equal weights and a licensed exact-value/subset-bound relationship.

An unresolved bound or invalid selected record leads to an operational rejection, not a scientific `INSUFFICIENT_EVIDENCE` verdict. The check never searches for a replacement. We report numerical correctness, proof validity, acceptance and answerable-case coverage separately. The primary comparison asks what full definition checking prevents and what coverage it loses relative to run-ID checking on identical selections. This isolates physical-definition validation from ordinary provenance checking. Qwen is the primary development-selected model; Phi and SmolLM are secondary comparisons.

The payload-only deterministic interval oracle remains a mandatory strong baseline and solves this explicitly specified task family. Full validation plus deterministic arithmetic can enforce safety by construction here. Neither that guarantee nor a high score establishes a new reasoning algorithm. The empirical question concerns evidence/operation selection failures and the verification-versus-coverage tradeoff on new source systems.

## Freeze and interpretation

`PROTOCOL.md` specifies the mathematical and scoring rules. Preparation verifies all parent checksums, the accepted cohort, unchanged model manifests, unit tests, development regression and final oracle agreement, then hashes the code, cases, gold proofs, protocol, settings and model files before any model job. GPU jobs refuse changed inputs. Raw outputs, prompt hashes, input-token hashes, failures and all derived decisions are retained.

The return ZIP contains per-case traces, `method_scores.csv`, `completeness.csv`, full evaluation JSON, paired comparisons with source-group intervals, frozen inputs and logs. Scientific three-way accuracy is reported for direct answers and the oracle only; checker rejections receive no automatic scientific-insufficiency credit. A completely missing model can have zero unsafe acceptances simply because it answered nothing, so always inspect completeness, coverage and correct accepted answers together.

This is the first frozen model evaluation on these source groups after geometry-only quality review. It is not an externally preregistered study, a test of new chemical families, or proof of independence from UMA training data. All five source exclusions involve C2H3O2; 16 accepted systems retain descriptive close-contact or weak/remote-contact flags. Preserve these limitations, the original 60-source denominator and the deterministic baseline in any publication or CV description.

After the ZIP is reviewed, the remaining work within Phase 3 is final interpretation and preparation of the reproducible release, figures and manuscript/CV wording. Publication novelty depends on the bounded evidence and comparison with prior work, not an assumed improvement over an already-perfect deterministic oracle.
