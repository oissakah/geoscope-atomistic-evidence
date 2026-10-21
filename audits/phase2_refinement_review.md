# Phase 2 refinement review: development complete

Reviewed 20 October 2026. Run `phase2_refine_20261020T201951Z_3900908_15370`.

**Phase 2 passes its development gate. We can proceed to Phase 3 source qualification while preserving the current results and freezing a narrow candidate for final evaluation.** This does not establish a new scientific-reasoning algorithm or a publishable performance claim by itself.

All 69 member checksums, seven prepared-input hashes, 22 delivered source hashes, three run signatures and 2,880 request signatures independently verify. Every model completed 960 independent requests with no missing or duplicate requests, failed generation, overlength input or truncation. The exact cached model manifests and pinned software were reused. Cases, gold labels, audit metadata and coordinate-derived measurements are unchanged from the first Phase 2 run. Independent reconstruction reproduces all 4,800 derived/scored records and every reported evaluation field exactly. Archived programs were read as data and were not executed.

Scores below use all 320 expected cases per method. Joint correctness requires the verdict and exact required evidence. Markdown-fence handling and minimal-citation rules were specified before this run.

| Model | Direct joint | Selection + calculation joint | Selection + checking joint | Answerable cases rejected by check |
|---|---:|---:|---:|---:|
| Qwen | 192/320 (60.00%) | 206/320 (64.38%) | 258/320 (80.63%) | 62/240 (25.83%) |
| Phi | 81/320 (25.31%) | 119/320 (37.19%) | 198/320 (61.88%) | 120/240 (50.00%) |
| SmolLM | 61/320 (19.06%) | 115/320 (35.94%) | 195/320 (60.94%) | 124/240 (51.67%) |

Qwen direct verdict accuracy is 221/320 (69.06%); the checklist scores 207/320 (64.69%) for verdicts and 177/320 (55.31%) jointly. The checklist is not the preferred candidate here. Phi direct frequently abstains on answerable cases, while SmolLM direct accepts 188 of 200 unsupported claims. Invalid output contracts and invented IDs remain scored errors; successful generation is not the same as a valid answer.

The cleaner causal comparison uses the same selector output with and without checking. Qwen gains 52 joint-correct decisions, Phi 79 and SmolLM 80. **Every one of those gains occurs on a truly insufficient packet, where the selected record belongs to another comparison.** Decisive-case joint correctness is unchanged: 178/240 for Qwen, 119/240 for Phi and 115/240 for SmolLM. We have not yet shown that validating physical definitions adds joint accuracy beyond checking the run/comparison ID.

Qwen's checker rejects 53 selections from another comparison and 61 selections with the wrong physical definition within the requested comparison. Of the total 114 rejected selections, 52 concern truly insufficient packets and 62 concern answerable packets. The checker never finds a replacement measurement. Its accepted numerical decisions cover 178/240 answerable cases (74.17%), or 178/320 of all cases (55.63%). The 80.63% aggregate joint score also credits correct insufficiency outputs; it must not be presented as 80.63% coverage of verified numerical answers.

The checker reduces unsupported acceptance to zero on this pilot. This follows from exact definition matching and deterministic arithmetic under the generated task assumptions. It is not evidence that the model learned physics. The fully deterministic scope selector solves every case without the language model and remains the strongest control at 320/320. The structure-only and first-number controls score 62.5% and 48.75% for verdicts. Retain these baselines in the final report.

Presentation remains the main weakness. Qwen's checked joint accuracy is 154/160 (96.25%) for structured inputs but 104/160 (65.00%) for reports. On answerable cases only, these become 114/120 (95.00%) and 64/120 (53.33%). The checker cannot repair a wrong selection. These are fixed generated presentations, so the difference does not establish a general result about scientific prose.

Exploratory 1,000-sample whole-source-group bootstrap intervals are 76.88–84.06% for Qwen's checked joint score and +13.44 to +19.06 percentage points for its paired joint improvement over calculation alone. The sample has 20 correlated development groups, five adsorbate formulas and synthetic controls; intervals are unadjusted for multiple comparisons. They are not confirmatory estimates on unseen chemistry. Changes from the first Phase 2 run also include new instructions and scoring conventions, so cross-run improvement cannot be attributed solely to checking.

Freeze Qwen evidence selection as the primary candidate; retain direct answering, calculation alone, run-only checking, complete definition checking and the deterministic selector as final controls. Keep Phi and SmolLM as secondary model-family comparisons if resources permit. Final evaluation should distinguish a rejected selection from a scientific conclusion that the full evidence packet is insufficient, and report acceptance, correctness and coverage separately.

Phase 3 begins with a frozen geometry-only source-selection protocol: 60 new OC20-Dense system groups, excluding all 20 development groups before sampling. All selected outcomes remain in the reporting denominator, including nonconvergence and interruption, with no replacement or extension beyond the declared 600-step cap. This is candidate physical-source qualification, not the final model test. It creates no claim cases, gold labels or language-model outputs. Review their raw coordinate evidence before constructing and freezing the final benchmark.

The final benchmark must isolate same-comparison definition mismatches from wrong-comparison mismatches, distinguish genuine missing values from mathematically valid bounds, and report structured and prose tasks separately. Those changes require mathematical and independent label checks before model scoring. Final cases/prompts/parsers/checkers and primary comparisons must be frozen before any protected model outputs are viewed. Geometry-based exclusions must follow the declared criteria without model-outcome-based selection; task tuning using candidate metric values must be disclosed as further development rather than called confirmatory testing.

The three phases remain unchanged: Phase 1 evidence pilot is complete; Phase 2 development is complete; Phase 3 covers new physical sources, the final frozen evaluation and publication artifacts. The prospective contribution is a reproducible geometric-evidence diagnostic and a measured validation-versus-coverage tradeoff. Broad novelty, DFT accuracy, catalyst quality and unseen-chemical-family generalization remain unestablished.

Reviewed archive SHA256: `8e8e77cc36b6f1dde2ab282bfb4f79f5c00d9f5333eff0fc0d9e593781727b86`.
