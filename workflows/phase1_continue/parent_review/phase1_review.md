# Phase 1 review: UMA + OC20-Dense pilot

Reviewed 20 October 2026. Source run: `uma_phase1_20261020T133725Z_1360575_11887`.

**The computational workflow succeeded, but Phase 1 needs one bounded continuation and a correction to its draft claim cases before language-model evaluation.**

## What passed

- All 181 archived file checksums and the prepared selection/model/configuration hashes match. The launch log identifies the preparation, GPU and collection jobs.
- All 64 bundled tests passed on Swan. UMA ran on an NVIDIA L40S using FAIRchem Core 2.23.0, PyTorch 2.13.0+cu126 and the frozen `uma-s-1p2p1` checkpoint revision `9f578aa4bda5d1723b0cb0c4a5d2c115728a5b2e`.
- All 20 trajectories, containing 4,027 saved frames, are readable and finite. Atom ordering, tags, cells, periodicity and fixed-atom constraints are preserved. Fixed atoms have zero drift.
- Independent calculation from saved trajectory forces confirms the recorded convergence status. Thirteen systems meet the strict maximum mobile-force criterion below 0.05 eV/angstrom. Seven reach the 300-step cap; they are explicitly excluded from the initial claim cases.
- All 20 initial/final adsorbate graphs remain connected and unchanged under the declared distance heuristic. Visual top/side overlays show no obvious molecular fragmentation or coordinate failure.
- All 26 real/control pair measurements reproduce independently within 9.23e-16 angstrom. Synthetic controls move the adsorbate by 0.7 angstrom, preserve its aligned internal shape and leave anchors fixed. Synthetic coordinates contain no inherited calculator results.

## Seven unfinished systems

All stopped at 300 steps without ever satisfying the force criterion. None is a calculation crash.

| System and placement | Final maximum mobile force, eV/angstrom |
|---|---:|
| 41_3279_37 / heur4 | 0.087186 |
| 41_3656_153 / rand19 | 0.086892 |
| 41_5029_75 / heur6 | 0.066535 |
| 41_2093_165 / heur2 | 0.119346 |
| 19_3313_6 / rand35 | 0.155197 |
| 19_2928_66 / rand31 | 0.225501 |
| 41_351_158 / rand23 | 0.526256 |

Their recent trajectories still lower the energy, with oscillating or slowly decreasing forces. One additional attempt of at most 300 FIRE steps, with the same model, constraints and force threshold, is reasonable. Resetting the optimizer from saved final coordinates is numerical continuation; it cannot restore the unsaved optimizer state exactly. No further automatic extensions or replacement systems are planned. All 20 original systems remain in the reporting denominator.

## Claim-case defect and correction

The initial ZIP contains 780 draft cases from 13 independent scientific systems and 13 synthetic controls. These variants are correlated development examples, not 780 independent experiments.

The first generator incorrectly assumed that removing a target measurement always made its claim undecidable. The audit identified 52 synthetic cases where the visible rigid-translation description determines the omitted internal or surface-frame RMSD. It also found a real case where the remaining mobile RMSD and atom counts imply a sufficient upper bound on the omitted adsorbate RMSD. Thus at least 53 original insufficient-evidence labels are not defensible under the supplied evidence. The original case set must not be used for language-model scores.

Case schema 2 corrects this by removing all geometric values in the missing-measurements condition, retaining the definitions separately. It uses neutral case-specific aliases and keeps transformation descriptions, original IDs and source hashes outside `model_payload`. Required evidence IDs are updated to the aliases. Every case must be evaluated in a separate request without shared conversation history. The continuation package regenerates the cases with this corrected constructor.

These transparent templates remain feasibility tests. Simple field selection, arithmetic and empty-evidence checks can solve them. Phase 2 must include those strong simple baselines and refine the tasks before interpreting accuracy as scientific reasoning.

## Scientific scope and remaining review

Twenty selected systems contain only five adsorbate formulas; the 13 converged systems contain four. Phase 2 needs broader documented sampling and protected groups. This pilot does not establish broad chemical generalization or independent DFT accuracy.

Three accepted structures warrant chemical-state review: `58_8727_41` has a substantial Mo-Mo surface contraction, while `58_9161_34` and `10_1444_17` have comparatively weak/far surface contacts. These flags do not invalidate the coordinate measurements, but neither convergence nor RMSD proves successful chemisorption, catalyst quality or a global minimum.

The project remains in Phase 1. Review the continuation ZIP, remaining exclusions and corrected cases before preparing Phase 2.
