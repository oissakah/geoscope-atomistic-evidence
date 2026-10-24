# One scientific investigation: GeoScope

## Research question

Can language models select atomistic measurements and mathematical operations that **physically justify** the scientific claim being made, and are these selections reliable when source collections, evidence presentations, and model configurations change?

This is **one physical-proof framework evaluated under complementary conditions**, not a claim that two experiments used identical protocols.

## One common scientific mechanism

A measurement is licensed evidence only if it refers to the required source comparison and has compatible physical metadata: selected atoms, coordinate frame, rigid alignment, periodic treatment, weights and permitted operation. The paper distinguishes mobile-atom RMSD (M), stored-frame adsorbate RMSD (A), and aligned internal RMSD (I). Same-frame subset bounds are permitted for M/A under matched conventions, but such bounds cannot simply be applied to I.

## Why two source collections are necessary

| Question | Evidence in unified paper | Original archived component |
|---|---|---|
| Do weaker checks let physically invalid proofs through? | 55-system UMA evaluation: arithmetic, comparison-ID and full-definition checks on the same model selections. | Frozen original Phase 3 research; see `FINAL_REPORT.md` and `analysis/`. |
| Does definition-aware verification reduce accepted coverage? | Rejections among 1,100 answerable questions and an explicit deterministic oracle baseline. | Frozen original Phase 3. |
| Is correct verdict equal to valid scientific proof? | Original direct-answer versus proof-aware scores, with scientific insufficiency separately evaluated. | Frozen original Phase 3. |
| Are movement and internal molecular deformation distinct? | Original aggregate findings and external 48-system coordinate audit. | Original physical definitions + external geometry audit. |
| Do evidence selection failures persist across another atomic source? | 48 external OC20 source systems; four LLMs and distinct strict/fence-normalized scoring. | Phase 4 v1.7 external evaluation. |
| Are these failures attributable to operation, evidence type, or presentation? | External error taxonomy, operation-only oracle diagnostic and matched presentation pairs. | Phase 4 v1.7 audits. |
| Can high token confidence certify physical validity? | Exact-response confidence replay, eligible-case AUROC, and highly confident invalid proofs. | Phase 4 v1.7 confidence study. |

## Editorial unification versus new analysis

- The paper's revised Figure 1 shows *two atomic source streams entering one physical-proof definition*, followed by study-specific analyses; it no longer presents chronological Phase 3/Phase 4 as independent projects.
- Original 55-system and external 48-system scoring **must not** be pooled. The former permits one enclosing JSON fence in its protocol; the latter reports strict JSON and a separate diagnostic that removes an enclosing Markdown fence.
- The external evaluation **did not repeat** the original comparison-ID versus full-definition ablation as a newly run matched experiment. Do not imply that the 81 additional Qwen invalid acceptances replicated on the external systems.
- The external 48 structures were qualified under predefined rules. `val_ood_both` is an OC20 split label; it does not establish independence from LLM pretraining.
- The deterministic oracle enumerates licensed proofs under complete benchmark rules. Operation-only repair is a retrospective upper-bound diagnostic, not an autonomous recovery tool.
- No claim has been made that this study optimized catalysts, selected an improved material, or increased autonomous laboratory throughput.

## Primary publication source

The canonical unified submission-draft sources live in `publication/phase4_v1_7/manuscript/`. The manuscript now compiles `sections/results_discussion.tex` rather than separate chronological Results and Discussion/Phase 4 files. Legacy sections are retained as archival provenance and are **not** active manuscript inputs.

Use `publication/phase4_v1_7/publication_figures` for the 17 numerical figure plots and 1 integrated framework diagram. The data-derived figures are not recomputed from invented raw atom coordinates. Follow the existing audits for provenance limits.

## Release checks and remaining work

After applying the unified manuscript update, run the original repository hash verification and original analysis before preparing a paper release. Also compile both LaTeX documents, verify figure placements and equation references, and confirm authorship between the main manuscript and Supplementary Information. Expert chemical review and missing parent artifacts in `FREEZE_AUDIT_STATUS.md` remain unresolved, independent of this editorial update.
