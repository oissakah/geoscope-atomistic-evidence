#!/usr/bin/env bash
#SBATCH --job-name=geo-ext-32
#SBATCH --partition=ock
#SBATCH --gres=gpu:1
#SBATCH --constraint=gpu_l40s
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=04:00:00
#SBATCH --array=0-11%1
#SBATCH --output=outputs/logs/extlarge_%A_%a.out
set -Eeuo pipefail
: "${PHASE4_DIR:?Missing root}"
cd "$PHASE4_DIR"
source outputs/large_environment.sh
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
# Fail immediately with a useful diagnostic if the preflight interpreter is not
# preserved into the compute-node batch environment. No model weights loaded.
"$LARGE_GPU_PYTHON" - <<'PY_PREFLIGHT'
import importlib.metadata as md
import json,sys,os
from pathlib import Path
root=Path(os.environ['PHASE4_DIR'])
report=json.loads((root/'outputs/large_preflight.json').read_text())
print('LARGE_BATCH_PYTHON:',sys.executable,'prefix:',sys.prefix,'base_prefix:',sys.base_prefix,flush=True)
if str(Path(sys.executable).absolute())!=str(Path(report['python']).absolute()):
    raise RuntimeError('Batch interpreter drift versus passed tokenizer preflight')
if sys.prefix==sys.base_prefix:
    raise RuntimeError('Batch Python escaped the dedicated large-model virtualenv')
from transformers import AutoTokenizer
import torch,vllm
assert md.version('vllm')==report['versions']['vllm'],'vLLM version drift'
print('LARGE_BATCH_ENVIRONMENT_PASS:',md.version('torch'),md.version('transformers'),md.version('vllm'),flush=True)
PY_PREFLIGHT
"$LARGE_GPU_PYTHON" -m hpc.run_large_external --shard "${SLURM_ARRAY_TASK_ID:?Missing shard}"
