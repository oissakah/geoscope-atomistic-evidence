#!/usr/bin/env bash
set -euo pipefail
BASE="${GEOSCOPE_BASE:-/lustre/work/ock/oissakah10}"
PY="$(command -v python3)"
VENV="$BASE/.geoscope_venvs/oc20_cpu_v15"
if [[ ! -x "$VENV/bin/python3" ]]; then
 mkdir -p "$(dirname "$VENV")"
 "$PY" -m venv "$VENV"
fi
"$VENV/bin/python3" -m pip install --disable-pip-version-check 'numpy>=1.23,<2.0' 'ase==3.24.0'
echo "CPU_ENV=$VENV"
