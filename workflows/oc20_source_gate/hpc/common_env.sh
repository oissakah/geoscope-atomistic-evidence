#!/usr/bin/env bash
export GEOSCOPE_BASE="${GEOSCOPE_BASE:-/lustre/work/ock/oissakah10}"
export PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}"
echo "External source audit environment: $(python3 --version 2>&1)"
