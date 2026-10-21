#!/usr/bin/env bash
# Run once from the original Phase 1 package; reuse its environment and cache.
set -Eeuo pipefail
CONTINUE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BASE_DIR="$(cd -- "$CONTINUE_DIR/.." && pwd -P)"
parent_zip="${1:-$BASE_DIR/results/return_zips/uma_phase1_20261020T133725Z_1360575_11887_phase1_results.zip}"
output_root="${2:-$BASE_DIR/results}"
run_id="uma_phase1_cont_$(date -u +%Y%m%dT%H%M%SZ)_$$_${RANDOM}"
[[ -x "$BASE_DIR/.env/bin/python" ]] || { printf 'Existing Phase 1 environment missing: %s\n' "$BASE_DIR/.env/bin/python" >&2; exit 1; }
[[ -f "$parent_zip" ]] || { printf 'Original results ZIP missing: %s\n' "$parent_zip" >&2; exit 1; }
command -v sbatch >/dev/null 2>&1 || { printf 'Submit this from Swan.\n' >&2; exit 1; }
parent_zip="$(realpath -- "$parent_zip")"
output_root="$(realpath -m -- "$output_root")"
mkdir -p -- "$CONTINUE_DIR/logs" "$output_root/$run_id"
export GEOMSCOPE_CONTINUE_DIR="$CONTINUE_DIR"
export GEOMSCOPE_BASE_DIR="$BASE_DIR"
export GEOMSCOPE_PARENT_ZIP="$parent_zip"
export GEOMSCOPE_CONTINUE_OUTPUT="$output_root"
export GEOMSCOPE_CONTINUE_ID="$run_id"
cd -- "$CONTINUE_DIR"
gpu_job_id=""
collect_job_id=""
record_jobs() {
    "$BASE_DIR/.env/bin/python" - "$output_root/$run_id/launcher_jobs.json" "$run_id" "$gpu_job_id" "$collect_job_id" "$CONTINUE_DIR/logs" <<'PY'
import json
from pathlib import Path
import sys
path = Path(sys.argv[1])
record = dict(zip(["run_id", "gpu_job_id", "collect_job_id", "logs_dir"], sys.argv[2:]))
temporary = path.with_suffix(".json.part")
temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
temporary.replace(path)
PY
}
record_jobs
submission="$(sbatch --parsable --chdir="$CONTINUE_DIR" "$CONTINUE_DIR/run_continue.sbatch")"
gpu_job_id="${submission%%;*}"
[[ "$gpu_job_id" =~ ^[0-9]+$ ]] || { printf 'Unexpected Slurm response: %s\n' "$submission" >&2; exit 1; }
record_jobs
printf 'Continuation run: %s\nGPU job: %s\n' "$run_id" "$gpu_job_id"
submission="$(sbatch --parsable --chdir="$CONTINUE_DIR" --dependency="afterany:$gpu_job_id" "$CONTINUE_DIR/collect_continue.sbatch")"
collect_job_id="${submission%%;*}"
[[ "$collect_job_id" =~ ^[0-9]+$ ]] || { printf 'Unexpected Slurm response: %s\n' "$submission" >&2; exit 1; }
record_jobs
printf 'Collector job: %s\nReturn ZIP after collection: %s/return_zips/%s_phase1_results.zip\n' "$collect_job_id" "$output_root" "$run_id"
