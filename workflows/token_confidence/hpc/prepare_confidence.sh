#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" PYTHONNOUSERSITE=1
python3 -m unittest discover -s tests -q
python3 -m hpc.external_stage
python3 - <<'PY_PREP'
import json
from pathlib import Path
from hpc.confidence_common import checked_inputs,verify_stage
root=Path('.').resolve();verify_stage(root)
for key in ['qwen','phi','smol','qwen32b']:
    for shard in range(12):
        checked_inputs(root,key,shard)
for p in root.rglob('*'):
    if p.is_file() and ('SEALED_REVIEW_ONLY' in str(p) or 'gold_proofs' in p.name.lower()):
        raise RuntimeError('Sealed answer data must not enter GPU experiment')
print('PREPARED: 1,536 frozen OC20 questions / 48 source groups / 6,144 reference responses; gold absent')
PY_PREP
