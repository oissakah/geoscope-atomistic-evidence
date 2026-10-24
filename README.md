# GeoScope — Reproducibility Code

**Unified research question:** Do language models select measurements and mathematical operations that *physically support* their conclusions about atomistic simulations?

This is the **code-focused main branch** of GeoScope. It contains the scientific evaluation code, the original frozen-response input archive, essential configuration and pinned provenance, source-generation and GPU/HPC workflows, software tests, and independent audit routines. It deliberately contains **no manuscript, PDFs, publication figures, image files, plotting scripts, or presentation material**.

The complete unified publication/manuscript version was preserved before cleanup as the branch [`draft/unified-manuscript-2026-10-24`](https://github.com/oissakah/geoscope-atomistic-evidence/tree/draft/unified-manuscript-2026-10-24).

## What can be reproduced

| Collection | Scientific role | What is included |
| --- | --- | --- |
| 55 qualified UMA-relaxed OC20-Dense source groups | Identical-selection comparison of increasingly strict physical-definition checks; validity, coverage, and direct-answer evaluation | The archived 1,760 cases, gold proofs, all 10,560 first-attempt model responses, pinned settings, CPU scorer, and the code to rerun scores |
| 48 OC20 DFT-trajectory source groups | External proof-validity, error taxonomy, output-format and confidence diagnostics | Source gate, inference, confidence, and independent audit **code**, pinned identifiers, compact frozen score tables, and audit metadata |

**Important external-data limitation:** The external 48-system GPU raw-response and confidence ZIP archives, original large OC20 trajectories, and all of the upstream UMA/Phase 3 parent archives are **not contained in this repository**. The Phase 4 scripts alone cannot reproduce all external numerical results until those exact archived inputs and pinned model environments are supplied. Do not describe the external result as fully self-contained. The pinned archive identities appear in `evidence/phase4/FROZEN_ARCHIVE_MANIFEST.json`.

## Quick start: reproduce the frozen 55-system scores (CPU only)

Python 3.12, standard library:

```bash
python verify_repository.py
python reproduce_analysis.py
PYTHONPATH=workflows/phase3_final/src python -m unittest discover -s workflows/phase3_final/tests -v
```

The `reproduce_analysis.py` program authenticates `evidence/final_results_original.zip` and its 69 internal checksums, verifies completeness of the 10,560 original attempts, then recomputes the frozen analysis from raw responses. It writes reports to `recomputed/`. No model download or GPU is required for **score reproduction**. Tests use synthetic software fixtures, not new atomistic calculations.

`verify_repository.py` checks a manifest of the retained original frozen input/code files. The branch is also tracked by Git; the manifest is not a claim that every moved workflow file has a second SHA-256 hash.

## Code layout

- `reproduce_analysis.py` — trusted command to replay the original frozen evaluation.
- `lib/finalstudy/` — proof verifier and deterministic scoring implementation.
- `evidence/final_results_original.zip` — **required** original input archive; it is not a publication artifact.
- `workflows/geom_scope_phase1_uma/` — original UMA source and relaxation scripts.
- `workflows/phase3_prepare/` — frozen physical source qualification.
- `workflows/phase3_final/` — final inference, benchmark and tests.
- `workflows/oc20_source_gate/` — external OC20 source records, geometry and benchmark builder.
- `workflows/external_four_model_inference/` — four-model inference and HPC launch scripts.
- `workflows/token_confidence/` — confidence replay and offline confidence analysis.
- `audits/phase4/` — independent consistency/proof and frozen-archive audit routines.
- `evidence/phase4/` — external compact result tables and archive-identity metadata, **not** complete raw results.

Slurm `.sbatch` and `.sh` scripts, frozen JSON pins and tests are kept where necessary to rerun the computational workflows. No source archives or model weights are silently substituted.

## Reexecuting physical simulations or GPU inference

Raw-score replay and rerunning all upstream simulations are **different tasks**. Source generation requires official OC20 structures, ASE/FAIRchem/UMA and its pinned checkpoint, and suitable GPU hardware. The four-model external evaluation requires the exact model and input archives identified in its frozen protocols. For details consult the workflow `EXPERIMENT_PROTOCOL.md` and `HPC_RUNBOOK.md` files and `workflows/phase3_final/PROTOCOL.md`. For scientific source and license restrictions see `THIRD_PARTY_NOTES.md`.

The original archive provenance and immutable publication files remain on the draft branch and in Git history. This cleanup changes repository layout only; it does not create a new experimental result, replace scientific data, or establish independent model-pretraining exclusion or autonomous catalyst-discovery performance.
