#!/usr/bin/env bash
#SBATCH --job-name=geom-final-model
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --constraint=gpu_l40s
#SBATCH --time=04:00:00
#SBATCH --output=logs/model-%j.log
set -Euo pipefail
cd -- "${GEOMSCOPE_FINAL_DIR:?}" || exit 1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || true
fi
"${GEOMSCOPE_FINAL_BASE:?}/phase2_pilot/.env/bin/python" run_final.py run --model-key "${1:?Missing model key}" \
    --run-id "${GEOMSCOPE_FINAL_ID:?}" --source-zip "${GEOMSCOPE_FINAL_SOURCE:?}" \
    --development-zip "${GEOMSCOPE_FINAL_DEVELOPMENT:?}" --output-root "${GEOMSCOPE_FINAL_OUTPUT:?}" \
    --cache-dir "${GEOMSCOPE_FINAL_CACHE:?}"
result=$?
printf '\nFinal model job exit status: %s\n' "$result"
exit "$result"
