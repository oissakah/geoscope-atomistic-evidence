#!/usr/bin/env bash
#SBATCH --job-name=geom-uma-continue
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --constraint=gpu_l40s
#SBATCH --time=01:00:00
#SBATCH --output=logs/phase1-%j.log

set -Euo pipefail
cd -- "${GEOMSCOPE_CONTINUE_DIR:?Use bash phase1_continue/start_continue.sh}" || exit 1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export PYTHONUNBUFFERED=1
export HF_HUB_OFFLINE=1
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || true
fi
"${GEOMSCOPE_BASE_DIR:?}/.env/bin/python" continue_phase1.py run \
    --parent-zip "${GEOMSCOPE_PARENT_ZIP:?}" \
    --output-root "${GEOMSCOPE_CONTINUE_OUTPUT:?}" \
    --run-id "${GEOMSCOPE_CONTINUE_ID:?}"
result=$?
printf '\nContinuation exit status: %s\n' "$result"
exit "$result"
