#!/usr/bin/env bash
# Freeze the final protocol, run three language models, then return a ZIP.
set -Eeuo pipefail
FINAL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BASE_DIR="$(cd -- "$FINAL_DIR/.." && pwd -P)"
source_zip="${1:-$BASE_DIR/results_phase3_prepare/return_zips/phase3_prepare_20261020T211054Z_234814_30462_phase3_prepare_results.zip}"
development_zip="${2:-$BASE_DIR/results_phase2_refine/return_zips/phase2_refine_20261020T201951Z_3900908_15370_phase2_results.zip}"
output_root="${3:-$BASE_DIR/results_phase3_final}"
cache_dir="${GEOMSCOPE_FINAL_CACHE:-$BASE_DIR/cache/llms_phase2}"
run_id="final_study_$(date -u +%Y%m%dT%H%M%SZ)_$$_${RANDOM}"
[[ -x "$BASE_DIR/phase2_pilot/.env/bin/python" && -x "$BASE_DIR/.env/bin/python" ]] || { printf 'The working Phase 2 language-model environment is required.\n' >&2; exit 1; }
[[ -f "$source_zip" && -f "$development_zip" ]] || { printf 'Keep the reviewed source and development ZIPs in their original return_zips folders.\n' >&2; exit 1; }
command -v sbatch >/dev/null 2>&1 || { printf 'Run this launcher on Swan.\n' >&2; exit 1; }
source_zip="$(realpath -- "$source_zip")"
development_zip="$(realpath -- "$development_zip")"
output_root="$(realpath -m -- "$output_root")"
cache_dir="$(realpath -m -- "$cache_dir")"
[[ "$cache_dir" != "$output_root" && "$cache_dir" != "$output_root/"* ]] || { printf 'Keep the cache outside results.\n' >&2; exit 1; }
mkdir -p -- "$FINAL_DIR/logs" "$output_root/$run_id"
export GEOMSCOPE_FINAL_DIR="$FINAL_DIR" GEOMSCOPE_FINAL_BASE="$BASE_DIR" GEOMSCOPE_FINAL_ID="$run_id"
export GEOMSCOPE_FINAL_SOURCE="$source_zip" GEOMSCOPE_FINAL_DEVELOPMENT="$development_zip"
export GEOMSCOPE_FINAL_OUTPUT="$output_root" GEOMSCOPE_FINAL_CACHE="$cache_dir"
prepare_job_id=""; qwen_job_id=""; phi_job_id=""; smol_job_id=""; collect_job_id=""
record_jobs() {
    "$BASE_DIR/.env/bin/python" - "$output_root/$run_id/launcher_jobs.json" "$run_id" "$FINAL_DIR/logs" \
        "$prepare_job_id" "$qwen_job_id" "$phi_job_id" "$smol_job_id" "$collect_job_id" \
        "$cache_dir" "$source_zip" "$development_zip" <<'PY'
import json,sys
from pathlib import Path
path=Path(sys.argv[1])
record=dict(zip(['run_id','logs_dir','prepare_job_id','qwen_job_id','phi_job_id','smol_job_id','collect_job_id',
                 'cache_dir','source_zip','development_zip'],sys.argv[2:]))
temporary=path.with_suffix('.json.part')
temporary.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
temporary.replace(path)
PY
}
job_id=""
recover_collection() {
    local recovery_reply recovery_id dependency="" item
    for item in "$prepare_job_id" "$qwen_job_id" "$phi_job_id" "$smol_job_id"; do
        if [[ -n "$item" ]]; then dependency="${dependency:+$dependency:}$item"; fi
    done
    printf 'A job submission failed. Preserving accepted jobs and attempting diagnostic collection.\n' >&2
    if [[ -n "$dependency" ]]; then
        recovery_reply="$(sbatch --parsable --chdir="$FINAL_DIR" --dependency="afterany:$dependency" "$FINAL_DIR/collect.sbatch")" || recovery_reply=""
    else
        recovery_reply="$(sbatch --parsable --chdir="$FINAL_DIR" "$FINAL_DIR/collect.sbatch")" || recovery_reply=""
    fi
    recovery_id="${recovery_reply%%;*}"
    if [[ "$recovery_id" =~ ^[0-9]+$ ]]; then
        collect_job_id="$recovery_id"; record_jobs
        printf 'Recovery collector: %s\nReturn ZIP: %s/return_zips/%s_final_results.zip\n' "$collect_job_id" "$output_root" "$run_id" >&2
    else
        printf 'Collector submission was also rejected. After accepted jobs finish, run:\nbash %q %q\n' "$FINAL_DIR/collect_now.sh" "$output_root/$run_id" >&2
    fi
}
submit() {
    local reply
    if ! reply="$(sbatch --parsable --chdir="$FINAL_DIR" "$@")"; then
        recover_collection
        exit 1
    fi
    job_id="${reply%%;*}"
    [[ "$job_id" =~ ^[0-9]+$ ]] || { printf 'Unexpected Slurm response: %s\n' "$reply" >&2; recover_collection; exit 1; }
}
record_jobs
submit "$FINAL_DIR/prepare.sbatch"; prepare_job_id="$job_id"; record_jobs
printf 'Final study run: %s\nPreparation: %s\n' "$run_id" "$prepare_job_id"
submit --dependency="afterany:$prepare_job_id" "$FINAL_DIR/model.sbatch" qwen; qwen_job_id="$job_id"; record_jobs
printf 'Qwen: %s\n' "$qwen_job_id"
submit --dependency="afterany:$qwen_job_id" "$FINAL_DIR/model.sbatch" phi; phi_job_id="$job_id"; record_jobs
printf 'Phi: %s\n' "$phi_job_id"
submit --dependency="afterany:$phi_job_id" "$FINAL_DIR/model.sbatch" smol; smol_job_id="$job_id"; record_jobs
printf 'SmolLM: %s\n' "$smol_job_id"
submit --dependency="afterany:$smol_job_id" "$FINAL_DIR/collect.sbatch"; collect_job_id="$job_id"; record_jobs
printf 'Collector: %s\nReturn ZIP: %s/return_zips/%s_final_results.zip\n' "$collect_job_id" "$output_root" "$run_id"
