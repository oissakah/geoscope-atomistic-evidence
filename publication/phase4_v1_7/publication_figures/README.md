# GeoScope publication figures — unified manuscript

The canonical publication has **one shared physical-proof framework** tested on two complementary atomic source collections. Figure 1 is a conceptual diagram of that framework and is regenerated from the manuscript's editable source script; the remaining 17 plots have frozen per-figure numerical CSV inputs.

## Build all figures

```bash
python -m pip install numpy matplotlib reportlab
python scripts/verify_inputs.py
python scripts/build_all.py
```

Figure 1: `../manuscript/figures/make_figure_01.py` generates the canonical vector PDF. The build script copies it to `main/figure_01.pdf`. The optional SVG view is created when `pdftocairo` is present; a prebuilt SVG is committed for browsing. Figure 1's CSV is historical protocol annotation, not a numerical data source. Do **not** use the old four-panel chronological diagram for the unified manuscript.

Figures 2–7 and S1–S11: `scripts/plot_common.py` reads the frozen CSVs under `data/`; the original numerical values and data sources are unchanged.

## Figure map

| Figure | Content |
|---|---|
| 1 | Shared physical-evidence definitions and licensed-proof framework across both source collections |
| 2 | Original 55-system same-selection comparison: arithmetic, structure identity and full-definition checks |
| 3 | Original verdict-only versus proof-aware evaluation |
| 4 | External 48-system stored-frame versus internal aligned adsorbate RMSD |
| 5 | External four-model strict, fence-normalized and diagnostic operation-repair outcomes |
| 6 | External Qwen3-32B error types by presentation |
| 7 | Decision-token confidence AUROC and highly confident invalid proof rate |

Supplementary figures S1–S11 remain original-source diagnostic plots. Source groups, uncertainty units, missing original per-system coordinates and expert-review limits are documented in the frozen audits. Neither normalized formatting nor oracle-assisted operation repair represents an improved independent LLM proof-selection algorithm.

## Output integrity

`SHA256SUMS.txt` is a publication-asset snapshot. Regenerating PDFs can change binary bytes because of plotting tools and embedded PDF metadata. Scientific CSV inputs remain the authoritative numerical records; run `scripts/verify_inputs.py` for semantic and denominator checks. Figure 1 is editorial artwork, not a measured result.
