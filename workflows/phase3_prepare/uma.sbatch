#!/usr/bin/env bash
#SBATCH --job-name=geom-p3-uma
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --constraint=gpu_l40s
#SBATCH --time=04:00:00
#SBATCH --output=logs/uma-%j.log
set -Euo pipefail
cd -- "${GEOMSCOPE_P3_DIR:?}" || exit 1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
export HF_HUB_OFFLINE=1
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || true
fi
"${GEOMSCOPE_P3_BASE:?}/.env/bin/python" run_phase3.py run --batch-index "${1:?Missing batch index}" \
    --run-id "${GEOMSCOPE_P3_ID:?}" --refinement-zip "${GEOMSCOPE_P3_REFINEMENT:?}" \
    --geometry-zip "${GEOMSCOPE_P3_GEOMETRY:?}" --output-root "${GEOMSCOPE_P3_OUTPUT:?}" \
    --cache-dir "${GEOMSCOPE_P3_CACHE:?}"
result=$?
printf '\nUMA batch exit status: %s\n' "$result"
exit "$result"
