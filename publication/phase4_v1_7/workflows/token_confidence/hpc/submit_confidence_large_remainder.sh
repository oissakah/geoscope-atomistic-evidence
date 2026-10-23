#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -f hpc/require_python312_headers.sh && -f hpc/run_confidence_large.sbatch ]] || {
 echo 'STOP: v1.7.4 helper files absent; install the corrected ZIP before submitting.' >&2
 exit 31
}
source hpc/check_environment.sh
[[ -f outputs/confidence/qwen32b/confidence_shard_00.jsonl ]] || { echo 'STOP: Pilot shard 0 output missing; review its GPU logs first.' >&2; exit 3; }
"$GEOSCOPE_GPU_PYTHON" - <<'PY_AUDIT'
import json,pathlib
p=pathlib.Path('outputs/confidence/qwen32b/confidence_shard_00.jsonl')
rs=[json.loads(s) for s in p.read_text().splitlines() if s.strip()]
assert len(rs)==128 and len({r['request_id'] for r in rs})==128
assert all(r['exact_replay'] and r['status']=='ok' for r in rs)
assert all(r['all_token_geomean'] is not None for r in rs)
print('32B PILOT PASS: 128 exact response replays; confidence recorded')
PY_AUDIT
mkdir -p outputs/logs
export PHASE4_DIR="$PWD"
sbatch --partition=ock --array=1-11%1 --export=ALL hpc/run_confidence_large.sbatch
squeue -u "$USER"
