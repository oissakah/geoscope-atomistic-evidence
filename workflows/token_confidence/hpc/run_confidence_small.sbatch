#!/usr/bin/env bash
#SBATCH --job-name=geo-conf-sm
#SBATCH --partition=ock
#SBATCH --gres=gpu:1
#SBATCH --constraint=gpu_l40s
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --array=0-35%2
#SBATCH --output=outputs/logs/geo_conf_small_%A_%a.out
set -Eeuo pipefail
: "${PHASE4_DIR:?Missing root}"
cd "$PHASE4_DIR"
source hpc/check_environment.sh
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" PYTHONUNBUFFERED=1
idx="${SLURM_ARRAY_TASK_ID:?missing array id}"
if ((idx<12));then key=qwen;shard=$idx;elif ((idx<24));then key=phi;shard=$((idx-12));else key=smol;shard=$((idx-24));fi
"$GEOSCOPE_GPU_PYTHON" -m hpc.run_small_confidence --model "$key" --shard "$shard"
