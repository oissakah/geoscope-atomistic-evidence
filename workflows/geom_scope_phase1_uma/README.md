# Phase 1: UMA evidence for geometric claim verification

This fresh package uses public OC20Dense data and FAIRchem directly. It supersedes the earlier CPU-only/private-repository package. It has no dependency on the old catalyst repository or its filesystem layout.

The research question, three phases and review gates are in [PROJECT_PLAN.md](PROJECT_PLAN.md).

The dependency versions and upstream interfaces were checked against official sources on 19 October 2026. The package still needs the Swan execution checks described below.

Phase 1 produces traceable atomistic measurements and claim cases. **It does not run language models or demonstrate a remedy.** The Swan GPU run and its resulting scientific measurements still need to be validated on your account. Local tests and a synthetic demonstration do not establish successful GPU execution or a real-data result.

## Run on Swan

Use a working location with room for the environment, model weights and dataset cache. Unpack the ZIP, enter its `geom_scope_phase1_uma` directory, then submit setup:

```bash
sbatch setup.sbatch
```

Wait for the setup job to finish and check `setup-JOBID.log`. Setup installs the environment on a CPU compute node; do not run an installation on the login node. An existing `.env` is checked without being overwritten. If it is incomplete, inspect the setup log and use a fresh package directory rather than overwriting it. If setup fails before a usable Python environment exists, there is no automatic result ZIP; return the setup log instead.

Accept the access terms on [facebook/UMA](https://huggingface.co/facebook/UMA) using your Hugging Face account. Then authenticate once from the package directory:

```bash
.env/bin/hf auth login
bash start_phase1.sh
```

Enter the token only into the interactive login prompt. Do not put tokens in the configuration, scripts, logs or returned ZIP. Authentication does not download the model; preparation does that inside a compute job.

The launcher prints one run ID and three job IDs:

1. **Prepare:** a CPU job downloads/caches public data and the authorized model, freezes source/model provenance and prepares the selected inputs.
2. **Run:** a GPU job runs after preparation finishes. It checks preparation status before inference; failed preparation should produce a diagnostic result. It first processes a three-system smoke test before the full pilot.
3. **Collect:** a CPU job runs after the GPU job finishes, including failure or timeout, and packages available results and diagnostics.

The dependencies use `afterany` deliberately so a failed upstream stage does not leave the collector waiting for a success that cannot occur. If you cancel all jobs, delete the environment or lose access to the filesystem, automatic collection may not run. Keep the printed job IDs and Slurm logs.

Each run has its own directory under `results/`. Return the ZIP location printed by the collector. Review its status first: a diagnostic or partial run is useful, but it is not a completed 20-system result. Return only that ZIP; leave `.env/` and `cache/` out. The launcher records job IDs in `results/RUN_ID/launcher_jobs.json` so the collector can include the matching Slurm logs. A run interrupted during inference can be reported as `INTERRUPTED_OR_TIMEOUT`; this is a partial diagnostic result.

The usual return location is `results/return_zips/RUN_ID_phase1_results.zip`. Its `summary.json` reports `READY_FOR_SCIENTIFIC_REVIEW`, `PARTIAL_NEEDS_REVIEW`, or a diagnostic state such as `FAILED` or `INTERRUPTED_OR_TIMEOUT`. If the full results exceed the 512 MiB return budget, a small `PACKAGING_FAILED` diagnostic ZIP replaces the earlier archive; the full files stay on Swan. Every archive includes a checksum manifest. You can check it without extracting or executing its contents:

```bash
.env/bin/python verify_results.py results/return_zips/RUN_ID_phase1_results.zip
```

No status automatically authorizes Phase 2: upload the ZIP here first. A failed setup that never creates a usable environment may only leave its setup logs, as described below.

For a deliberately small first run, set `"smoke_only": true` in `config/pilot.json`; this stops after three systems. Once that output has been reviewed, restore `false` and start a new run. The default `false` configuration attempts the full 20-system pilot after the initial smoke test. Twenty systems are a feasibility choice, not a sufficient sample for a definitive model comparison.

## Configuration and resource requests

The supplied `config/pilot.json` selects 20 systems using seed 20261019, at most 180 atoms per configuration, and at least three adsorbate atoms. It uses `uma-s-1p2p1`, the `oc20` task, FIRE relaxation, a 0.05 eV/Å force threshold and a 300-step limit. A run that reaches its step limit is not automatically converged. Configuration thresholds are task definitions and planning choices, not universal chemical accuracy criteria.

The starting data is the official 2023 OC20-Dense OOD validation ASE archive: 15,256 configurations from 200 systems, about 13 MB compressed. Only one eligible initial placement per selected system is relaxed. This package does not download the large DFT trajectory archives. Selection, input hashes, model revision and settings are frozen before GPU inference. Nonconverged endpoints remain in the logs and relaxation records but do not generate the primary claim cases. Topology changes or ambiguous mappings are excluded with reasons.

Setup and preparation request CPU nodes for up to one hour. The GPU job requests one GPU, four CPUs, 32 GB system memory, and two hours, with the `gpu_l40s` constraint. An L40S has 48 GB device memory; the Slurm `--mem=32G` request concerns host memory. Edit the GPU constraint in `phase1.sbatch` if the permitted hardware on your account differs. Runtime and sufficient memory must be established with the smoke run. A timeout can yield a partial archive through collection.

The environment pins Python 3.12, PyTorch 2.13.0 with CUDA 12.6 wheels, FAIRchem Core 2.23.0, ASE 3.27.0, NumPy 2.3.5 and SciPy 1.16.3. Setup checks imports and versions on CPU; the run stage checks actual GPU execution. Successful installation does not guarantee that the node's driver supports the wheel.

By default the cache is `cache/` in the package directory, separate from `results/`. Point it to another shared storage location if desired:

```bash
export GEOMSCOPE_CACHE=/absolute/path/to/shared/geom_scope_cache
bash start_phase1.sh
```

The launcher also accepts `--config PATH`, `--cache-dir PATH`, `--output-root PATH` and `--run-id ID`. Use a new run ID for each attempt; the launcher rejects an existing run directory. The cache must remain outside the results directory so bulky downloads and authentication material are not bundled as run artifacts. Custom configuration files must use the same schema as `config/pilot.json`.

## Scientific scope and the three phases

**Phase 1 establishes geometric ground truth and provenance.** Pair identities, atom correspondence, masks, frame, alignment and periodic treatment must be explicit. Official OC20Dense placements belonging to the same adsorbate/surface system can start in different adsorption sites and relax to different minima. Differences between their endpoints describe placement or basin variation; they do not demonstrate scheduler effects or failure to reproduce the same computation. Preserve all placements and transformed variants from one source system together for later splitting.

A geometric claim concerns the supplied coordinates and its declared measurement definition. Numerical convergence, geometric agreement, agreement with an archived DFT reference, and finding a global minimum are different claims. Existing DFT energy targets do not supply missing DFT coordinates, and UMA total energies cannot be compared directly with adsorption energies without compatible referencing. This pilot performs no new DFT calculations.

Synthetic transformations must retain their synthetic label. Adsorbate-only rigid motion can preserve aligned internal shape while changing surface-relative placement. Recompute the affected geometric quantities; do not carry original energy, force or convergence claims onto transformed coordinates. Periodic wrapping and symmetry can make some apparent motions equivalent, so expected relations need executable checks.

**Phase 2 compares language models on frozen evidence.** Evaluate direct answering, metric-aware instructions, explicit evidence selection and numerical/unit tools. Supply only each case's `model_payload` to a model; the public case record can also contain labels and diagnostic fields that must not enter the prompt. Keep source systems, placements, paraphrases and transformations in one split and report complete-pair correctness, evidence selection, unsupported acceptance, abstention and formatting separately. UMA generates evidence; the language models interpret it. Those are separate roles.

**Phase 3 tests a measurement-definition/provenance checker.** Evaluate whether checking subset, frame, alignment, correspondence, PBC and reference identity improves held-out evidence use beyond ordinary numerical tools. Include strong baselines and ablations. Do not claim a successful mitigation until the protected evaluation supports it.

The proposed project is a specialized extension of existing scientific evidence verification, including [PhyVer](https://aclanthology.org/2026.acl-demo.54/) and [Table-Text Alignment](https://aclanthology.org/2025.findings-emnlp.135/). Public OC20 data is also related to UMA's training domain. A new language-model evaluation split does not establish unseen chemistry for the potential. This package supports a feasibility study; it does not establish first-ever novelty, independent DFT accuracy or publication readiness.

## Sources and troubleshooting

Use the [OC20Dense documentation](https://facebookresearch.github.io/fairchem/oc20dense/), [FAIRchem UMA guide](https://github.com/facebookresearch/fairchem/blob/main/docs/core/uma.md), and HCC instructions for [job submission](https://hcc.unl.edu/docs/submitting_jobs/), [partitions](https://hcc.unl.edu/docs/submitting_jobs/partitions/) and [Conda environments](https://hcc.unl.edu/docs/applications/user_software/using_anaconda_package_manager/).

If preparation cannot access the model, check accepted UMA terms and authentication. If a job fails or times out, let the collector finish and inspect the reported archive and matching `logs/prepare-JOBID.log`, `logs/phase1-JOBID.log` and `logs/collect-JOBID.log`. The preparation/GPU/collection commands are separate runner modes so diagnostics can be collected without repeating inference. Running another GPU attempt requires a fresh run ID.
