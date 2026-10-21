# Delivery checks

Checked locally on 20 October 2026:

- All 65 tests pass. Tests cover geometry/alignment/MIC and atom masks; safe pinned source handling; exclusion before selection; fixed batches; original-reference comparison; partial or missing batches; saved-checkpoint recovery; interrupted/corrupt-attempt preservation without automatic retry; input/source hash freezing; failed preparation and return-ZIP verification.
- CPU preparation using the actual pinned official archive selected exactly 60 unique source groups with zero overlap with the 20 development groups. Selected initial structures contain 36–168 atoms and nine descriptive adsorbate formulas. This is a source-eligibility preflight, not UMA or language-model performance evidence.
- The actual reviewed parent ZIPs pass their pinned archive and member hashes. A CPU collection rehearsal with the real selected inputs and deliberately absent GPU batches retains the full 60-source denominator and returns a checksum-verified partial-result ZIP.
- A separate analytic zero-force ASE test produces genuine optimizer/checkpoint files and verifies CPU-only recovery when the batch summary is missing. Those analytic fixtures are tests only and are excluded from research data and delivery results.
- All Python files compile. All five shell/Slurm scripts and their embedded Python blocks pass static syntax checks. Delivery text uses Linux line endings and UTF-8 without a byte-order mark; ZIP paths, executable permissions and archive integrity are checked.

The production UMA checkpoint and environment have already worked on Swan, but this new 60-system, 600-step run has not been executed locally. Native Slurm submission/recovery and actual GPU calculations still require Swan validation. No model weights, environment, candidate coordinates, gold labels, model outputs or local rehearsal results are included in the delivery ZIP.
