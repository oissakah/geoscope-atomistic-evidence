#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
command -v sinfo >/dev/null && sinfo -h -p ock -o '%P' | grep -Eq '^ock\*?$' || { echo 'OCK not visible';exit 2; }
grep -qx '#SBATCH --partition=ock' hpc/run_large_external.sbatch || exit 3
bash hpc/prepare_large.sh
mkdir -p outputs/logs outputs/gpu/qwen32b
export PHASE4_DIR="$PWD"
sbatch --partition=ock --export=ALL hpc/run_large_external.sbatch
squeue -u "$USER"
