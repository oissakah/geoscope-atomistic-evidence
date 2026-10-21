#!/usr/bin/env bash
set -Eeuo pipefail
[[ -n "${SLURM_JOB_ID:-}" ]] || { printf 'Use bash phase2_pilot/start_phase2.sh to submit the compute jobs.\n' >&2; exit 1; }
P2_DIR="${GEOMSCOPE_P2_DIR:?}"
BASE_DIR="${GEOMSCOPE_P2_BASE:?}"
ENV_PREFIX="$P2_DIR/.env"
export CONDA_PKGS_DIRS="$BASE_DIR/cache/phase2_conda_pkgs"
export PIP_DISABLE_PIP_VERSION_CHECK=1
mkdir -p -- "$CONDA_PKGS_DIRS"
if type module >/dev/null 2>&1; then
    module purge
    module load anaconda
fi
command -v conda >/dev/null 2>&1 || { printf 'Conda unavailable; inspect the anaconda module.\n' >&2; exit 1; }
if [[ ! -e "$ENV_PREFIX" ]]; then
    conda create --yes --override-channels --channel conda-forge --prefix "$ENV_PREFIX" python=3.12 pip
    conda run --no-capture-output --prefix "$ENV_PREFIX" python -m pip install \
        'torch==2.13.0' --index-url https://download.pytorch.org/whl/cu126
    conda run --no-capture-output --prefix "$ENV_PREFIX" python -m pip install \
        'torch==2.13.0' 'transformers==5.3.0' 'accelerate==1.12.0' 'numpy==2.3.5'
else
    printf 'Checking the existing Phase 2 environment without replacing it.\n'
fi
"$ENV_PREFIX/bin/python" -m pip check
"$ENV_PREFIX/bin/python" - <<'PY'
import sys
from importlib.metadata import version
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
assert sys.version_info[:2] == (3, 12), sys.version
for package, wanted in [('transformers','5.3.0'),('accelerate','1.12.0'),('numpy','2.3.5')]:
    actual=version(package)
    print(package, actual)
    assert actual == wanted, (package, actual)
assert torch.__version__.split('+')[0] == '2.13.0'
assert torch.version.cuda == '12.6'
print('Phase 2 software imports passed; GPU execution will be checked in model jobs.')
PY
"$ENV_PREFIX/bin/python" -m pip freeze
