#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
source hpc/check_environment.sh
bash hpc/prepare_confidence.sh
sinfo -h -p ock -o '%P' | grep -Eq '^ock\*?$' || { echo 'OCK unavailable' >&2;exit 2; }
mkdir -p outputs/logs outputs/confidence/qwen32b
export PHASE4_DIR="$PWD"
sbatch --partition=ock --export=ALL hpc/run_confidence_large.sbatch
squeue -u "$USER"
