#!/usr/bin/env bash
#SBATCH --job-name=geom-final-prepare
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/prepare-%j.log
set -Eeuo pipefail
cd -- "${GEOMSCOPE_FINAL_DIR:?}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1
PYTHON_PATH="${GEOMSCOPE_FINAL_BASE:?}/phase2_pilot/.env/bin/python"
"$PYTHON_PATH" - <<'PY'
import sys
from importlib.metadata import version
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
assert sys.version_info[:2]==(3,12)
for name,wanted in [('transformers','5.3.0'),('accelerate','1.12.0'),('numpy','2.3.5')]:
    actual=version(name)
    assert actual==wanted,(name,actual,wanted)
assert torch.__version__.split('+')[0]=='2.13.0'
assert torch.version.cuda=='12.6'
print('Existing language-model environment verified; no installation or download requested.')
PY
"$PYTHON_PATH" run_final.py prepare --run-id "${GEOMSCOPE_FINAL_ID:?}" \
    --source-zip "${GEOMSCOPE_FINAL_SOURCE:?}" --development-zip "${GEOMSCOPE_FINAL_DEVELOPMENT:?}" \
    --output-root "${GEOMSCOPE_FINAL_OUTPUT:?}" --cache-dir "${GEOMSCOPE_FINAL_CACHE:?}"
