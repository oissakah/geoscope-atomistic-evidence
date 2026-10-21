#!/usr/bin/env bash
#SBATCH --job-name=geom-p2-collect
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=logs/collect-%j.log
set -Euo pipefail
cd -- "${GEOMSCOPE_P2_DIR:?}" || exit 1
export PYTHONUNBUFFERED=1
# Collection uses only the standard library and the already-working Python.
PYTHON_PATH="${GEOMSCOPE_P2_BASE:?}/.env/bin/python"
"$PYTHON_PATH" run_phase2.py collect \
    --parent-zip "${GEOMSCOPE_P2_PARENT:?}" --run-id "${GEOMSCOPE_P2_ID:?}" \
    --output-root "${GEOMSCOPE_P2_OUTPUT:?}" --cache-dir "${GEOMSCOPE_P2_CACHE:?}"
result=$?
printf '\nCollection exit status: %s\n' "$result"
exit "$result"
