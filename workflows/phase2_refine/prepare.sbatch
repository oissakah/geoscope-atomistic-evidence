#!/usr/bin/env bash
#SBATCH --job-name=geom-p2-prepare
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/prepare-%j.log
set -Eeuo pipefail
cd -- "${GEOMSCOPE_P2_DIR:?}" 
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
bash setup_phase2.sh
"$GEOMSCOPE_P2_BASE/phase2_pilot/.env/bin/python" run_phase2.py prepare \
    --parent-zip "${GEOMSCOPE_P2_PARENT:?}" --run-id "${GEOMSCOPE_P2_ID:?}" \
    --output-root "${GEOMSCOPE_P2_OUTPUT:?}" --cache-dir "${GEOMSCOPE_P2_CACHE:?}"
