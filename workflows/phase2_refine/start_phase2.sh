#!/usr/bin/env bash
# One CPU preparation job, three sequential GPU jobs, then CPU collection.
set -Eeuo pipefail
P2_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BASE_DIR="$(cd -- "$P2_DIR/.." && pwd -P)"
parent_zip="${1:-$BASE_DIR/results_phase2/return_zips/phase2_pilot_20261020T171803Z_2789668_14528_phase2_results.zip}"
output_root="${2:-$BASE_DIR/results_phase2_refine}"
cache_dir="${GEOMSCOPE_P2_MODEL_CACHE:-$BASE_DIR/cache/llms_phase2}"
run_id="phase2_refine_$(date -u +%Y%m%dT%H%M%SZ)_$$_${RANDOM}"
[[ -x "$BASE_DIR/.env/bin/python" ]] || { printf 'Original Phase 1 Python environment is required for diagnostic fallback.\n' >&2; exit 1; }
[[ -f "$parent_zip" ]] || { printf 'Reviewed continuation ZIP missing: %s\n' "$parent_zip" >&2; exit 1; }
command -v sbatch >/dev/null 2>&1 || { printf 'Run this launcher on Swan.\n' >&2; exit 1; }
parent_zip="$(realpath -- "$parent_zip")"
output_root="$(realpath -m -- "$output_root")"
cache_dir="$(realpath -m -- "$cache_dir")"
[[ "$cache_dir" != "$output_root" && "$cache_dir" != "$output_root/"* ]] || { printf 'Keep the model cache outside results.\n' >&2; exit 1; }
mkdir -p -- "$P2_DIR/logs" "$output_root/$run_id"
export GEOMSCOPE_P2_DIR="$P2_DIR" GEOMSCOPE_P2_BASE="$BASE_DIR"
export GEOMSCOPE_P2_PARENT="$parent_zip" GEOMSCOPE_P2_OUTPUT="$output_root"
export GEOMSCOPE_P2_CACHE="$cache_dir" GEOMSCOPE_P2_ID="$run_id"
prepare_job_id=""; qwen_job_id=""; phi_job_id=""; smol_job_id=""; collect_job_id=""
record_jobs() {
    "$BASE_DIR/.env/bin/python" - "$output_root/$run_id/launcher_jobs.json" "$run_id" "$P2_DIR/logs" \
        "$prepare_job_id" "$qwen_job_id" "$phi_job_id" "$smol_job_id" "$collect_job_id" <<'PY'
import json
from pathlib import Path
import sys
path=Path(sys.argv[1])
record=dict(zip(['run_id','logs_dir','prepare_job_id','qwen_job_id','phi_job_id','smol_job_id','collect_job_id'],sys.argv[2:]))
temporary=path.with_suffix('.json.part')
temporary.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
temporary.replace(path)
PY
}
job_id=""
submit() {
    local reply
    reply="$(sbatch --parsable --chdir="$P2_DIR" "$@")"
    job_id="${reply%%;*}"
    [[ "$job_id" =~ ^[0-9]+$ ]] || { printf 'Unexpected Slurm response: %s\n' "$reply" >&2; exit 1; }
}
record_jobs
submit "$P2_DIR/prepare.sbatch"; prepare_job_id="$job_id"; record_jobs
printf 'Phase 2 run: %s\nPrepare: %s\n' "$run_id" "$prepare_job_id"
submit --dependency="afterany:$prepare_job_id" "$P2_DIR/model.sbatch" qwen; qwen_job_id="$job_id"; record_jobs
printf 'Qwen GPU: %s\n' "$qwen_job_id"
submit --dependency="afterany:$qwen_job_id" "$P2_DIR/model.sbatch" phi; phi_job_id="$job_id"; record_jobs
printf 'Phi GPU: %s\n' "$phi_job_id"
submit --dependency="afterany:$phi_job_id" "$P2_DIR/model.sbatch" smol; smol_job_id="$job_id"; record_jobs
printf 'SmolLM GPU: %s\n' "$smol_job_id"
submit --dependency="afterany:$smol_job_id" "$P2_DIR/collect.sbatch"; collect_job_id="$job_id"; record_jobs
printf 'Collector: %s\nReturn ZIP: %s/return_zips/%s_phase2_results.zip\n' "$collect_job_id" "$output_root" "$run_id"
