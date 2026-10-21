# Data card

## Purpose

Evaluate whether an LLM selects a measurement and operation that actually establish an atomistic RMSD claim. The benchmark separates comparison identity, physical definition, numerical entailment and scientific insufficiency. It is not a catalyst-screening dataset or a measure of chemical ground-truth accuracy.

## Sources and splits

Official OC20-Dense structures supply initial atomic configurations. UMA `uma-s-1p2p1` at the pinned checkpoint supplies relaxed endpoints. Original source members, selections and checkpoint hashes are preserved in the parent artifacts. Development comprises 20 source groups. The new source-preparation pool contains 60 disjoint groups, of which 55 pass the declared convergence and unchanged-adsorbate-graph gates.

The five exclusions remain in provenance: two nonconverged endpoints and three converged endpoints with changed graphs. No replacement was selected. All five involve C2H3O2. Sixteen accepted endpoints retain descriptive chemical flags. Review `audits/phase3_source_review.md` for exact identities, conventions and limitations.

The 55 accepted groups each have one real initial/final comparison and one synthetic control, translating only the adsorbate by +0.7 angstrom in stored x. Controls carry no energy, force or convergence claim. They supply other-comparison distractors in the final packets.

## Construction and annotations

There are 880 base cases with two presentations each: 1,760 variants. Every source has 32 variants, and no final cases are skipped. The labels are 550 supported, 550 contradicted and 660 insufficient. Gold proofs enumerate all licensed single-measurement evidence/operation witnesses: 660 cases have no decisive proof, 918 have one and 182 have two.

The three metric definitions are mobile-atom coordinate RMSD, adsorbate RMSD in the same frame, and internal adsorbate RMSD after graph-based unwrapping and proper rigid alignment. Equal weights, atom correspondence, masks and periodic conventions are explicit. With the adsorbate a strict subset of mobile atoms, same-frame RMSD permits the supplied subset bounds. Independently minimum-imaged frame RMSD does not generally bound rigid-aligned internal RMSD; no such relation is licensed.

Structured and report payloads carry equivalent numerical facts. Report rendering also omits redundant metric names, so presentation comparisons mix formatting and explicit-label redundancy. Gold labels, source-group metadata, true/synthetic origin and raw source identities are outside model payloads. The gold filename is a release artifact; it was not sent to inference.

## Recorded evaluation

Three fixed compact models each make independent direct-answer and evidence-selection requests for every variant. There are 10,560 unique first attempts. Greedy BF16/SDPA inference uses batch two, seed 20261021, a 6,144-token input limit without input truncation, and at most 160 new tokens. SmolLM extended thinking is disabled, and the template date is fixed. Model revisions, weight hashes, software, prompt hashes, token hashes and request identities are recorded.

All requests are present. SmolLM has 258 truncated direct outputs and three truncated selections. Malformed, truncated and failed responses retain their denominators. The frozen parser removes only a permitted whole-output fence and whitespace, with no answer repair or prefix extraction. Scientific insufficiency is scored for direct/oracle responses; rejection in a selection pipeline is a separate outcome.

## Statistical unit and allowed claims

Source groups are the resampling unit. The 1,760 variants are correlated. The protocol was fixed after development and geometry-only source review, before final model outputs. It was not externally preregistered. These are same-dataset groups; no chemical-family, UMA-training independence or general frontier-model comparison is established.

The deterministic public-payload solver is perfect on this controlled family. Full checking is a selective proof filter whose conditional safety follows the declared rules. Report answerable coverage, accepted proof correctness, invalid/missing fractions and scientific-insufficiency handling beside any safety result.

## Distribution

The original final ZIP is included unchanged. It contains all cases, gold proofs, raw model text, scores and trace metadata. Original structural trajectories and development archives are retained as separately hashed parent artifacts rather than duplicated here. Preserve source acknowledgments and upstream terms; model weights are not included. See `THIRD_PARTY_NOTES.md`.
