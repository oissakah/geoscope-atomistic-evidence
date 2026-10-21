#!/usr/bin/env bash
#SBATCH --job-name=geom-p2-model
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
cd -- "${GEOMSCOPE_P2_DIR:?}" || exit 1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export PYTHONUNBUFFERED=1
export HF_HUB_OFFLINE=1
PYTHON_PATH="$GEOMSCOPE_P2_BASE/phase2_pilot/.env/bin/python"
[[ -x "$PYTHON_PATH" ]] || PYTHON_PATH="${GEOMSCOPE_P2_BASE:?}/.env/bin/python"
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || true
fi
"$PYTHON_PATH" run_phase2.py run --model-key "${1:?Missing model key}" \
    --parent-zip "${GEOMSCOPE_P2_PARENT:?}" --run-id "${GEOMSCOPE_P2_ID:?}" \
    --output-root "${GEOMSCOPE_P2_OUTPUT:?}" --cache-dir "${GEOMSCOPE_P2_CACHE:?}"
result=$?
printf '\nModel job exit status: %s\n' "$result"
exit "$result"
