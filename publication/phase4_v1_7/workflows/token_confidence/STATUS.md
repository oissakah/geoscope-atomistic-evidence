# Current status v1.7.3

- Qwen3-4B, Phi-4-mini, SmolLM3-3B token confidence: **1,536/1,536 each; exact replay 4,608/4,608** (the data is in the separately collected v1.7 confidence-results ZIP; this package does not overwrite it).
- Qwen3-32B token confidence: **0/1,536**, all 12 shards aborted during a Triton CUDA extension build. GPU log shows `fatal error: Python.h: No such file or directory`.
- This patch adds a **Python-3.12 development-header compiler preflight** before large-model loading, `CPATH` override for GCC, and a **single-shard 32B pilot** to prevent 12 repeated failures. The hardware, scientific benchmark, model/checkpoint, inference settings, logprobs, and scoring code are unchanged.
- Passing v1.7.2 environment-check imports does not test compile-time availability of Python.h. A header path visible in another environment may be used if it is **CPython 3.12**-compatible and can compile with GCC.
- On Swan: do **not** blindly submit the full 12 tasks; run the pilot first, inspect logs. If headers remain absent, ask HCC for an appropriate development-header environment or module.

## v1.7.4 pilot startup fix

The v1.7.3 pilot `18605603` aborted before the Python.h gate because `hpc/check_environment.sh` was **sourced** from SLURM's copied `/var/spool/slurmd/.../slurm_script`. The helper used `dirname "$0"`, which refers to that copied SLURM script rather than the sourced helper. It changed cwd away from the project and `source hpc/require_python312_headers.sh` failed with `No such file or directory`. This was a launcher defect, **not proof that Python.h exists or is missing**. The v1.7.4 package uses `BASH_SOURCE[0]`, absolute paths for both helpers, an early helper-existence guard, and a synthetic SLURM-spool regression test. The scientific protocol and checkpoint/model runners are unchanged. After installation, submit **only the 128-question pilot**. Do not run the remainder until the pilot proves exact replay and confidence capture.
