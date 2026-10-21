# Regenerate the figures

The delivered figures are standalone SVGs in `output/`. Text is converted to vector paths, so viewing the SVGs does not require the original font. Each script verifies the original evidence ZIP and its checksums before reading the scores; no uploaded code is executed.

To regenerate them, install `requirements.txt` into a separate plotting environment. This does not change the frozen Swan inference environment. Arial must be installed locally. If it is not registered with Matplotlib, set `GEOMSCOPE_ARIAL_FONT` to your licensed Arial TTF file. Font files are not redistributed.

Run from this folder:

```bash
python 01_plot1_qwen_acceptance.py
python 02_plot2_answerable_coverage.py
python 03_plot3_direct_accuracy.py
```

Each script creates one SVG and one JSON file containing its exact plotted numbers and caption. `CAPTIONS.md` collects the captions. Preview PNGs were generated outside this release solely for visual inspection; the publication exports remain SVG.

Figure 1 separates wrong verdicts from correct-looking verdicts with invalid proofs. Figure 2 reports numerical coverage, so the run-ID bars must not be read as accuracy. Figure 3 reports scientific three-way scores for direct answers and the deterministic oracle; guard rejections are not scored as scientific insufficiency.
