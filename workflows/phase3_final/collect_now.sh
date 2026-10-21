#!/usr/bin/env bash
# Recovery when the scheduler rejected the automatic collector submission.
set -Eeuo pipefail
FINAL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BASE_DIR="$(cd -- "$FINAL_DIR/.." && pwd -P)"
run_dir="${1:?Supply the full run-directory path printed by the launcher}"
[[ -d "$run_dir" ]] || { printf 'Run directory not found: %s\n' "$run_dir" >&2; exit 1; }
run_dir="$(realpath -- "$run_dir")"
"$BASE_DIR/.env/bin/python" - "$FINAL_DIR" "$BASE_DIR" "$run_dir" <<'PY'
import getpass,json,subprocess,sys
from pathlib import Path
package,base,out=map(Path,sys.argv[1:])
jobs_path=out/'launcher_jobs.json'
jobs={}
if jobs_path.exists():
    jobs=json.loads(jobs_path.read_text())
    ids=[str(jobs[k]) for k in ('prepare_job_id','qwen_job_id','phi_job_id','smol_job_id','collect_job_id') if str(jobs.get(k,'' )).isdigit()]
    if ids:
        check=subprocess.run(['squeue','--noheader','--user',getpass.getuser(),'--format','%i %T'],text=True,capture_output=True)
        if check.returncode!=0:
            raise SystemExit('Cannot verify whether compute jobs finished. Retry after the scheduler responds.')
        active=[line for line in check.stdout.splitlines() if line.split() and line.split()[0] in ids]
        if active:raise SystemExit('Compute or collection jobs are still active. Let them finish before collection.\n'+'\n'.join(active))
command=[str(base/'.env/bin/python'),str(package/'run_final.py'),'collect','--run-id',out.name,
         '--output-root',str(out.parent),'--cache-dir',str(jobs.get('cache_dir',base/'cache/llms_phase2')),
         '--source-zip',str(jobs.get('source_zip',base/'results_phase3_prepare/return_zips/phase3_prepare_20261020T211054Z_234814_30462_phase3_prepare_results.zip')),
         '--development-zip',str(jobs.get('development_zip',base/'results_phase2_refine/return_zips/phase2_refine_20261020T201951Z_3900908_15370_phase2_results.zip'))]
raise SystemExit(subprocess.call(command))
PY
