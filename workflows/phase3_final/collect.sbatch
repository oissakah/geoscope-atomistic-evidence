#!/usr/bin/env bash
#SBATCH --job-name=geom-final-collect
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=logs/collect-%j.log
set -Euo pipefail
cd -- "${GEOMSCOPE_FINAL_DIR:?}" || exit 1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
# Collection is standard-library only and survives a broken LLM environment.
"${GEOMSCOPE_FINAL_BASE:?}/.env/bin/python" run_final.py collect \
    --run-id "${GEOMSCOPE_FINAL_ID:?}" --source-zip "${GEOMSCOPE_FINAL_SOURCE:?}" \
    --development-zip "${GEOMSCOPE_FINAL_DEVELOPMENT:?}" --output-root "${GEOMSCOPE_FINAL_OUTPUT:?}" \
    --cache-dir "${GEOMSCOPE_FINAL_CACHE:?}"
result=$?
printf '\nFinal collection exit status: %s\n' "$result"
exit "$result"
