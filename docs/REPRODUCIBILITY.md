# Reproducing GeoScope

The repository supports self-contained reproduction of the **final analysis**. Reexecuting the original UMA and language-model calculations additionally requires their recorded environments, cached checkpoints and parent result archives. These are different reproducibility targets.

## 1. Recompute the frozen final scores

Use Python 3.12 from the repository root:

```bash
python reproduce_analysis.py
```

This requires only the Python standard library and the files already in the repository. It does not require a GPU, Hugging Face account, downloaded model or plotting installation.

The script:

1. Verifies the exact SHA256 of `evidence/final_results_original.zip`, validates safe archive membership, and checks all 69 member checksums.
2. Reads cases, gold proofs, raw predictions and frozen settings as data. It does not import or execute the archived source snapshot.
3. Checks that all 10,560 expected first-attempt request identities occur exactly once.
4. Recomputes the entire evaluation using the trusted scorer in `lib/finalstudy/`, including the frozen source-group bootstrap.
5. Requires exact agreement with the recorded evaluation before writing the reproduced reports.

By default, outputs go to `recomputed/`. They include the full evaluation, method and case scores, completeness, paired comparisons, family/presentation breakdowns and a reviewed summary. To choose another output directory:

```bash
python reproduce_analysis.py --output-folder recomputed_check
```

Reviewed lightweight tables and examples already appear in `analysis/`. The input ZIP remains unchanged.

All 10,560 requests were recorded. SmolLM's 261 output-cap failures remain in the denominators: 258 direct answers and three evidence selections. The preserved collector summary says `PARTIAL_FINAL_RESULTS` because it counts untruncated responses as successful. Score reproduction retains that original summary and separately records completion of the planned first-attempt experiment. It does not retry, repair or discard failed responses.

## 2. Run the final workflow's software tests

The frozen final workflow has 57 CPU unit tests covering the benchmark, model/request protocol, proof-aware scoring and orchestration. They use synthetic responses and mocked inference; they do not download a checkpoint or perform new research calculations.

On a Unix shell, from the repository root:

```bash
PYTHONPATH=workflows/phase3_final/src python -m unittest discover -s workflows/phase3_final/tests -v
```

In PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path workflows/phase3_final/src).Path
python -m unittest discover -s workflows/phase3_final/tests -v
```

Python 3.12 and the standard library suffice for these final-workflow tests. Earlier atomistic workflows have additional ASE, NumPy and related dependencies. Their individual instructions and frozen environments remain authoritative for those stages.

## 3. Regenerate the figures

The delivered publication figures are standalone SVGs in `figures/output/`. Their captions and source scripts are in `figures/`. Regenerating them is optional and separate from score reproduction.

Install the versions in `figures/requirements.txt` in a plotting environment, then run:

```bash
cd figures
python 01_plot1_qwen_acceptance.py
python 02_plot2_answerable_coverage.py
python 03_plot3_direct_accuracy.py
```

The scripts verify the original evidence before reading scores. Each writes an SVG and a JSON record of the plotted values and caption. They require a licensed local Arial font, or `GEOMSCOPE_ARIAL_FONT` pointing to its TTF file. Font files are not redistributed. See [the figure guide](../figures/README.md) for details. Plotting packages do not alter the frozen inference environment.

## 4. Inspect the original workflows and delivery bundles

The extracted original scripts are visible in:

```text
workflows/geom_scope_phase1_uma/
workflows/phase1_continue/
workflows/phase2_pilot/
workflows/phase2_refine/
workflows/phase3_prepare/
workflows/phase3_final/
```

The corresponding unchanged delivery ZIPs are in `runners/`. Those are script bundles, not the complete sequence of original result archives. Workflow documentation describes the state and validation available when each bundle was prepared; later reviewed findings appear in the root `FINAL_REPORT.md` and `audits/`.

The small `lib/finalstudy/` copy supplies the trusted benchmark/scorer used for CPU reanalysis. Original frozen workflow source is preserved separately rather than updated in place to match a new machine.

## 5. Reexecuting physical evidence generation

Full atomistic reexecution requires the official pinned OC20-Dense ASE initial-configuration archive, access to the gated UMA checkpoint, the recorded model/reference files, and an ASE/FAIRchem/PyTorch environment matching the original run. The reviewed UMA checkpoint is `uma-s-1p2p1` at revision `9f578aa4bda5d1723b0cb0c4a5d2c115728a5b2e`; file hashes and paths are preserved in the parent manifests.

The original calculations ran on UNL Swan with NVIDIA L40S GPUs. Source qualification used one continuous FIRE optimization from each selected initial structure, at most 600 steps, and a strict maximum mobile-force threshold below 0.05 eV/angstrom. It retained the 60 selected sources and reported two nonconvergences and three graph changes without replacement. The earlier development continuation had a different explicitly recorded restart policy.

The repository contains the resulting final measurement records, benchmark and model outputs, but does not duplicate every structural trajectory or development result archive. For the complete physical audit trail, retain the original result ZIPs referenced by the frozen parent provenance, including:

- `uma_phase1_20261020T133725Z_1360575_11887_phase1_results.zip`
- `uma_phase1_cont_20261020T151825Z_1912433_9416_phase1_results.zip`
- `phase2_pilot_20261020T171803Z_2789668_14528_phase2_results.zip`
- `phase2_refine_20261020T201951Z_3900908_15370_phase2_results.zip`
- `phase3_prepare_20261020T211054Z_234814_30462_phase3_prepare_results.zip`

Their original SHA256 values, source identities and checkpoint provenance are the references for reconstruction. A newly packaged archive with the same logical contents can have different bytes and will fail an exact parent-archive check.

Model weights, cache directories, authentication tokens and complete compute environments are not included. Obtain upstream materials under their own terms; see [THIRD_PARTY_NOTES.md](../THIRD_PARTY_NOTES.md). No new blanket project license is assigned here.

## 6. Reexecuting language-model inference

The final workflow reused the successful development model cache and environment. It used Python 3.12, Transformers 5.3.0, PyTorch 2.13.0 with CUDA 12.6, Accelerate 1.12.0 and NumPy 2.3.5. Exact model commits and weight hashes are recorded in the preserved manifest.

The inference protocol used greedy BF16/SDPA generation, batch size two, a maximum of 6,144 input tokens without input truncation, and at most 160 new tokens. SmolLM extended thinking was disabled and its chat-template date fixed. The final workflow's `PROTOCOL.md`, configuration and source snapshot specify the complete settings and stop rule.

The original launchers expect the Swan project tree, known-working environments, cached file locations and exact parent ZIPs. Reconstruct those dependencies before using them. Resolving a current model branch, changing paths without updating the recorded provenance, installing a different software stack, or modifying generation limits does not recreate the original frozen experiment. Hardware and software can also affect fresh GPU outputs despite greedy decoding.

A new inference run should have a separate experiment identity and retain all attempts. The inspected final groups must not be used to tune a revised method and then reported as an untouched final test. No rerun is needed to reproduce the existing scores.

## Interpretation checks

Report the 55 qualified evaluation groups alongside the original 60-source denominator and all five exclusions. Keep development results separate from the frozen new-group evaluation. Preserve token-cap and formatting failures, the deterministic oracle, and source-group rather than case-level uncertainty estimates.

A selector's rejected measurement is an operational nonanswer, not a correct scientific insufficient-evidence verdict. Full validation's perfect accepted correctness is conditional on the explicit finite proof system; answerable-case coverage is the practical cost. These checks reproduce a controlled evidence-selection study, without establishing DFT accuracy, new chemical families or a novel learned-reasoning capability.
