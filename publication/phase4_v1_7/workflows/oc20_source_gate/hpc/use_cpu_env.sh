#!/usr/bin/env bash
BASE="${GEOSCOPE_BASE:-/lustre/work/ock/oissakah10}"
VENV="$BASE/.geoscope_venvs/oc20_cpu_v15"
if [[ ! -x "$VENV/bin/python3" ]]; then
 echo "Missing CPU env; first run bash hpc/setup_cpu_env.sh" >&2
 return 2 2>/dev/null || exit 2
fi
export PATH="$VENV/bin:$PATH"
export VIRTUAL_ENV="$VENV"
export PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}"
echo "OC20 Python: $(python3 --version 2>&1)"
