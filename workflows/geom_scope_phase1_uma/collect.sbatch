#!/usr/bin/env bash
#SBATCH --job-name=geom-uma-collect
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=logs/collect-%j.log

set -Euo pipefail
PACKAGE_DIR="${GEOMSCOPE_PACKAGE_DIR:-${SLURM_SUBMIT_DIR:?}}"
cd -- "$PACKAGE_DIR" || exit 1
export PYTHONUNBUFFERED=1
"$PACKAGE_DIR/.env/bin/python" "$PACKAGE_DIR/run_phase1.py" collect \
    --config "${GEOMSCOPE_CONFIG:-$PACKAGE_DIR/config/pilot.json}" \
    --output-root "${GEOMSCOPE_OUTPUT_ROOT:-$PACKAGE_DIR/results}" \
    --cache-dir "${GEOMSCOPE_CACHE:-$PACKAGE_DIR/cache}" \
    --run-id "${GEOMSCOPE_RUN_ID:?Use bash start_phase1.sh to supply a shared run ID.}"
stage_status=$?
printf '\nCollection exit status: %s\nInspect the ZIP location and status printed above.\n' "$stage_status"
exit "$stage_status"
