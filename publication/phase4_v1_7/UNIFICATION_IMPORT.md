# Applying the unified GeoScope manuscript

The manuscript and publication figures are coordinated with the existing Phase 3 and Phase 4 research repository. This document records the safe upgrade procedure.

## Scope

The publication overlay replaces the *active manuscript* at `publication/phase4_v1_7/manuscript/`, its canonical Figure 1, and publication navigation/build instructions. It introduces a structural preflight check at `tools/verify_unified_publication.py`. It **does not modify** the raw archives under `evidence/`, the analysis results under `analysis/`, the scientific workflows, or the frozen Phase 4 audit records.

The revised Results and Discussion are organized into six findings, not a chronological original/external-study split. The manuscript continues to report source-specific denominators and scoring conventions separately.

## Apply the reviewed local overlay

Obtain `GeoScope_Unified_Repository_Overlay_2026-10-24.zip` supplied with the manuscript revision. Extract it **outside** the Git clone, then run:

```bash
python apply_to_clone.py /path/to/geoscope-atomistic-evidence
cd /path/to/geoscope-atomistic-evidence
python verify_repository.py
python tools/verify_unified_publication.py
python reproduce_analysis.py
git status --short
git diff --stat
```

The installer validates its manifest, backs up any overwritten publication files, recalculates affected checked-file hashes, and refuses to overwrite preserved research-evidence directories. It does not commit, push, delete files, or alter model outputs.

For manuscript builds:

```bash
cd publication/phase4_v1_7/manuscript
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error supplementary.tex
```

## Review points before merge

1. Compare the compiled main PDF and Supplementary Information with the reviewed unified manuscript.
2. Confirm Figure 1 shows one physical-proof framework fed by two complementary atomic source collections.
3. Verify original experimental archives and result CSVs are unchanged.
4. Keep strict JSON, fence-normalized scoring, operation-oracle repair, and the original same-selection checker comparison scientifically distinct.
5. Confirm authorship between the main article and Supplementary Information.
6. Do not claim expert chemical review or prospective autonomous optimization has been completed.

**Status:** This GitHub branch is an editable review branch; the complete manuscript overlay is not yet committed until the installation step has been applied and reviewed.
