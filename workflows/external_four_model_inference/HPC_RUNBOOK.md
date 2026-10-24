# Swan OCK commands

```bash
cd /lustre/work/ock/oissakah10
unzip -o GeoScope_Phase4_v1_6_OC20_fourmodel_GPU.zip
cd GeoScope_Phase4_v1_6_OC20_fourmodel_GPU
cat VERSION
source hpc/common_env.sh
python3 -m unittest discover -s tests -v
bash hpc/prepare_external.sh
bash hpc/check_ock_partition.sh
bash hpc/submit_small.sh
bash hpc/submit_large.sh
squeue -u "$USER"
```

Requirements: the completed `GeoScope_Phase4_v1_3_ock_multimodel/outputs/gpu_environment.sh`, the completed `GeoScope_Phase4_v1_4_ock_qwen32b_awq/outputs/large_environment.sh`, corresponding immutable models, and original sealed v1.5.2 benchmark. The program explicitly reuses the existing environments; it does not reinstall packages or download models.

Run the submitters separately if you prefer to schedule GPU demand sequentially. Check job logs `outputs/logs/extsmall_*` and `outputs/logs/extlarge_*`.

After arrays have completed or if they fail:

```bash
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_6_OC20_fourmodel_GPU
source hpc/common_env.sh
squeue -u "$USER"
bash hpc/collect_external.sh
ls -lh /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_6_OC20_FOURMODEL_results_*.zip
```

Upload newest results ZIP for scientific scoring. The ZIP collector marks incomplete results explicitly and preserves logs.

## 32B resubmission after v1.6.0 import failure (v1.6.1)
Upload and unzip the v1.6.1 ZIP over the existing project. Re-execute `bash hpc/prepare_large.sh` to **regenerate** the corrected interpreter environment file (do not reuse the previous `outputs/large_environment.sh`); then `bash hpc/submit_large.sh`. The submission script performs the preflight again, and each GPU task first verifies the interpreter, virtual environment, Transformers, Torch and vLLM. The 1,536 questions, four-model benchmarking plan, and small-model outputs are unchanged. After jobs finish, `bash hpc/collect_external.sh` and upload the latest results archive.
