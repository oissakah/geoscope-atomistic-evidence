#!/usr/bin/env bash
set -euo pipefail
export PYTHONNOUSERSITE=1
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
python3 -c 'import sys;print("CPU Python:",sys.version.split()[0])'
