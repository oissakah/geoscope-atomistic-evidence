# Three phases for the fresh UMA + OC20-Dense project

Research question: **Can a language model identify whether a simulation measurement supports a scientific claim when similar-looking measurements use different atom subsets, alignment rules or source structures?**

UMA generates the atomic coordinates. A deterministic geometry calculation supplies each defined measurement. Language models then judge claims using the supplied evidence. This separation lets us study interpretation errors without attributing every error to the simulator.

| Phase | Work | What comes back for review |
|---|---|---|
| 1: Establish reliable evidence | Select 20 distinct systems from official OC20-Dense initial configurations; relax with one pinned UMA model; record constraints, atom correspondence, force convergence and three geometry metrics. Add separately labelled rigid-motion controls. | A ZIP with initial/final structures, trajectories, logs, provenance, measurements, draft claim cases and diagnostics. |
| 2: Measure language-model failures | Refine weak templates and freeze a larger benchmark after Phase 1 review. Compare several model families/sizes using identical evidence, direct answering, explicit evidence selection and ordinary numerical tools. | A ZIP with model/version settings, prompts, predictions, group splits, errors and baseline scores. |
| 3: Test the contribution and prepare release | Evaluate a checker for measurement definitions and source identity on protected systems and paraphrases; run ablations and uncertainty estimates. Prepare the paper, repository and dataset documentation. | A ZIP with reproducible evaluation, figures, tables, limitations and manuscript/release materials. |

Only Phase 1 scripts are included now. Each subsequent package will be prepared after we inspect the preceding results. No language-model or paid API calls run in this package.

## Phase 1 decisions

- Primary pair: an official initial configuration and its own UMA-relaxed final structure. This measures change during relaxation; it is not a comparison between independently reproduced workflows.
- Geometry: mobile-atom coordinate RMSD, adsorbate coordinate RMSD in the stored slab frame, and rigid-aligned internal adsorbate RMSD. Each uses explicit atom indices, periodic rules and alignment conventions.
- Controls: translate the adsorbate in a saved final structure by 0.7 angstrom along stored x, recompute the geometry, and omit physical energy/force/convergence claims for that artificial structure.
- Selection is frozen before model inference. Nonconverged calculations, changed topology and ambiguous geometry remain visible as exclusions or diagnostics. Do not select replacements after inspecting language-model errors.
- Bond graphs are provisional distance-based hypotheses. Review them and coordinate overlays before accepting the scientific dataset.
- All 20 systems and their variants belong to pilot development. They are not the final protected test set. Twenty groups cannot support a definitive model ranking.

Before Phase 2 we will inspect coverage, convergence, topology, contrast cases, label balance and template shortcuts. If too few systems are usable, we will revise the documented protocol and rerun Phase 1. A diagnostic ZIP is a valid return for review, not evidence that this gate has passed.

## Contribution and limits

Related scientific claim-verification work exists. The proposed contribution is a coordinate-derived evaluation and a tested method for checking the meaning and origin of a measurement. Using UMA and OC20-Dense alone does not establish novelty.

The initial claim templates are intentionally transparent feasibility checks. Field-name matching and threshold arithmetic may solve them. Phase 2 must add realistic ambiguity, matched controls and strong simple baselines before attributing performance to scientific reasoning.

UMA has OC20 training-domain connections. This project does not establish unseen-chemistry prediction, new DFT accuracy, global-minimum discovery or a better catalyst. The initial archive contains starting coordinates, not matched DFT final geometries. UMA total energies and stored adsorption energies cannot be compared without compatible references.

Any publication claim will depend on the reviewed results and the final comparison with related work. The intended deliverable is a reproducible research project with a clear question, auditable evidence and an evaluated contribution.
