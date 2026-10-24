# GeoScope — unified publication and frozen research record

This directory contains **one research investigation** using two complementary atomic source collections to test whether a selected measurement and mathematical operation physically justify an atomistic claim.

The original 55-system UMA-relaxed collection establishes the value and coverage cost of progressively checking evidence definitions; the external 48-system OC20 stored-trajectory collection tests persistent evidence-selection errors, formatting sensitivity, operation errors, scientific abstention and decision-token confidence. The scientific question and licensed-proof definition are shared; the two collections have different output contracts and central scoring comparisons. Their scores are not pooled.

## Where things are

| Location | Purpose |
|---|---|
| [`manuscript/`](manuscript/) | **Canonical unified manuscript** (main paper + Supplementary Information, figures, and bibliography) |
| [`publication_figures/`](publication_figures/) | Per-figure CSV records, numerical plotting scripts and output plots; new shared-framework Figure 1 source belongs to `manuscript/figures/` |
| [`results/`](results/) | Compact frozen external model and confidence tables |
| [`audits/`](audits/) | Independent external coordinate and proof audits; provenance manifests |
| [`workflows/`](workflows/) | Original GPU and confidence-run code; historical source, not rewritten |
| [`expert_review/`](expert_review/) | Expert review protocol and unfilled forms; human scientific review is pending |
| [`FREEZE_AUDIT_STATUS.md`](FREEZE_AUDIT_STATUS.md) | Completed checks, limits and outstanding reproducibility work |
| [`../../docs/UNIFIED_STUDY.md`](../../docs/UNIFIED_STUDY.md) | Unified research-question and figure/analysis mapping |

## Build

```sh
python -m pip install numpy matplotlib reportlab
cd publication_figures
python scripts/verify_inputs.py
python scripts/build_all.py
cd ../manuscript
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error supplementary.tex
```

The original 55-system scientific raw evidence and CPU reanalysis remain at the **repository root**, and the frozen external scientific results are preserved in their Phase 4 research paths. No experiments were rerun for the unification and no independent original 55-system re-scoring is claimed.

## Publication boundaries

The manuscript is a working scientific draft. The original and external evaluations have different response-format policies. Outer-fence normalization is a formatting diagnostic; operation repair uses an oracle and is not deployed performance. Independent expert chemical review and some complete parent structural archives remain outstanding. Authorship should be confirmed across the main paper and Supplementary Information before submission.
