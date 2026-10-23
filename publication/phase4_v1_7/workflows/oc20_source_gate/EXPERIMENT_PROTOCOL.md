# GeoScope Phase 4 v1.5.2 — Prospective external-source admission

## Post-inventory correction before external inference
The previously MD5-verified `s2ef_val_ood_both.tar` has 400 compressed files: 200 extxyz.xz SHARDS containing structures belonging to different physical systems, with 200 corresponding text files containing system IDs. Pairing shard endpoints would be a serious scientific error. Zero source pairs were admitted and no model observed this dataset. Replace the source with official OC20 IS2RE/IS2RS relaxation trajectories (`is2res_val_ood_both_trajectories.tar`, MD5 `bc74b6474a13542cc56eaa97bd51adfc`). The source comes from Open Catalyst Project; publication Chanussot et al., ACS Catalysis (2021), DOI 10.1021/acscatal.0c04525, CC BY 4.0.

## Frozen admission policy before model evaluation
1. Verify the entire new tar MD5 **before reading coordinates**; never reuse S2EF source files for endpoint pairs.
2. Index archive metadata (not decompressing 35 GB) for per-system `.extxyz.xz` files. Reject duplicate official system IDs from independent selection. Rank unique IDs via SHA256 of official ID and path without reading coordinates or model outputs.
3. Visit candidates in that fixed rank order and admit the **first 48 passing** geometry/identity checks; count all screening rejection reasons. This yields the 48 lowest source-identity ranks among eligible screened systems, without claiming the complete dataset-wide eligible population size. If exhausted with fewer than 48, STOP. Any debug/partial scan may not freeze.
4. For each candidate file, decompress only its own compressed extxyz trajectory with limits, iterate saved ASE frames, compare first and last frames of *that same official system*. Do not claim convergence or external experimental validation.
5. Require identical ordered atomic symbols, tag assignments and PBC; same cell tolerance; at least two adsorbate atoms with OC20 tag 2; fixed slab anchors tagged 0 (inferred unless original constraints explicitly stored) must actually remain stationary; reject if anchor drift exceeds frozen thresholds.
6. Compute direct/mobile/internal metrics using unchanged v1.1 physical functions: atom-matched minimum-image displacements; stable adsorbate bond graph; periodic unwrapping; proper Kabsch for internal RMSD. Reject disconnected graphs and nonfinite values.
7. Label one additional 0.35-A adsorbate translation as a **synthetic distractor**, never another real DFT trajectory. Record composition-cell chemistry clusters to support dependence-aware uncertainty estimates.
8. Import pinned original GeoScope benchmark/selector code commit `4932b4f574203d4d02689727dd7c6e5ed1fb7555`; generate 48-group benchmark in isolated `SEAL_OFFLINE` and only send PUBLIC requests to future GPU inference. Do not alter the 4-model baseline scoring rules based on these new answers.
9. Source distinctness = separately published OC20 (not ALCHEMI); exact structural non-overlap and LLM pretraining exposure are not verified. Do not overclaim external generalization beyond this source.

## Dataset and resources
Official source: https://dl.fbaipublicfiles.com/opencatalystproject/data/is2res_val_ood_both_trajectories.tar (approx. 4.4 GB compressed, up to 35 GB when fully extracted). The CPU reader does *not* extract the whole archive. No OCK GPU resources are required for source preparation. Prior S2EF tar is preserved but excluded.

## Known untested integration risks
The exact extxyz tag/constraint encoding, path layout, candidate acceptance rate and end-to-end runtime have not yet been checked against the 4.4GB tar in this environment. A live Swan run must verify them and may reveal incompatibilities. Treat any failure as an audit result, not a license to relax scientific rules.
