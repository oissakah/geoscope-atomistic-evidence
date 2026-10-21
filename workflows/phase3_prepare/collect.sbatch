#!/usr/bin/env bash
#SBATCH --job-name=geom-p3-collect
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=logs/collect-%j.log
set -Euo pipefail
cd -- "${GEOMSCOPE_P3_DIR:?}" || exit 1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
"${GEOMSCOPE_P3_BASE:?}/.env/bin/python" run_phase3.py collect \
    --run-id "${GEOMSCOPE_P3_ID:?}" --refinement-zip "${GEOMSCOPE_P3_REFINEMENT:?}" \
    --geometry-zip "${GEOMSCOPE_P3_GEOMETRY:?}" --output-root "${GEOMSCOPE_P3_OUTPUT:?}" \
    --cache-dir "${GEOMSCOPE_P3_CACHE:?}"
result=$?
printf '\nCollection exit status: %s\n' "$result"
exit "$result"
