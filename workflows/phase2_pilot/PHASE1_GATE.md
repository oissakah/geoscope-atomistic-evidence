# Phase 1 gate: passed for pilot development

Reviewed 20 October 2026. Run: `uma_phase1_cont_20261020T151825Z_1912433_9416`.

**All 20 selected systems converged. Phase 1 is complete as a coordinate-measurement pilot, and Phase 2 development evaluation can begin. No further UMA run is needed for these systems.**

The seven unfinished systems required 8–259 additional FIRE steps. Their final maximum mobile forces satisfy the unchanged strict criterion below 0.05 eV/angstrom. The original 13 converged endpoints, trajectories and logs remain byte-identical. The seven continuation starts match their parent endpoints exactly, while all scientific comparisons retain the original OC20 initial coordinates as their reference.

All 228 result-file checksums passed. All 1,062 new trajectory frames have finite positions, energies and saved forces; fixed atoms do not move. Each new optimization stops at its first below-threshold frame. Independent calculations reproduce all 40 real/control geometric comparisons within 1.77e-15 angstrom. Atom ordering, masks, cells, periodicity and provisional connected adsorbate graphs remain consistent.

All 1,200 schema-2 draft case labels and required evidence IDs passed an independent payload-only audit. The prior missing-measurement leakage is corrected. These examples derive from 20 independent source systems and 20 synthetic controls; they are correlated development variants, not 1,200 independent experiments.

## What this supports

The data is suitable for testing interpretation of explicitly defined geometric measurements. It does not establish independent DFT accuracy, successful chemisorption for every endpoint, catalyst quality or global-minimum discovery. Four chemical interpretation flags remain: Mo close contact, Mn-Nb surface reconstruction, Pt weak contact and a remote molecule on a Ga-containing surface. Preserve those flags in release metadata. The measurements themselves remain valid for the stated coordinate task.

The pilot covers five adsorbate formulas. Keep all 20 systems in development; none can later become an untouched confirmatory test after inspecting its model results.

## Why Phase 2 changes the cases

The transparent Phase 1 templates have strong shortcuts. A deterministic payload-only selector scores 100%, and a value-blind heuristic using metric type and evidence availability scores 89.5%. Those cases alone would be a weak primary paper benchmark.

The next package builds a balanced development diagnostic from the frozen measurements: true/false thresholds for every metric, neutral evidence IDs, same-unit distractors from another comparison of the same source group, and matched structured/prose presentations. It compares three public language-model families under neutral and scope-checklist prompts, with deterministic scope, number-only and structure-only controls. All variants remain grouped by their original source system.

This Phase 2 checkpoint measures failure modes and tests the evaluation machinery. After its results are reviewed, refine the benchmark, freeze the proposed method and select new protected source groups before the final Phase 3 comparison. Neither completing the next GPU jobs nor a high score alone establishes a publishable contribution.
