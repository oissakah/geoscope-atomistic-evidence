#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source hpc/use_cpu_env.sh
python3 - <<'PY_CHECK'
import sys,importlib.util
print('Python:',sys.version)
for name in ('ase','numpy'):
 if importlib.util.find_spec(name) is None:raise SystemExit('MISSING '+name+'; install into a separate Python environment before auditing')
print('PASS: NumPy and ASE importable')
PY_CHECK
python3 -m unittest discover -s tests -v
