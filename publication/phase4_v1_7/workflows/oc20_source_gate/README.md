# GeoScope Phase 4 v1.5.2 — true external OC20 source gate

**Critical correction:** `s2ef_val_ood_both.tar` is 200 sharded extxyz.xz files containing one frame per many DIFFERENT systems; it must NOT be treated as one trajectory per file. The uploaded v1.5.1 inventory conclusively established this. The v1.5.2 package uses the OC20 **IS2RE/IS2RS** `val_ood_both` relaxation trajectories, one `.extxyz.xz` per official system ID. Source: https://github.com/facebookresearch/fairchem/blob/main/docs/catalysts/datasets/oc20.md .

The existing S2EF tar stays on Swan for provenance; it is not used by the new parser. The new archive is about 4.4 GB compressed and must match MD5 `bc74b6474a13542cc56eaa97bd51adfc`. A new CPU-only job downloads it in a separate filename. The source gate checks 48 eligible systems, atom identity, tags/anchors, PBC, cell, bond connectivity, and computes frame/internal RMSD via the unchanged v1.1 physical methods. All rejections are reported. No inference is permitted until source gate and benchmark freeze are reviewed.

See `HPC_RUNBOOK.md` for full Swan commands. Independent-source does not guarantee unseen language-model pretraining data. No benchmark exists until a real CPU run completes and its results are reviewed.
