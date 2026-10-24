#!/usr/bin/env bash
#SBATCH --job-name=geo-conf-32
#SBATCH --partition=ock
#SBATCH --gres=gpu:1
#SBATCH --constraint=gpu_l40s
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=04:00:00
#SBATCH --array=0-11%1
#SBATCH --output=outputs/logs/geo_conf_large_%A_%a.out
set -Eeuo pipefail
: "${PHASE4_DIR:?Missing root}"
cd "$PHASE4_DIR"
# Use absolute paths: SLURM runs a copy of this script from /var/spool/slurmd.
[[ -f "$PHASE4_DIR/hpc/check_environment.sh" ]] || { echo 'STOP: environment helper missing from PHASE4_DIR' >&2; exit 31; }
[[ -f "$PHASE4_DIR/hpc/require_python312_headers.sh" ]] || { echo 'STOP: Python.h preflight helper missing from PHASE4_DIR' >&2; exit 32; }
source "$PHASE4_DIR/hpc/check_environment.sh"
source "$PHASE4_DIR/hpc/require_python312_headers.sh"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" PYTHONUNBUFFERED=1
"$LARGE_GPU_PYTHON" -m hpc.run_large_confidence --shard "${SLURM_ARRAY_TASK_ID:?Missing shard}"
