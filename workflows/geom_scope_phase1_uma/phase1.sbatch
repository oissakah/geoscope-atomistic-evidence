#!/usr/bin/env bash
#SBATCH --job-name=geom-uma-phase1
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --constraint=gpu_l40s
#SBATCH --time=02:00:00
#SBATCH --output=logs/phase1-%j.log

# Edit the constraint above only if your Swan allocation uses another GPU type.
set -Euo pipefail
PACKAGE_DIR="${GEOMSCOPE_PACKAGE_DIR:-${SLURM_SUBMIT_DIR:?}}"
cd -- "$PACKAGE_DIR" || exit 1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export PYTHONUNBUFFERED=1
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || true
fi
"$PACKAGE_DIR/.env/bin/python" "$PACKAGE_DIR/run_phase1.py" run \
    --config "${GEOMSCOPE_CONFIG:-$PACKAGE_DIR/config/pilot.json}" \
    --output-root "${GEOMSCOPE_OUTPUT_ROOT:-$PACKAGE_DIR/results}" \
    --cache-dir "${GEOMSCOPE_CACHE:-$PACKAGE_DIR/cache}" \
    --run-id "${GEOMSCOPE_RUN_ID:?Use bash start_phase1.sh to supply a shared run ID.}"
stage_status=$?
printf '\nGPU stage exit status: %s\nThe collector will attempt to package the run, including failures.\n' "$stage_status"
exit "$stage_status"
