# GeoScope Phase 4 v1.7: frozen publication snapshot

This directory **adds** Phase 4 research to the original Phase 3 GeoScope repository without replacing or altering the frozen Phase 3 evaluation, original workflow code, or raw evidence ZIP.

## What is in this snapshot

- `manuscript/main.tex`, `sections/`, `references.bib`, and `manuscript/supplementary.tex`: publication-draft source documents.
- `manuscript/figures/`: 7 main + 11 supplementary prebuilt **PDF** figures.
- `publication_figures/scripts/` and `data/`: Python plotting code and 18 traceable per-figure CSVs, plus SVG and PDF figure outputs.
- `audits/`: separately implemented geometry/proof checks and frozen audit summaries.
- `workflows/`: original source-gate, four-model GPU inference and token-confidence **code and tests**, preserved without large data or weights.
- `results/`: compact four-model accuracy and confidence tables where available.
- `expert_review/`: independent reviewer protocol and unfilled response form; there is **no claim expert review has occurred**.
- `FREEZE_AUDIT_STATUS.md`: validated results, limitations, outstanding checks.

## Rebuild figures

```bash
python -m pip install numpy matplotlib
cd publication/phase4_v1_7/publication_figures
python scripts/verify_inputs.py
python scripts/build_all.py
```

To compile manuscript and Supplementary Information (requires LaTeX with biblatex/biber):

```bash
cd publication/phase4_v1_7/manuscript
pdflatex -interaction=nonstopmode main.tex
biber main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode supplementary.tex
biber supplementary
pdflatex -interaction=nonstopmode supplementary.tex
pdflatex -interaction=nonstopmode supplementary.tex
```

## Key results and limitations

External OC20 validation: 48 physical systems; 1,536 questions (960 answerable; 576 insufficient evidence); four models, 6,144 responses. Qwen3-32B-AWQ achieved 567/960 (59.1%) valid scientific proofs **after removing Markdown fences** and a decision-token confidence AUROC of 0.724 on eligible answerable questions. The original strict JSON-format Qwen3-32B score is zero. Oracle-assisted operation repair is only a controlled upper bound, not deployed correction. A deterministic proof enumerator fully resolves the controlled benchmark by construction.

Do **not** interpret the OC20 `OOD` split as an LLM pretraining exclusion guarantee. No model delivered correctly formatted abstentions on insufficient-evidence cases; confidence is not a reliable scientific validity certificate. Earlier original 55-group raw outcome/reproducibility requirements and **independent human review** are flagged in the freeze status. No experimental inference data, human judgments, or source coordinates have been fabricated.

**Status: frozen research data; manuscript under scientific review, not submission-ready.**
