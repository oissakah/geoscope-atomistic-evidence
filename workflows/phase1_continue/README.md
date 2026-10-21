# Phase 1 continuation and corrected claim cases

This package is for the reviewed run `uma_phase1_20261020T133725Z_1360575_11887`. Its original ZIP is pinned by SHA256. Keep that ZIP and the original `.env/` and `cache/` in place. No environment installation, new data selection, model download or language-model run is needed.

Upload `geom_scope_phase1_continue.zip` into the existing `geom_scope_phase1_uma` folder on Swan, then run:

```bash
unzip geom_scope_phase1_continue.zip
bash phase1_continue/start_continue.sh
```

The launcher prints one GPU job ID and a collector job ID. Collection runs after the GPU job finishes, including failure or timeout. Upload the new ZIP printed by the collector from `results/return_zips/`. It starts with `uma_phase1_cont_`.

If the launch fails, retain the printed error and `phase1_continue/logs/`. You may supply another path to the unchanged parent ZIP as the first launcher argument and an output directory as the second. Do not place the original model cache inside a results run directory.

## What this changes

- The original 13 converged endpoints are copied with their hashes and are not recomputed.
- Only the seven systems that reached 300 steps receive one further attempt of at most 300 FIRE steps, with the same potential, seed, fixed atoms and strict force criterion below 0.05 eV/angstrom.
- This is a fresh FIRE optimization from saved endpoint coordinates. The original solver's velocities/time-step state were not saved; it is not an exact optimizer restart. The maximum nominal budget is 600 steps for each continued system, not an automatic guarantee of convergence.
- Scientific measurements still compare the **official original starting structure with the accepted final structure**. The continuation start is recorded separately and never substituted for the original initial endpoint.
- The original 20-system selection stays fixed. Remaining failures, changed topologies or questionable adsorption states remain visible; no replacement systems are selected.

## Claim-case correction

The original cases are draft engineering tests and must not be used for language-model scores. Some omitted-measurement cases exposed a rigid translation in their provenance. Related RMSDs could also imply a bound on an omitted quantity, making an insufficient-evidence label incorrect.

Case schema 2 removes all geometric values in the missing-measurements condition while retaining the definitions. Model input uses fresh neutral aliases for every case; original IDs, file hashes and transformation descriptions stay in audit metadata. Claim/evidence pair identities still differ explicitly in wrong-run controls. Give a model only `model_payload`, in a separate request for every case with no shared conversation history.

These transparent templates are feasibility checks. High accuracy on them alone does not demonstrate scientific reasoning. Phase 2 still needs stronger simple baselines, realistic paraphrases, broader chemical coverage and protected system groups.

## Review status

The parent run's 181 file checksums and prepared manifests were verified. All 20 trajectories are readable with finite coordinates/forces and zero fixed-atom drift. Thirteen met the force threshold; seven reached the step cap. The 26 recorded real/control geometry pairs reproduce independently within about 1e-15 angstrom. Adsorbate bond graphs are provisional distance-based unwrapping aids, not proof of a particular chemical state or DFT accuracy.

This remains Phase 1. Upload the continuation results for review before Phase 2. There is no automatic second extension if some systems remain unconverged.
