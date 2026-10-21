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
cd -- "${GEOMSCOPE_CONTINUE_DIR:?Use bash phase1_continue/start_continue.sh}" || exit 1
export PYTHONUNBUFFERED=1
"${GEOMSCOPE_BASE_DIR:?}/.env/bin/python" continue_phase1.py collect \
    --parent-zip "${GEOMSCOPE_PARENT_ZIP:?}" \
    --output-root "${GEOMSCOPE_CONTINUE_OUTPUT:?}" \
    --run-id "${GEOMSCOPE_CONTINUE_ID:?}"
result=$?
printf '\nCollection exit status: %s\n' "$result"
exit "$result"
