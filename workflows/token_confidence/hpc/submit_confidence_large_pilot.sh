#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -f hpc/require_python312_headers.sh && -f hpc/run_confidence_large.sbatch ]] || {
 echo 'STOP: v1.7.4 helper files absent; install the corrected ZIP before submitting.' >&2
 exit 31
}
source hpc/check_environment.sh
bash hpc/prepare_confidence.sh
sinfo -h -p ock -o '%P' | grep -Eq '^ock\*?$' || { echo 'OCK unavailable' >&2; exit 2; }
mkdir -p outputs/logs outputs/confidence/qwen32b
export PHASE4_DIR="$PWD"
# Only one shard until the Python.h + vLLM compilation is verified on an OCK node.
sbatch --partition=ock --array=0 --export=ALL hpc/run_confidence_large.sbatch
squeue -u "$USER"
