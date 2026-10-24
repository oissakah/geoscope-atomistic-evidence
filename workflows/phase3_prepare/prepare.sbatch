#!/usr/bin/env bash
#SBATCH --job-name=geom-p3-prepare
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/prepare-%j.log
set -Eeuo pipefail
cd -- "${GEOMSCOPE_P3_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
PYTHON_PATH="${GEOMSCOPE_P3_BASE:?}/.env/bin/python"
"$PYTHON_PATH" - <<'PY'
from importlib.metadata import version
import sys,torch
assert sys.version_info[:2]==(3,12)
for name,wanted in [('fairchem-core','2.23.0'),('ase','3.27.0'),('numpy','2.3.5')]:
    actual=version(name)
    assert actual==wanted,(name,actual,wanted)
assert torch.__version__.split('+')[0]=='2.13.0'
assert torch.version.cuda=='12.6'
print('Previously working UMA environment verified; no installation requested.')
PY
"$PYTHON_PATH" run_phase3.py prepare --run-id "${GEOMSCOPE_P3_ID:?}" \
    --refinement-zip "${GEOMSCOPE_P3_REFINEMENT:?}" --geometry-zip "${GEOMSCOPE_P3_GEOMETRY:?}" \
    --output-root "${GEOMSCOPE_P3_OUTPUT:?}" --cache-dir "${GEOMSCOPE_P3_CACHE:?}"
