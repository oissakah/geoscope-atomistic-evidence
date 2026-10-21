#!/usr/bin/env bash
#SBATCH --job-name=geom-uma-prepare
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=logs/prepare-%j.log

set -Euo pipefail
PACKAGE_DIR="${GEOMSCOPE_PACKAGE_DIR:-${SLURM_SUBMIT_DIR:?}}"
cd -- "$PACKAGE_DIR" || exit 1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
"$PACKAGE_DIR/.env/bin/python" "$PACKAGE_DIR/run_phase1.py" prepare \
    --config "${GEOMSCOPE_CONFIG:-$PACKAGE_DIR/config/pilot.json}" \
    --output-root "${GEOMSCOPE_OUTPUT_ROOT:-$PACKAGE_DIR/results}" \
    --cache-dir "${GEOMSCOPE_CACHE:-$PACKAGE_DIR/cache}" \
    --run-id "${GEOMSCOPE_RUN_ID:?Use bash start_phase1.sh to supply a shared run ID.}"
stage_status=$?
printf '\nPreparation exit status: %s\n' "$stage_status"
exit "$stage_status"
