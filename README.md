# GeoScope — definition-aware verification of atomistic evidence

**One scientific question, two complementary atomic source collections:** do language models select measurements and mathematical operations that physically justify claims about atomistic simulations?

Scientific AI can identify the correct structure pair and even produce the correct answer while using an invalid measurement. GeoScope evaluates *licensed scientific proofs*: a proposed claim is supported only when its evidence identifier, compared endpoints, atom set, coordinate frame, alignment, periodic treatment, weighting, and mathematical operation are compatible with the claim. GeoScope is a benchmark and verifier for atomistic evidence; it is **not** a deployed autonomous catalyst-discovery system.

## Study design

| Shared framework | UMA-relaxed OC20-Dense collection | OC20 stored DFT-trajectory collection |
|---|---|---|
| Physical evidence | Mobile and adsorbate stored-frame RMSD, adsorbate rigid-aligned internal RMSD, admissible subset bounds | The same measurement types and proof rules |
| Atomic sources | 55 qualified groups | 48 qualified groups |
| Claims | 1,760 variants (1,100 answerable; 660 insufficient evidence) | 1,536 variants per model (960 answerable; 576 insufficient evidence) |
| Models | Qwen3-4B, Phi-4-mini, SmolLM3-3B | The same three plus Qwen3-32B-AWQ |
| Main analysis | Arithmetic-only vs. comparison-ID vs. full-definition checking; verdict/proof and coverage | Strict vs. fence-normalized scoring; error types; oracle-assisted operation repair; decision-token confidence |

Both source collections use the same conceptual evidence/proof framework, but their **output-format contracts and central comparisons differ**. Results are reported separately, rather than being pooled as though the evaluations were identical.

## Core findings

- In the 55-system collection, full-definition checking retained **312 valid Qwen numerical proofs** and rejected **81 additional invalid acceptances** left by a comparison-ID-only check, including 39 correct verdicts justified by invalid evidence. Valid accepted coverage on 1,100 answerable questions was 28.36% for Qwen.
- On the independent-source OC20 trajectory collection, Qwen3-32B-AWQ returned **567/960 (59.1%)** valid proofs after *outer Markdown-fence normalization*. Its original strict-JSON score was **0/960** because its responses were fenced. Fence normalization is a formatting diagnostic, not scientific repair.
- All four external models had **0/576** qualifying scientific abstentions under the frozen output contract. Qwen3-32B-AWQ's decision-token confidence AUROC was **0.724**; **185/601** responses above a 0.99 decision-token score were scientifically invalid.
- Deterministic proof enumeration resolves all benchmark questions from complete structured public evidence under the predefined rules; this work **does not** show that an LLM/verifier hybrid outperforms deterministic-only inference.

## Start here

- **[Unified manuscript](publication/phase4_v1_7/manuscript/)** — primary publication draft and Supplementary Information; six integrated Results and Discussion subsections and a shared-framework Figure 1
- [One-study design and mapping](docs/UNIFIED_STUDY.md) — how the two source collections and figures support the same research question
- [Publication package guide](publication/phase4_v1_7/README.md) — manuscript, audits, model outputs, figure sources, reproducibility status
- [Data card](DATA_CARD.md) and [original-study final report](FINAL_REPORT.md) — frozen 55-system methods, source qualification, outcomes, and limitations
- [External freeze and audit status](publication/phase4_v1_7/FREEZE_AUDIT_STATUS.md) — external verification and unresolved expert-review requirements

## Reproduce the original 55-system analysis

Using Python 3.12 and the standard library, from the repository root:

```bash
python verify_repository.py
python reproduce_analysis.py
PYTHONPATH=workflows/phase3_final/src python -m unittest discover -s workflows/phase3_final/tests -v
```

The raw original model selections and exact freeze records remain in `evidence/final_results_original.zip`. This archived evidence is not rewritten by the publication update.

## Reproduce external publication figures and build the manuscript

```bash
python -m pip install numpy matplotlib reportlab
cd publication/phase4_v1_7/publication_figures
python scripts/verify_inputs.py
python scripts/build_all.py
cd ../manuscript
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error supplementary.tex
```

`latexmk` requires a LaTeX distribution with `biber`. The canonical unified overview is regenerated using `manuscript/figures/make_figure_01.py`; the figure plotting pipeline calls this script for Figure 1, while the other figures retain their original numerical CSV inputs. Read [manuscript build notes](publication/phase4_v1_7/manuscript/README_BUILD.md).

## Scope, provenance, and status

The original phase-level code, frozen model outputs, source audits, plots and scientific datasets remain archived and traceable. The unified manuscript is an **editorial reorganization of frozen results**, not a new evaluation or claim of external checker-ablation replication. No evidence establishes that the external OC20 systems were absent from LLM pretraining. UMA relaxation and DFT trajectory geometry alone do not establish a globally stable adsorbate or catalytic activity. The complete structural source archives and expert chemical review retain the limitations documented in the freeze reports.

**Publication status:** working draft; independent human chemical review and authorship reconciliation are outstanding. See [third-party source notes](THIRD_PARTY_NOTES.md) for reuse considerations. The project has not selected a blanket license for its original code.
