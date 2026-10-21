# Independent final case and scientific-validity review

**The case/gold audit passes. No material labeling, scope-mathematics, source-split or model-payload leakage defect was found. The final results support a narrow finding about evidence-definition validation and its coverage cost, rather than improved scientific understanding or a new verification algorithm.**

Input: `final_study_20261021T014441Z_2087139_1912_final_results.zip`. Only trusted local code was executed; uploaded programs were treated as data.

## Verification

All 69 member checksums pass. The trusted constructor exactly reproduces all 1,760 public cases, gold records and benchmark audit from the archived 110 source-pair records. Those source records exactly match the qualified Phase 3 pool. All 55 groups are disjoint from the 20 development groups; each retains 32 case variants, with no case skips or source replacements. The earlier 60-source qualification denominator remains a separate reporting requirement.

The labels are 550 supported, 550 contradicted and 660 insufficient, with 880 cases in each presentation. There are 880 base cases; variants are correlated and statistical inference must retain the source-group unit.

All model payloads omit original source identities, group/split metadata, family labels, gold labels and interval witnesses. Pair and evidence aliases are fresh, opaque and unique. Mathematical background and the definition of the reported scalar are explicit in both presentations.

The audit reproduces every valid proof, not merely the generator's preferred citation: 660 cases have no decisive proof, 918 have one, and 182 have two. All 1,282 permissible proofs are licensed: 660 direct-value witnesses, 310 adsorbate-upper-bound witnesses and 312 mobile-lower-bound witnesses. Every derived trace reconstructed from raw outputs matches the saved trace, and every full-definition acceptance matches a licensed gold proof.

## Mathematical soundness

For common shared-frame per-atom MIC residuals and equal atom weights, the subset sum-of-squares identity licenses the two supplied bounds. Every source has at least eight mobile atoms outside the adsorbate set, so these subsets are genuinely different. Missing-mobile ambiguous cases place the threshold strictly above the attainable lower bound, and missing-adsorbate ambiguous cases place it strictly between zero and the attainable upper bound. Thus neither inequality is settled by the remaining same-pair scalar.

Positive controls correctly establish claims from a bound despite the absence of the target scalar. Missing internal RMSD is paired only with an independent fixed-anchor value. No invalid internal-from-MIC-adsorbate bound is used. No unseen numerical cell or geometric constraint is assumed. These are controlled information-entailment questions, not claims about acceptable chemical error or physical simulation accuracy.

## What the full-definition guard adds beyond run identity

All selector methods reuse the same raw selected record and operation. The comparison therefore isolates the extra physical-definition validation from prompt variation.

| Model | Run-only numeric acceptances | Full-definition acceptances | Additional bad acceptances rejected | Correct numeric/proof answers retained |
|---|---:|---:|---:|---:|
| Qwen | 393 | 312 | 81 | 312 |
| Phi | 366 | 121 | 245 | 121 |
| SmolLM | 441 | 168 | 273 | 168 |

The additional rejections concern records for the **correct pair** but an unlicensed atom population, alignment/frame definition or operation. They are therefore not repetitions of the earlier wrong-run-only result. Qwen's 81 additional rejections comprise 60 answerable cases and 21 genuinely insufficient cases. Phi's split is 184 and 61; SmolLM's is 177 and 96.

This is filtering, not retrieval repair. Each full-definition method retains exactly the same correct numeric/proof answers as run-only. Qwen's answerable numeric coverage drops from 372/1,100 (33.8%) to 312/1,100 (28.4%). Full-definition accepted correctness is 100% under the declared proof system, while most answerable cases still do not receive a correct accepted answer. Its rejection is correctly kept separate from a scientific insufficient-evidence verdict.

Because the full checker and gold constructor share the same finite set of licensed mathematical rules, the checker's perfect accepted correctness is a structural guarantee on this task universe. The empirical findings are how often raw model selections violate those rules, which extra errors run-only validation misses, and how much answer coverage remains after validation. The deterministic payload oracle remains the 100% ceiling and must be reported.

## Qwen failure patterns and examples

Qwen's direct method returns the correct three-way label on 683/1,760 cases (38.8%), but only 306/1,760 (17.4%) have both the correct scientific verdict and a licensed proof where required. This difference includes correct-looking scalar comparisons attached to the wrong scientific quantity or operation.

- `fs_90b10f73ef813803264f5829`: the claim concerns aligned internal RMSD, but the selector chooses a same-pair unaligned adsorbate-frame scalar in nm and the `mobile_lower` operation. Run-only produces a supported verdict; the correct label is contradicted. Full-definition rejects the invalid relation.
- `fs_5e7eba82b910fcc99c10de81`: the correct label is supported, but the model uses a same-pair mobile-frame scalar and `mobile_lower` for an internal-shape target. The numerical verdict happens to be right; the witness is invalid. This illustrates why verdict accuracy alone is inadequate.
- `fs_f0131ede5cca0b4b9fe81469`: the requested adsorbate scalar is absent. A mobile scalar of approximately 1.10088 angstrom licenses an adsorbate upper bound, settling the claim at 3.19776 angstrom. The direct answer labels the claim correctly but declares `value`, which is not the correct witness operation. The selector chooses `adsorbate_upper`, and both run-only and full-definition accept the valid bound calculation.

The same-pair ambiguity controls are especially difficult: direct Qwen correctly declares insufficiency on only 2/220 missing-mobile ambiguous cases and 3/220 missing-adsorbate ambiguous cases. On positive bound controls, its scientific verdict-plus-proof counts are 16/220 for mobile lower bounds and 20/220 for adsorbate upper bounds. A policy that always rejects a missing scalar would therefore also fail valid positive controls.

Detailed payload claims, selected-record definitions, raw outputs and traces are retained in `examples.json`, with a complete machine-readable audit in `audit.json`.

## Presentation and execution limits

For Qwen, the full checker accepts 182 correct numeric/proof answers in structured form versus 130 in prose, each from 880 cases. Run-only accepts 192 and 201, respectively, so 71 of its 81 additional full-definition rejections occur in prose. This is consistent with greater definition/operation confusion after explicit metric names are removed. The condition changes both formatting and redundant quantity labels, so the effect should not be attributed solely to prose formatting.

All 10,560 planned requests have records; none is missing. SmolLM has 261 prespecified token-cap failures: 258 direct responses and three selector responses. They remain scored errors. They should not be retried with a larger cap after final-result inspection and then presented as the same frozen experiment. These are bounded-generation outcomes, not evidence of universal inability. The summary's `PARTIAL_FINAL_RESULTS` describes unsuccessful generations; it does not imply unattempted requests.

The sample remains 55 qualified groups from the same OC20 source domain and three small instruction models. It does not establish chemical-family independence, absence from model training, performance of current frontier assistants, a preregistered study, or a novel algorithm. The guarded selective method should not receive a three-way accuracy that counts its operational rejections as correct scientific insufficiency answers.

The bounded publishable contribution is an executable, coordinate-derived diagnostic with valid missing-measurement bounds, alternative proof-aware scoring, and a paired demonstration that run identity alone does not prevent physically misapplied measurements. Publication strength depends on positioning this carefully against prior verification and numerical-reasoning work. No tuning, rerunning, or case exclusions were performed for this review.
