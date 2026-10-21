# Phase 2 follow-up: selection versus calculation

Your first Phase 2 run completed all 1,920 requests. Its strict scores mixed scientific errors with Markdown wrapping and an insufficiently explicit citation rule. The original results remain valid as instruction-compliance measurements and are preserved. This follow-up stays inside Phase 2 and clarifies those issues before any protected test.

## Run on Swan

Upload `geom_scope_phase2_refine.zip` into the existing `geom_scope_phase1_uma` folder, alongside `phase2_pilot/`. Keep the original Phase 2 results ZIP in `results_phase2/return_zips/`.

```bash
unzip geom_scope_phase2_refine.zip
bash phase2_refine/start_phase2.sh
```

The launcher submits five sequential jobs: CPU preparation, Qwen GPU, Phi GPU, SmolLM GPU, and CPU collection. It prints the exact return ZIP path. Only one GPU is requested at a time. Return the new ZIP from `results_phase2_refine/return_zips/` here for analysis.

This reuses the working environment at `phase2_pilot/.env` and the exact model files pinned in the reviewed parent run. It installs nothing, downloads no weights and does not rerun UMA. Do not remove the previous model cache or environment. An unchanged parent-ZIP path can be supplied as the launcher's first argument; the second overrides the output root. The parent archive's SHA256 must match the reviewed ZIP.

If a job fails, let collection finish and return its diagnostic ZIP. Collection still uses the original Phase 1 Python and only the standard library. If Slurm submission itself fails, send the printed error and launcher logs. Keep at least a few GB of free space for results/logs; scheduler limits remain four hours and one L40S per model job, not runtime estimates.

## What changes

The same 320 public cases, gold labels, 20 source groups, evidence IDs and row order are regenerated from the reviewed measurements. Keeping them fixed isolates this development change; these are never untouched test data.

Each model makes three independent requests per case: direct judgment, judgment with a scope checklist, and evidence selection without a verdict. That is 960 requests per model, 2,880 total. Prompts now explicitly require exactly one matching measurement ID for a decisive judgment and an empty list for insufficient evidence. The selector returns only `evidence_ids` with zero or one ID and does not perform the inequality comparison.

The frozen primary parser accepts bare JSON or removes exactly one entire-output Markdown JSON fence. It never edits a verdict, identifier, number, key or list; commentary, extra keys, multiple citations and duplicate keys remain errors. Bare-JSON compliance is reported separately. This parser is a declared rule for this new development run, not a retroactive change to the prior primary scores.

The selector feeds two paired controls using the same raw selection:

- `selector_arithmetic`: a deterministic unit conversion and inequality calculation, deliberately ignoring the selected record's physical scope.
- `selector_guard`: the same calculation, after checking the requested pair, selected atoms, frame, alignment, periodic convention and weights. A known but mismatched selection is rejected with insufficient evidence. It never searches for a correct replacement; false abstentions are scored. An invented ID is an error, not a rewarded abstention.

The full deterministic scope selector remains a transparent upper control and already solves these templates exactly. The new guarded pipeline is an engineering control under development, not an established novel contribution. The final study must distinguish added physical-definition checking from ordinary selection and arithmetic.

## Results and review

The return ZIP includes frozen inputs/prompts/code/model hashes, raw outputs, derived tool decisions, output-contract diagnostics, per-case scores, model summaries, group-bootstrap intervals, paired contrast/representation scores and logs. Raw generation completeness and scored-answer validity are separate. A completed GPU run can still contain scientifically wrong or malformed responses.

Primary development outcomes are correct verdict plus exact required evidence, complete threshold-pair correctness, selection accuracy, unsupported acceptance and excess abstention. In this construction, `selector_arithmetic` joint accuracy equals exact selection accuracy because an exact selection makes the fixed calculator correct. The guarded result measures the subsequent accept/reject decision and must be read together with false abstention. All expected cases remain in denominators.

Read `PROTOCOL.md` for frozen scoring rules. Review these results before choosing the final method and protocol. Phase 3 will require new protected source groups and stronger controls for field matching, run-ID matching, atom-set definitions and reference/alignment changes. No novel-method, catalyst-quality, DFT-accuracy or unseen-chemistry claim follows from this development run.
