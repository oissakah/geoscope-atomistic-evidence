# GeoScope v1.5.2 — Swan external-validation source and benchmark freeze

Run all commands from `/lustre/work/ock/oissakah10`. Upload the v1.5.2 ZIP there. The exact project folder is **the same** as v1.5.1, so existing outputs remain available; new source archive and logs use different names.

```bash
cd /lustre/work/ock/oissakah10
unzip -o GeoScope_Phase4_v1_5_2_OC20_IS2RES_external_gate.zip
cd GeoScope_Phase4_v1_5_OC20_external_gate
cat VERSION
source hpc/common_env.sh
source hpc/use_cpu_env.sh
python3 -m unittest discover -s tests -v
```

## Download the correct dataset on an HCC CPU job
The old `s2ef_val_ood_both.tar` is deliberately **not used**; preserve it. The new tar is approximately 4.4GB. The download script checks the published MD5 and writes to a distinct path. On Swan:

```bash
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_5_OC20_external_gate
bash hpc/submit_download_oc20.sh
squeue -u "$USER"
```

On restricted network nodes, obtain the file from the official URL on your computer and transfer via `swan-xfer.unl.edu` to `/lustre/work/ock/oissakah10/GeoScope_OC20_source/is2res_val_ood_both_trajectories.tar`. Transfer server is not an interactive login shell. Before auditing, verify locally on Swan:

```bash
md5sum /lustre/work/ock/oissakah10/GeoScope_OC20_source/is2res_val_ood_both_trajectories.tar
# expected: bc74b6474a13542cc56eaa97bd51adfc
```

## CPU-only geometry/identity gate
After the download job completed successfully:

```bash
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_5_OC20_external_gate
source hpc/common_env.sh
bash hpc/submit_oc20_source_audit.sh
squeue -u "$USER"
```

Once CPU audit has **COMPLETED**, inspect `outputs/external_oc20_source/SOURCE_GATE_STATUS.json` and `outputs/external_oc20_source/eligibility_counts_PRESELECTION.json`; failed cases remain enumerated. If 48 eligible source systems were admitted and you have access to the pinned reference checkout, prepare a sealed benchmark (CPU only):

```bash
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_5_OC20_external_gate
source hpc/common_env.sh
bash hpc/build_external_benchmark.sh
bash hpc/collect_external_gate.sh
ls -lh /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_5_OC20_external_gate_results_*.zip
```

Upload the newest results ZIP here. **Do not run GPUs until the external source and sealed benchmark have been reviewed.** The exact intended public case count is determined by the frozen benchmark constructor; do not invent it. If CPU audit stops on data incompatibilities, collect and upload logs and the partial gate inventory instead.
