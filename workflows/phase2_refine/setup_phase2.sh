#!/usr/bin/env bash
# Reuse the environment that completed all three model runs on Swan.
set -Eeuo pipefail
[[ -n "${SLURM_JOB_ID:-}" ]] || { printf 'Use bash phase2_refine/start_phase2.sh on Swan.\n' >&2; exit 1; }
PYTHON_PATH="${GEOMSCOPE_P2_BASE:?}/phase2_pilot/.env/bin/python"
[[ -x "$PYTHON_PATH" ]] || { printf 'The working Phase 2 environment is missing: %s\n' "$PYTHON_PATH" >&2; exit 1; }
"$PYTHON_PATH" -m pip check
"$PYTHON_PATH" - <<'PY'
import sys
from importlib.metadata import version
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
assert sys.version_info[:2] == (3, 12)
for package, wanted in [('transformers','5.3.0'),('accelerate','1.12.0'),('numpy','2.3.5')]:
    actual=version(package)
    assert actual == wanted, (package,actual,wanted)
assert torch.__version__.split('+')[0] == '2.13.0'
assert torch.version.cuda == '12.6'
print('Previously successful Phase 2 environment verified; no installation or download requested.')
PY
