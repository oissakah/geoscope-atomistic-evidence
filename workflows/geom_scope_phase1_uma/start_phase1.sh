#!/usr/bin/env bash
# Submit preparation, GPU calculation, then collection for one shared run ID.
set -Eeuo pipefail
PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd -- "$PACKAGE_DIR"
config_path="$PACKAGE_DIR/config/pilot.json"
output_root="$PACKAGE_DIR/results"
cache_dir="${GEOMSCOPE_CACHE:-$PACKAGE_DIR/cache}"
run_id="uma_phase1_$(date -u +%Y%m%dT%H%M%SZ)_$$_${RANDOM}"
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --config|--output-root|--cache-dir|--run-id)
            [[ "$#" -ge 2 ]] || { printf 'Missing value for %s\n' "$1" >&2; exit 1; }
            case "$1" in
                --config) config_path="$2" ;;
                --output-root) output_root="$2" ;;
                --cache-dir) cache_dir="$2" ;;
                --run-id) run_id="$2" ;;
            esac
            shift 2 ;;
        -h|--help)
            printf 'Usage: bash start_phase1.sh [--config PATH] [--cache-dir PATH] [--output-root PATH] [--run-id ID]\n'
            exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$1" >&2; exit 1 ;;
    esac
done
[[ "$run_id" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]] || { printf 'Run ID must contain only letters, digits, underscores and hyphens.\n' >&2; exit 1; }
command -v sbatch >/dev/null 2>&1 || { printf 'Run this launcher on Swan, where sbatch is available.\n' >&2; exit 1; }
[[ -x "$PACKAGE_DIR/.env/bin/python" ]] || { printf 'Environment missing. Submit sbatch setup.sbatch and wait for successful setup first.\n' >&2; exit 1; }
[[ -f "$config_path" ]] || { printf 'Configuration does not exist: %s\n' "$config_path" >&2; exit 1; }
config_path="$(realpath -- "$config_path")"
output_root="$(realpath -m -- "$output_root")"
cache_dir="$(realpath -m -- "$cache_dir")"
if [[ "$cache_dir" == "$output_root" || "$cache_dir" == "$output_root/"* ]]; then
    printf 'Choose a cache directory outside the results directory.\n' >&2
    exit 1
fi
if [[ -e "$output_root/$run_id" ]]; then
    printf 'Run directory already exists. Choose a new run ID: %s\n' "$output_root/$run_id" >&2
    exit 1
fi
mkdir -p -- "$PACKAGE_DIR/logs"
export GEOMSCOPE_PACKAGE_DIR="$PACKAGE_DIR"
export GEOMSCOPE_CACHE="$cache_dir"
export GEOMSCOPE_CONFIG="$config_path"
export GEOMSCOPE_OUTPUT_ROOT="$output_root"
export GEOMSCOPE_RUN_ID="$run_id"
submitted_job_id=""
submit_job() {
    local submission
    if ! submission="$(sbatch --parsable --chdir="$PACKAGE_DIR" "$@")"; then
        printf 'A Slurm submission failed. Already submitted jobs may still run; inspect the job IDs printed above.\n' >&2
        exit 1
    fi
    submitted_job_id="${submission%%;*}"
    if [[ ! "$submitted_job_id" =~ ^[0-9]+$ ]]; then
        printf 'Cannot interpret Slurm submission response: %s\n' "$submission" >&2
        exit 1
    fi
}
printf 'Run ID: %s\n' "$run_id"
submit_job "$PACKAGE_DIR/prepare.sbatch"
prepare_job_id="$submitted_job_id"
printf 'Prepare job: %s\n' "$prepare_job_id"
submit_job --dependency="afterany:$prepare_job_id" "$PACKAGE_DIR/phase1.sbatch"
gpu_job_id="$submitted_job_id"
printf 'GPU job: %s (after preparation finishes)\n' "$gpu_job_id"
submit_job --dependency="afterany:$gpu_job_id" "$PACKAGE_DIR/collect.sbatch"
collect_job_id="$submitted_job_id"
printf 'Collector job: %s (after GPU job finishes, including failure or timeout)\n' "$collect_job_id"
"$PACKAGE_DIR/.env/bin/python" - "$output_root/$run_id/launcher_jobs.json" "$run_id" "$prepare_job_id" "$gpu_job_id" "$collect_job_id" "$PACKAGE_DIR" "$PACKAGE_DIR/logs" <<'PY'
import json
from pathlib import Path
import sys
record = dict(zip(["run_id", "prepare_job_id", "gpu_job_id", "collect_job_id", "package_dir", "logs_dir"], sys.argv[2:]))
target = Path(sys.argv[1])
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
PY
printf '\nResults: %s/%s\nCache: %s\n' "$output_root" "$run_id" "$cache_dir"
printf 'After collection, return the ZIP reported by the collector. Do not include the environment or cache.\n'
