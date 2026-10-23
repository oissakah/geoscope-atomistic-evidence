# Swan OCK — copy/paste runbook

Upload `GeoScope_Phase4_v1_7_2_OC20_confidence_testfix.zip` to `/lustre/work/ock/oissakah10`.

```bash
cd /lustre/work/ock/oissakah10
unzip -o GeoScope_Phase4_v1_7_2_OC20_confidence_testfix.zip
cd GeoScope_Phase4_v1_7_OC20_confidence
cat VERSION
source hpc/common_env.sh
python3 -m unittest discover -s tests -v
bash hpc/prepare_confidence.sh
bash hpc/check_environment.sh
bash hpc/submit_confidence_small.sh
squeue -u "$USER"
```

The 36 small-model tasks run at most two at a time. After they finish, submit the large model (12 tasks, one at a time):

```bash
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_7_OC20_confidence
source hpc/common_env.sh
bash hpc/submit_confidence_large.sh
squeue -u "$USER"
```

After all jobs finish:

```bash
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_7_OC20_confidence
source hpc/common_env.sh
squeue -u "$USER"
bash hpc/collect_confidence.sh
ls -lh /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_7_CONFIDENCE_results_*.zip
```

Upload the resulting ZIP here. If a job fails, collect the partial results and logs anyway. No gold information goes to the GPU. Offline scoring uses separately sealed v1.6 analysis via

```bash
python3 hpc/analyze_confidence.py RESULTS_v1_7.zip GeoScope_Phase4_v1_6_FOURMODEL_EXTERNAL_ANALYSIS.zip --out offline_scoring
```

All scripts stop on data drift or unavailable environments and reuse the **virtualenv entry-point path rather than resolving symlinks**.

## v1.7.1 repair of early AssertionError
If v1.7.0 printed `SMALL ENV: ... transformers 5.3.0` then failed on
`AssertionError`, overwrite existing project with the v1.7.1 ZIP and rerun the
environment test. A CPython `sys.prefix` equality is **not a model-environment
validity test** in this HPC configuration. Installed packages and executable paths
remain checked. No GPU submission was made by the failed check.

## v1.7.2 fix for Swan Python `/usr/bin/python3`
Install v1.7.2 in the existing project directory and rerun the tests. The
regression test no longer launches `/usr/bin/python3` to mock model runtimes;
it uses the unit-test runner and simulates equal prefixes in a wrapper. The
production environment preflight and scientific code were not changed.


## v1.7.3 — Qwen3-32B missing Python.h recovery

The supplied 2026-10-23 results have 4,608 exact confidence replays and **zero 32B** replays. All 12 `geo_conf_large_18605439_*` logs report `fatal error: Python.h: No such file or directory` from a Triton CUDA-helper GCC build. This package adds a diagnostic/preflight but cannot guarantee headers exist on your Swan node.

Upload/install this zip over `GeoScope_Phase4_v1_7_OC20_confidence`, verify Python and test suite, then submit **only a 32B pilot**:

```bash
cd /lustre/work/ock/oissakah10
unzip -o GeoScope_Phase4_v1_7_3_OC20_confidence_python_headers.zip
cd GeoScope_Phase4_v1_7_OC20_confidence
cat VERSION
source hpc/common_env.sh
python3 -m unittest discover -s tests -v
bash hpc/prepare_confidence.sh
bash hpc/check_environment.sh
bash hpc/submit_confidence_large_pilot.sh
squeue -u "$USER"
```

The GPU batch script now sources `hpc/require_python312_headers.sh`. If `Python.h` is installed under a supported nonstandard path, export `GEOSCOPE_PY312_INCLUDE=/actual/path/to/include/python3.12` **before submitting** so Slurm passes it through `--export=ALL`. It must belong to the same Python 3.12 minor version as the 32B interpreter; do not use Python 3.9 or 3.11 headers. If the preflight cannot find working headers, the pilot fails early with diagnostic text. Ask Swan/HCC for installed Python 3.12 development headers or a sanctioned Python-3.12 environment with headers; do not reinstall model weights.

After pilot task completes, check the newest `outputs/logs/geo_conf_large_<job>_0.out`, and, if shard 0 has **128 exact replay** confidence outputs, submit remaining tasks:

```bash
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_7_OC20_confidence
source hpc/common_env.sh
bash hpc/submit_confidence_large_remainder.sh
squeue -u "$USER"
```

After all finish: `bash hpc/collect_confidence.sh` and upload the new `GeoScope_Phase4_v1_7_CONFIDENCE_results_*.zip`.

## v1.7.4: Corrected pilot (after 18605603 path failure)

Upload `GeoScope_Phase4_v1_7_4_OC20_confidence_slurm_pathfix.zip` into `/lustre/work/ock/oissakah10`. It overlays the existing `GeoScope_Phase4_v1_7_OC20_confidence` directory without deleting the 4,608 saved small-model confidence records. Then:

```bash
cd /lustre/work/ock/oissakah10
unzip -o GeoScope_Phase4_v1_7_4_OC20_confidence_slurm_pathfix.zip
cd GeoScope_Phase4_v1_7_OC20_confidence
cat VERSION
source hpc/common_env.sh
python3 -m unittest discover -s tests -v
bash hpc/prepare_confidence.sh
bash hpc/check_environment.sh
bash hpc/submit_confidence_large_pilot.sh
squeue -u "$USER"
```

After the pilot has *finished* (not while it is pending/running), check its job log:

```bash
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_7_OC20_confidence
ls -lt outputs/logs/geo_conf_large_*.out | head
# Use the latest pilot job ID from the submit output, then:
# tail -n 120 outputs/logs/geo_conf_large_JOBID_0.out
```

The pilot now reaches `hpc/require_python312_headers.sh`. If it prints `STOP: Python 3.12 development headers cannot be compiled`, its next solution is a compatible 3.12 header installation or documented HCC-provided module. Do not skip the header gate. If the pilot saves exactly 128 exact-replay confidence scores, submit the remainder:

```bash
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_7_OC20_confidence
source hpc/common_env.sh
bash hpc/submit_confidence_large_remainder.sh
squeue -u "$USER"
```

After the remaining 11 shards complete, run `bash hpc/collect_confidence.sh` and upload the results ZIP.
