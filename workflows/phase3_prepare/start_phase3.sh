#!/usr/bin/env bash
# Freeze a disjoint source pool, run three UMA batches, then return a ZIP.
set -Eeuo pipefail
P3_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BASE_DIR="$(cd -- "$P3_DIR/.." && pwd -P)"
refinement_zip="${1:-$BASE_DIR/results_phase2_refine/return_zips/phase2_refine_20261020T201951Z_3900908_15370_phase2_results.zip}"
geometry_zip="${2:-$BASE_DIR/results/return_zips/uma_phase1_cont_20261020T151825Z_1912433_9416_phase1_results.zip}"
output_root="${3:-$BASE_DIR/results_phase3_prepare}"
cache_dir="${GEOMSCOPE_P3_CACHE:-$BASE_DIR/cache}"
run_id="phase3_prepare_$(date -u +%Y%m%dT%H%M%SZ)_$$_${RANDOM}"
[[ -x "$BASE_DIR/.env/bin/python" ]] || { printf 'The working Phase 1 UMA environment is required.\n' >&2; exit 1; }
[[ -f "$refinement_zip" && -f "$geometry_zip" ]] || { printf 'Keep the reviewed refinement and continuation ZIPs in their original return_zips folders.\n' >&2; exit 1; }
command -v sbatch >/dev/null 2>&1 || { printf 'Run this launcher on Swan.\n' >&2; exit 1; }
refinement_zip="$(realpath -- "$refinement_zip")"
geometry_zip="$(realpath -- "$geometry_zip")"
output_root="$(realpath -m -- "$output_root")"
cache_dir="$(realpath -m -- "$cache_dir")"
[[ "$cache_dir" != "$output_root" && "$cache_dir" != "$output_root/"* ]] || { printf 'Keep the cache outside results.\n' >&2; exit 1; }
mkdir -p -- "$P3_DIR/logs" "$output_root/$run_id"
export GEOMSCOPE_P3_DIR="$P3_DIR" GEOMSCOPE_P3_BASE="$BASE_DIR" GEOMSCOPE_P3_ID="$run_id"
export GEOMSCOPE_P3_REFINEMENT="$refinement_zip" GEOMSCOPE_P3_GEOMETRY="$geometry_zip"
export GEOMSCOPE_P3_OUTPUT="$output_root" GEOMSCOPE_P3_CACHE="$cache_dir"
prepare_job_id=""; uma0_job_id=""; uma1_job_id=""; uma2_job_id=""; collect_job_id=""
record_jobs() {
    "$BASE_DIR/.env/bin/python" - "$output_root/$run_id/launcher_jobs.json" "$run_id" "$P3_DIR/logs" \
        "$prepare_job_id" "$uma0_job_id" "$uma1_job_id" "$uma2_job_id" "$collect_job_id" \
        "$cache_dir" "$refinement_zip" "$geometry_zip" <<'PY'
import json,sys
from pathlib import Path
path=Path(sys.argv[1])
record=dict(zip(['run_id','logs_dir','prepare_job_id','uma0_job_id','uma1_job_id','uma2_job_id','collect_job_id',
                 'cache_dir','refinement_zip','geometry_zip'],sys.argv[2:]))
temporary=path.with_suffix('.json.part')
temporary.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
temporary.replace(path)
PY
}
job_id=""
recover_collection() {
    local recovery_reply recovery_id dependency="" item
    for item in "$prepare_job_id" "$uma0_job_id" "$uma1_job_id" "$uma2_job_id"; do
        if [[ -n "$item" ]]; then dependency="${dependency:+$dependency:}$item"; fi
    done
    printf 'A job submission failed. Preserving accepted jobs and attempting diagnostic collection.\n' >&2
    if [[ -n "$dependency" ]]; then
        recovery_reply="$(sbatch --parsable --chdir="$P3_DIR" --dependency="afterany:$dependency" "$P3_DIR/collect.sbatch")" || recovery_reply=""
    else
        recovery_reply="$(sbatch --parsable --chdir="$P3_DIR" "$P3_DIR/collect.sbatch")" || recovery_reply=""
    fi
    recovery_id="${recovery_reply%%;*}"
    if [[ "$recovery_id" =~ ^[0-9]+$ ]]; then
        collect_job_id="$recovery_id"; record_jobs
        printf 'Recovery collector: %s\nReturn ZIP: %s/return_zips/%s_phase3_prepare_results.zip\n' "$collect_job_id" "$output_root" "$run_id" >&2
    else
        printf 'Collector submission was also rejected. After accepted jobs finish, run:\nbash %q %q\n' "$P3_DIR/collect_now.sh" "$output_root/$run_id" >&2
    fi
}
submit() {
    local reply
    if ! reply="$(sbatch --parsable --chdir="$P3_DIR" "$@")"; then
        recover_collection
        exit 1
    fi
    job_id="${reply%%;*}"
    [[ "$job_id" =~ ^[0-9]+$ ]] || { printf 'Unexpected Slurm response: %s\n' "$reply" >&2; recover_collection; exit 1; }
}
record_jobs
submit "$P3_DIR/prepare.sbatch"; prepare_job_id="$job_id"; record_jobs
printf 'Phase 3 source run: %s\nPreparation: %s\n' "$run_id" "$prepare_job_id"
submit --dependency="afterany:$prepare_job_id" "$P3_DIR/uma.sbatch" 0; uma0_job_id="$job_id"; record_jobs
printf 'UMA batch 0: %s\n' "$uma0_job_id"
submit --dependency="afterany:$uma0_job_id" "$P3_DIR/uma.sbatch" 1; uma1_job_id="$job_id"; record_jobs
printf 'UMA batch 1: %s\n' "$uma1_job_id"
submit --dependency="afterany:$uma1_job_id" "$P3_DIR/uma.sbatch" 2; uma2_job_id="$job_id"; record_jobs
printf 'UMA batch 2: %s\n' "$uma2_job_id"
submit --dependency="afterany:$uma2_job_id" "$P3_DIR/collect.sbatch"; collect_job_id="$job_id"; record_jobs
printf 'Collector: %s\nReturn ZIP: %s/return_zips/%s_phase3_prepare_results.zip\n' "$collect_job_id" "$output_root" "$run_id"
