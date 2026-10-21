# Frozen final evaluation: independent scoring review

Run: `final_study_20261021T014441Z_2087139_1912`.

The final output data are interpretable under the frozen protocol. Every expected request has a unique saved response record. The automated `PARTIAL_FINAL_RESULTS` status reflects 261 capped Smol outputs, rather than missing jobs or unattempted examples. Retain those failures in all denominators and preserve the original archive. The evidence supports a selective safety-versus-coverage result, with substantial limitations in the underlying models; it does not support an 80% general scientific-reasoning claim.

No uploaded code was executed. The raw public cases, gold records and predictions were read as data and scored using the trusted local evaluator. The local evaluator, benchmark, models and protocol files are byte-identical to their archived snapshots. Every field of `evaluation.json` matches the independent recomputation exactly. `method_scores.csv`, `case_scores.csv` and `completeness.csv` are byte-identical to independently written reports. `paired_comparisons.json` is semantically identical; its byte difference is only Linux versus Windows line endings.

## Completion versus output failures

- All 10,560 expected raw request records are present and unique: three models × two conditions × 1,760 case variants.
- No case is missing, duplicated or associated with an execution error. Collection warnings are empty.
- Qwen and Phi each return all 3,520 requests with status `ok`.
- Smol returns 3,259 `ok` records and 261 `truncated` records: 258/1,760 direct responses and 3/1,760 selectors reach the frozen 160-token output cap. None of these truncated outputs satisfies the exact schema even if its status is ignored.
- The 1,760 variants derive from 880 base cases and 55 source-system groups. There are 1,100 answerable cases and 660 scientifically insufficient cases. Original physical qualification retains its denominator of 60 selected systems, including five exclusions.

| Model | Direct contract valid | Selector contract valid | Truncated direct / selector |
|---|---:|---:|---:|
| Qwen | 1,757/1,760 (99.83%) | 1,670/1,760 (94.89%) | 0 / 0 |
| Phi | 1,682/1,760 (95.57%) | 1,638/1,760 (93.07%) | 0 / 0 |
| Smol | 1,106/1,760 (62.84%) | 1,447/1,760 (82.22%) | 258 / 3 |

Qwen's contract failures are inconsistent empty selections and `none` operations: three direct and 90 selector outputs. Phi's direct failures comprise 69 invalid/multiple citation arrays and nine empty-selection/operation inconsistencies; selectors have 65 invalid arrays and 57 such inconsistencies. Smol direct outputs include trailing prose, non-JSON material, unknown operations and invalid arrays, in addition to truncation. Its selectors chiefly violate the maximum-one-ID requirement. The frozen parser already handles one entire-output JSON fence, including inline closing fences; fence-only sensitivity or output repair is neither needed nor applied here.

The largest observed input is 3,089 tokens, below the 6,144-token input limit. These are output-compliance and reasoning failures, not evidence of input truncation. Some contract failures are themselves evidence-selection mistakes, so they should not all be described as cosmetic formatting failures.

## Direct answers expose poor scope reasoning

Numeric coverage means that the workflow accepts a numerical verdict. Correctness with proof requires both the correct verdict and any permissible evidence-ID/operation witness. Mere numerical agreement using an unlicensed measurement does not count as a correct proved answer.

| Model | Direct numeric coverage on 1,100 answerable cases | Correct verdict + proof on answerable cases | Numeric answers on 660 insufficient cases |
|---|---:|---:|---:|
| Qwen | 1,096/1,100 (99.64%) | 255/1,100 (23.18%) | 607/660 (91.97%) |
| Phi | 356/1,100 (32.36%) | 26/1,100 (2.36%) | 250/660 (37.88%) |
| Smol | 722/1,100 (65.64%) | 66/1,100 (6.00%) | 380/660 (57.58%) |

Among all accepted direct numerical answers, only 255/1,703 Qwen answers (14.97%), 26/606 Phi answers (4.29%) and 66/1,102 Smol answers (5.99%) have the correct verdict and licensed proof. These figures include the scientifically insufficient cases that should not receive numerical answers.

Direct scientific three-way label accuracy is 683/1,760 (38.81%) for Qwen, 573/1,760 (32.56%) for Phi and 360/1,760 (20.45%) for Smol. Requiring a licensed proof for decisive answers gives 306/1,760 (17.39%), 405/1,760 (23.01%) and 66/1,760 (3.75%), respectively. Phi's larger latter number comes largely from correct scientific insufficiency answers, not successful answerable-case proof construction. Aggregate scores alone therefore obscure important behavior.

## Selective methods: safety and coverage

All three methods below use the same raw selector response for each case. The arithmetic control ignores both run identity and definition binding; `run_only` checks run identity; `full_definition` checks both. Operational rejection receives no scientific-insufficiency credit.

| Model | Method | Answerable numeric coverage | Correct verdict + proof / 1,100 | Bad numerical acceptances / all accepted | Numeric acceptances on insufficient cases |
|---|---|---:|---:|---:|---:|
| Qwen | Arithmetic only | 478/1,100 (43.45%) | 312 (28.36%) | 365/677 | 199/660 |
| Qwen | Run only | 372/1,100 (33.82%) | 312 (28.36%) | 81/393 | 21/660 |
| Qwen | Full definition | 312/1,100 (28.36%) | 312 (28.36%) | 0/312 | 0/660 |
| Phi | Arithmetic only | 494/1,100 (44.91%) | 121 (11.00%) | 647/768 | 274/660 |
| Phi | Run only | 305/1,100 (27.73%) | 121 (11.00%) | 245/366 | 61/660 |
| Phi | Full definition | 121/1,100 (11.00%) | 121 (11.00%) | 0/121 | 0/660 |
| Smol | Arithmetic only | 720/1,100 (65.45%) | 168 (15.27%) | 1,005/1,173 | 453/660 |
| Smol | Run only | 345/1,100 (31.36%) | 168 (15.27%) | 273/441 | 96/660 |
| Smol | Full definition | 168/1,100 (15.27%) | 168 (15.27%) | 0/168 | 0/660 |

Full definition validation filters bad acceptances while preserving every already correct licensed selector proof. It does not improve evidence selection. Its conditional accepted correctness is 100% because exact formal validation and deterministic interval arithmetic enforce the same mathematical rules that define these controlled tasks. This is a demonstrated safety filter with low coverage, not a learned universal scientific reasoner or a new algorithm.

For Qwen, only 312 of 1,100 answerable cases survive. The other 788 comprise 737 workflow rejections and 51 invalid responses. Phi has 893 answerable rejections and 86 invalids; Smol has 718 and 214. Rejections are not recoded as correct scientific insufficiency answers. Scientific three-way accuracy fields remain null for all selective methods.

The transparent deterministic payload oracle establishes every available proof and correctly identifies all 660 insufficient cases, attaining 100% answerable coverage and correct proof construction. It is the mandatory strong baseline. The LLM pipelines do not outperform it.

## Primary comparison: definition validation beyond run identity

The primary comparison is `full_definition` versus `run_only` using identical saved selections. Hashes of the raw selector outputs agree across all three derived methods. No substitute evidence is searched for.

| Model | Bad numerical acceptances prevented | Additional answerable numerical acceptances rejected | Correct licensed answers lost |
|---|---:|---:|---:|
| Qwen | 81/1,760 (4.60 percentage points) | 60/1,100 (5.45 points) | 0 |
| Phi | 245/1,760 (13.92 points) | 184/1,100 (16.73 points) | 0 |
| Smol | 273/1,760 (15.51 points) | 177/1,100 (16.09 points) | 0 |

For Qwen, the 81 prevented numerical acceptances consist of 42 wrong verdicts and 39 coincidentally correct verdicts with unlicensed proofs. Sixty concern answerable claims for which the selected proof was wrong, and 21 concern truly insufficient evidence. Phi's 245 comprise 116 wrong verdicts and 129 coincidentally correct unlicensed verdicts; Smol's 273 comprise 153 and 120. Thus “bad acceptance” must not be used as a synonym for “wrong label”: unsupported justification is part of the endpoint.

Paired 95% percentile bootstrap intervals resample all 55 source-system groups, retaining all within-group variants together, with 1,000 samples and seed 20261021:

- Qwen bad-acceptance prevention: 3.58–5.57 percentage points of all cases; answerable coverage reduction: 4.09–6.91 points.
- Phi prevention: 12.44–15.40 points; answerable coverage reduction: 14.73–18.64 points.
- Smol prevention: 13.86–17.10 points; answerable coverage reduction: 13.82–18.45 points.
- The difference in correct-with-proof answerable coverage is exactly zero for each model: every correctly licensed proof is preserved.

Full-definition answerable coverage intervals are 25.73–31.00% for Qwen, 9.27–12.73% for Phi and 13.27–17.36% for Smol. Degenerate intervals of 100% accepted correctness or 100% prevention of observed bad acceptances reflect the deterministic contract construction; they are not an empirical guarantee for arbitrary scientific tasks. Multiple model/metric comparisons are not multiplicity-adjusted.

## Family and presentation weaknesses

Qwen's full-definition accepted proof coverage on answerable cases is 118/440 (26.82%) for direct-scope cases, 58/220 (26.36%) for unit conversion, 76/220 (34.55%) for a missing mobile value settled by a lower bound, and 60/220 (27.27%) for a missing adsorbate value settled by an upper bound. The corresponding Phi bound results are 35/220 and 0/220; Smol results are 0/220 and 11/220.

All scientifically insufficient families have zero numerical acceptances after full validation. That is a rejection outcome, not evidence that the selector can explain why the complete packet is insufficient. Direct Qwen outputs nevertheless accept numerical answers on 217/220 ambiguous adsorbate-bound cases and 218/220 ambiguous mobile-bound cases, demonstrating difficulty distinguishing a bound from an exact answer.

Full-definition answerable coverage is 182/550 (33.09%) for Qwen structured packets and 130/550 (23.64%) for report text; Phi scores 60/550 versus 61/550; Smol scores 107/550 versus 61/550. These are generated presentations and do not establish robustness to unrestricted scientific prose.

For both members of the paired supported/contradicted contrasts, full-definition proof correctness is 57/550 pairs (10.36%) for Qwen, 11/550 (2.00%) for Phi and 23/550 (4.18%) for Smol. Direct scores are 16/550, 0/550 and 0/550. Both-rendering answerable proof correctness is 44/550 (8.00%), 8/550 (1.45%) and 27/550 (4.91%) under full validation. Even the strongest pipeline therefore has low paired completeness.

## Gate and publication implications

Accept the frozen output set for final analysis and release, documenting that every request was attempted and capped/invalid responses are included as failures. The original automated partial flag should remain in the immutable archive; a reviewed completion statement can distinguish completed execution coverage from response validity. Do not rerun Smol with a larger budget to remove these failures, repair final answers, adjust the parser, choose new prompts or replace systems based on these protected outcomes. Any later improved protocol belongs to a separately identified study.

The defensible contribution is a reproducible, coordinate-derived measurement-scope benchmark with licensed bounds, alternative valid witnesses, and an explicit evaluation of verification safety versus coverage. The final results show substantial model limitations and a conservative validation mechanism that prevents unsupported numerical acceptances at considerable rejection cost. They do not establish DFT accuracy, catalyst discovery, chemical-family or training-data independence, a first-ever blind spot, or a novel algorithm. The same-domain 55-group design and the 60-source physical attrition denominator remain material limitations.

Supporting files: `reported_comparison.json`, `report_file_comparison.json`, `method_table.csv`, `subgroups_and_intervals.json`, `raw_output_diagnostics.json`, `primary_transition_audit.json` and `recomputed/`. No delivery bundle was edited.
