# Final review: physical-definition checking for atomistic evidence

Reviewed on 21 October 2026. Run: `final_study_20261021T014441Z_2087139_1912`.

The planned computational experiment is complete and its results reproduce exactly. Full-definition checking removes invalid evidence-based answers beyond checking the comparison ID alone. It retains the same valid answers, rather than solving additional cases. The low fraction of answerable cases accepted remains the main practical limitation.

## Completion and integrity

All 10,560 requests were attempted and saved exactly once: three models, two independent request conditions, and 1,760 cases. No request is missing or duplicated, and no execution error was recorded. All three GPU jobs exited successfully.

The original ZIP has SHA256 `20e6b415c0ab6b3d239138664301d5da1567c052d6770afa63e4c023a89c8b26`. All 69 member checksums, ten frozen-input hashes and 22 delivered-source hashes pass. The reserved model manifests, frozen protocol, three run signatures and 10,560 request signatures also pass. No archived code was executed during review.

Every field in the reported evaluation reproduces from the raw predictions using the trusted local scorer. The method, completeness and per-case CSV reports match the independent recomputation. The 1,760 public cases, gold proofs and benchmark audit reproduce exactly from the accepted source measurements. All 55 evaluation groups are disjoint from the 20 development groups.

The automated status is `PARTIAL_FINAL_RESULTS` because 261 SmolLM outputs reached the fixed 160-token output cap: 258 direct responses and three evidence selections. Qwen and Phi had no truncations. The collector counts 10,299 untruncated responses as successful. All 10,560 first attempts remain in the analysis. These are protocol outcomes, not missing jobs, so no continuation or rerun is required. The original automated summary has not been changed.

## What was tested

The source pool contained 60 OC20-Dense systems relaxed with the pinned UMA checkpoint. Fifty-eight converged, and 55 met the frozen intact-adsorbate geometry criteria. Two runs failed convergence and three changed the molecular graph. The original denominator and all five exclusions remain recorded.

Each qualified source contributes 16 base cases, rendered as structured data and prose, for 32 variants per group. There are 550 supported, 550 contradicted and 660 insufficient cases. The 55 synthetic translation controls supply other-comparison distractors; they are not additional independent physical systems or DFT relaxations.

Claims concern mobile-atom RMSD, adsorbate RMSD in the stored frame, or internal adsorbate RMSD after unwrapping and rigid alignment. The cases include direct measurements, unit conversion, valid subset bounds, unresolved bounds, fixed-anchor distractors and wrong-comparison evidence. All generic permitted mathematical relations are supplied. The task tests evidence/operation selection and entailment under explicit definitions, rather than discovery of an unknown physical law.

For each model, one request directly returns a verdict and proof; a separate request selects a measurement and operation. The same selection then feeds arithmetic-only, run-ID and full-definition checks. Full checking validates the atom set, frame, alignment, periodic treatment, weighting and mathematical relation. It never searches for a replacement measurement. Workflow rejection is kept separate from scientific insufficiency.

## Primary result: Qwen, full checking versus run-ID checking

Qwen was the development-selected primary model. The primary comparison uses identical raw selections, isolating the additional validation step.

| Outcome | Run-ID check | Full-definition check |
|---|---:|---:|
| Numerical answers accepted, all 1,760 cases | 393 | 312 |
| Correct accepted answers with a valid proof | 312 | 312 |
| Accepted answers with an incorrect verdict | 42 | 0 |
| Correct-looking verdicts with an invalid proof | 39 | 0 |
| Numerical answers accepted on 1,100 answerable cases | 372 (33.82%) | 312 (28.36%) |
| Numerical answers accepted on 660 insufficient cases | 21 | 0 |

Full checking rejects 81 additional bad acceptances: 42 incorrect verdicts and 39 coincidentally correct verdicts supported by an invalid measurement or operation. These are same-comparison physical-definition or operation errors, so the effect goes beyond ordinary comparison-ID checking.

Of the 81 rejected acceptances, 60 occur on answerable cases and 21 on insufficient cases. None of the 312 correct, licensed answers is lost. Nevertheless, answerable-case acceptance falls by 60/1,100, or 5.45 percentage points. The verifier does not recover a correct proof for those rejected answerable cases.

Across all 1,760 cases, the prevented bad-acceptance rate is 4.60 percentage points (95% source-group bootstrap interval 3.58–5.57). The answerable-coverage cost is 5.45 percentage points (4.09–6.91). Full-check coverage is 28.36% (25.73–31.00). These intervals resample all 55 source groups, retaining their correlated variants, using 1,000 resamples. They are descriptive percentile intervals, not multiplicity-adjusted confirmatory tests.

## Secondary models and deterministic baseline

| Model | Full-check valid numerical answers / 1,100 answerable | Bad acceptances rejected beyond run-ID checks | Additional answerable acceptances rejected | Correct licensed answers lost |
|---|---:|---:|---:|---:|
| Qwen3-4B-Instruct-2507 | 312 (28.36%) | 81 | 60 | 0 |
| Phi-4-mini-instruct | 121 (11.00%) | 245 | 184 | 0 |
| SmolLM3-3B | 168 (15.27%) | 273 | 177 | 0 |

All full-check accepted answers are licensed and correct. That conditional result follows the formal interval/proof construction in this restricted task family. It must not be described as 100% overall model accuracy or a novel learned-reasoning capability.

The transparent public-payload deterministic oracle solves all 1,760 cases, including all 1,100 decisive claims and all 660 insufficient claims. It remains a mandatory strong baseline. The proposed contribution is a controlled benchmark and an empirical account of selection failures and verification costs, not a superior solver for these templates.

## Direct answers, format failures and representation

| Model | Direct three-way verdict accuracy | Direct verdict plus licensed-proof accuracy | Format-valid direct outputs / 1,760 |
|---|---:|---:|---:|
| Qwen | 38.81% | 17.39% | 1,757 |
| Phi | 32.56% | 23.01% | 1,682 |
| SmolLM | 20.45% | 3.75% | 1,106 |

Qwen's direct responses accept numerical answers on 1,096/1,100 answerable cases, but only 255 carry a correct verdict and valid proof. It also accepts numerical answers on 607/660 insufficient cases. Thus valid JSON and willingness to answer do not establish reliable evidence use. The direct and selection conditions use separate requests; their differences are exploratory rather than an isolated causal effect of the checker.

For metric context, a constant insufficiency response would score 660/1,760 = 37.5% on three-way accuracy while answering zero numerical cases. This arithmetic reference, noted after review, illustrates why aggregate accuracy cannot replace coverage and proof-validity reporting. It does not change the frozen scoring or add a new model condition.

Every Phi direct response used an enclosing JSON fence. The frozen parser already permits one whole-output fence, so those wrappers were accepted. Remaining invalid responses include excess citations, incompatible operation/selection combinations, unknown operation names or extra prose. Truncated outputs and forbidden trailing text were not repaired or salvaged.

Qwen full-check valid-answer coverage is 33.09% for structured inputs and 23.64% for report inputs. Both presentations are answered with valid proofs in only 44/550 answerable pairs (8.00%). Both members of a supported/contradicted contrast are solved in 57/550 pairs (10.36%). These are exploratory diagnostics. Report rendering also removes redundant metric names; the observed difference cannot be attributed solely to prose formatting.

## Contribution and limits

The usable finding is that a correct run identity is insufficient for validating a scientific number. In this benchmark, checking the physical definition rejects real additional errors. The remaining bottleneck is selecting a compatible, conclusive measurement and operation. The formal checker filters failures; it does not repair that selection.

Only three compact open-weight models were tested under one fixed greedy, no-extended-thinking protocol. Long exact numerical strings, explicit proof conventions, alias identifiers and strict response rules contribute to task difficulty. The results do not establish how all LLMs, larger models, alternate prompts or longer inference budgets would perform.

There are 55 new same-domain source groups, not 1,760 independent physical experiments. Geometry was reviewed before frozen model inference. The protocol was fixed after development and was not externally preregistered. Development results and protected final results must be reported separately. Disjoint group IDs do not establish new chemical families or independence from UMA training data.

All five excluded systems have formula C2H3O2, and the two largest accepted formulas account for 38/55 groups. Sixteen accepted systems retain descriptive close-contact or weak/remote-contact flags. Geometry consistency, force convergence and RMSD validity do not establish DFT accuracy, chemisorption, catalytic activity or a global energy minimum.

No first-ever claim is warranted. Scientific context understanding, information-absence detection, tool use and templated reasoning already have substantial related work. The proposed narrow distinction is a physically grounded RMSD evidence/proof benchmark with a same-selection comparison of run identity and full definition checks. A focused literature comparison is provided in `PUBLICATION_AND_CV.md`.

## Completion decision

Phase 1 established and audited the physical measurements. Phase 2 developed and revised the task and scoring using the development groups. Phase 3 qualified new groups, froze the protocol, recorded every planned first attempt, and completed independent integrity and scoring review.

The planned computational work is complete. The package supplies the reproducible analysis and figures for a research-project release and manuscript preparation. Public deposition and journal submission have not occurred. Any future improved method should be evaluated as a separate study, with fresh evaluation data rather than tuned scores on this inspected test set.
