#!/usr/bin/env bash
# Installation belongs in a compute allocation, never on a login node.
set -Eeuo pipefail
if [[ -z "${SLURM_JOB_ID:-}" ]]; then
    printf 'Submit setup from the package directory with: sbatch setup.sbatch\n' >&2
    exit 1
fi
PACKAGE_DIR="${GEOMSCOPE_PACKAGE_DIR:-${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)}}"
cd -- "$PACKAGE_DIR"
ENV_PREFIX="$PACKAGE_DIR/.env"
CACHE_DIR="${GEOMSCOPE_CACHE:-$PACKAGE_DIR/cache}"
mkdir -p -- "$PACKAGE_DIR/logs" "$CACHE_DIR/conda_pkgs"
export CONDA_PKGS_DIRS="$CACHE_DIR/conda_pkgs"
export PIP_DISABLE_PIP_VERSION_CHECK=1
exec > >(tee -a "$PACKAGE_DIR/logs/setup-${SLURM_JOB_ID}.log") 2>&1
if type module >/dev/null 2>&1; then
    module purge
    module load anaconda
fi
if ! command -v conda >/dev/null 2>&1; then
    printf 'Conda is unavailable. Inspect the anaconda module configuration on Swan.\n' >&2
    exit 1
fi
printf 'Setting up the Phase 1 environment at %s\n' "$ENV_PREFIX"
if [[ -e "$ENV_PREFIX" ]]; then
    printf 'The environment already exists. Checking it without overwriting it.\n'
else
    conda create --yes --override-channels --channel conda-forge --prefix "$ENV_PREFIX" python=3.12 pip
    conda run --no-capture-output --prefix "$ENV_PREFIX" python -m pip install \
        'torch==2.13.0' --index-url https://download.pytorch.org/whl/cu126
    conda run --no-capture-output --prefix "$ENV_PREFIX" python -m pip install \
        'fairchem-core==2.23.0' 'ase==3.27.0' 'numpy==2.3.5' 'scipy==1.16.3' 'torch==2.13.0'
fi
"$ENV_PREFIX/bin/python" -m pip check
"$ENV_PREFIX/bin/python" - <<'PY'
from importlib.metadata import version
import sys
import torch
import fairchem.core

assert sys.version_info[:2] == (3, 12), sys.version
expected = {"fairchem-core": "2.23.0", "ase": "3.27.0", "numpy": "2.3.5", "scipy": "1.16.3"}
for name, wanted in expected.items():
    actual = version(name)
    print(name + ": " + actual)
    assert actual == wanted, (name, actual, wanted)
print("torch:", torch.__version__)
print("bundled CUDA:", torch.version.cuda)
assert torch.__version__.split("+")[0] == "2.13.0"
assert torch.version.cuda == "12.6", torch.version.cuda
print("Environment imports validated. GPU availability is checked in the GPU job.")
PY
[[ -x "$ENV_PREFIX/bin/hf" ]] || { printf 'The hf CLI is missing; setup is incomplete.\n' >&2; exit 1; }
conda run --prefix "$ENV_PREFIX" python -m pip freeze > "$PACKAGE_DIR/logs/setup-packages-${SLURM_JOB_ID}.txt"
printf '\nSetup complete. Accept the facebook/UMA access terms, then run:\n'
printf '  .env/bin/hf auth login\n  bash start_phase1.sh\n'
