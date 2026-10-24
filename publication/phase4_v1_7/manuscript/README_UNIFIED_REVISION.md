# GeoScope unified manuscript revision — 24 October 2026

## Files to compile
- `main.tex` — main manuscript (`main.pdf` included as matching compiled preview)
- `supplementary.tex` — Supplementary Information (`supplementary.pdf` included)
- `sections/abstract.tex`, `introduction.tex`, `methods.tex`, `results_discussion.tex`, `conclusion.tex`
- `figures/figure_01.pdf` — new vector overview; regenerate with `python figures/make_figure_01.py` (`reportlab` required)
- Original figure files 02–07 and S01–S11 preserved exactly from supplied ZIP.

## What changed
1. Reframed the Abstract, Introduction, Methods, Results/Discussion, and Conclusion around **one test of physically licensed atomistic evidence** across two complementary source collections.
2. Replaced Figure 1 to show the shared physical-proof definitions and source-specific verification and confidence diagnostics.
3. Reorganized the Results from eight phase-oriented subsections into six finding-oriented sections, retaining quantitative findings, Figure 2–7 insertion positions (in numerical order), captions, labels, and both original tables.
4. Clarified that source-specific scoring policies differ: the original UMA study permits one outer JSON code fence and compares arithmetic-only, comparison-ID, and full-definition checks, while the OC20 external study reports strict JSON, fence-normalization, and oracle-assisted operation repair. **No external comparison-ID/full-definition ablation has been newly computed.**
5. Reduced repetitive autonomous-catalyst examples; retained scientific relevance where it clarifies the physical consequences, with no claim that catalyst screening improved.
6. Cleaned `references.bib` of duplicate keys, repaired several entries against publisher records (Burger, Szymanski/A-Lab, Boiko), and removed previously questionable uncited records.
7. Moved uncompiled legacy `sections/results.tex` and `sections/discussion.tex` into `archive/unused_sections/`, unchanged, to preserve provenance while removing competing active manuscript sections.
8. Harmonized the Supplementary Information's framing, without changing the analysis numbers or supplementary figure files.

## Important evidential boundaries
- Original counts have been carried forward from the supplied manuscript; this is an **editorial and figure-restructuring revision**, not a fresh case-level reanalysis or model rerun.
- The external 48-source sample is qualified and not demonstrated unseen in model training; a direct replication of the original checker-ablation on the external responses was **not performed**.
- The original deterministic-only oracle enumerates all permitted proofs from complete public evidence; no hybrid-system superiority is claimed.
- The supplied ZIP does not include the separately archived `publication_figures.zip` source-data/scripts package or the full original raw model-response freeze. See Supplementary Information for provenance limits.
- The main manuscript lists two authors, while the original Supplementary Information lists five. **Please confirm the intended authorship with all contributors before submission.** Author names and affiliations were not silently changed.
- Expert chemical review and prospective autonomous-experiment validation remain outstanding.

## Build (tested with latexmk + biber)
```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error supplementary.tex
```
The PDFs in this ZIP were compiled from these exact updated sources.
