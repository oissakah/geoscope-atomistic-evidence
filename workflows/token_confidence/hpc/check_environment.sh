#!/usr/bin/env bash
set -Eeuo pipefail
# BASH_SOURCE[0] identifies this file even when sourced by a copied SLURM script.
# $0 identifies the caller (often /var/spool/slurmd/job.../slurm_script)
# and previously changed cwd away from the project during GPU jobs.
_geoscope_env_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$_geoscope_env_root"
unset _geoscope_env_root
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
PARENT="${GEOSCOPE_V16_PARENT:-/lustre/work/ock/oissakah10/GeoScope_Phase4_v1_6_OC20_fourmodel_GPU}"
if [[ ! -f "$PARENT/outputs/small_environment.sh" || ! -f "$PARENT/outputs/large_environment.sh" ]];then
  echo 'STOP: Previous v1.6 small and large environment files are required.' >&2;exit 10
fi
source "$PARENT/outputs/small_environment.sh"
source "$PARENT/outputs/large_environment.sh"
[[ -x "$GEOSCOPE_GPU_PYTHON" && -x "$LARGE_GPU_PYTHON" && -f "$MODEL_MANIFEST" ]] || { echo 'STOP: One or more GPU Python entrypoints/model manifest are missing or not executable.' >&2; exit 11; }
"$GEOSCOPE_GPU_PYTHON" - <<'PY_SMALL'
import sys,importlib.metadata as md
from transformers import AutoTokenizer,AutoModelForCausalLM
import torch
print('SMALL ENV:',sys.executable,'torch',md.version('torch'),'transformers',md.version('transformers'),'prefix',sys.prefix,'base_prefix',sys.base_prefix,flush=True)
assert md.version('transformers')=='5.3.0', 'Wrong small-model Transformers version'
PY_SMALL
"$LARGE_GPU_PYTHON" - <<'PY_LARGE'
import sys,importlib.metadata as md
from vllm import LLM,SamplingParams
from transformers import AutoTokenizer
import torch
print('LARGE ENV:',sys.executable,'vllm',md.version('vllm'),'transformers',md.version('transformers'),'prefix',sys.prefix,'base_prefix',sys.base_prefix,flush=True)
assert md.version('vllm')=='0.11.2', 'Wrong large-model vLLM version'
PY_LARGE
printf 'ENVIRONMENTS CHECKED: pinned imports/versions verified (Python installation prefix is diagnostic only). No weights loaded.\n'
