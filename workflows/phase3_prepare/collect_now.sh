#!/usr/bin/env bash
# Recovery when the scheduler rejected the automatic collector submission.
set -Eeuo pipefail
P3_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
BASE_DIR="$(cd -- "$P3_DIR/.." && pwd -P)"
run_dir="${1:?Supply the full run-directory path printed by the launcher}"
[[ -d "$run_dir" ]] || { printf 'Run directory not found: %s\n' "$run_dir" >&2; exit 1; }
run_dir="$(realpath -- "$run_dir")"
"$BASE_DIR/.env/bin/python" - "$P3_DIR" "$BASE_DIR" "$run_dir" <<'PY'
import getpass,json,subprocess,sys
from pathlib import Path
package,base,out=map(Path,sys.argv[1:])
jobs_path=out/'launcher_jobs.json'
jobs={}
if jobs_path.exists():
    jobs=json.loads(jobs_path.read_text())
    ids=[str(jobs[k]) for k in ('prepare_job_id','uma0_job_id','uma1_job_id','uma2_job_id','collect_job_id') if str(jobs.get(k,'' )).isdigit()]
    if ids:
        check=subprocess.run(['squeue','--noheader','--user',getpass.getuser(),'--format','%i %T'],text=True,capture_output=True)
        if check.returncode!=0:
            raise SystemExit('Cannot verify whether compute jobs finished. Retry after the scheduler responds.')
        active=[line for line in check.stdout.splitlines() if line.split() and line.split()[0] in ids]
        if active:raise SystemExit('Compute or collection jobs are still active. Let them finish before collection.\n'+'\n'.join(active))
command=[str(base/'.env/bin/python'),str(package/'run_phase3.py'),'collect','--run-id',out.name,
         '--output-root',str(out.parent),'--cache-dir',str(jobs.get('cache_dir',base/'cache')),
         '--refinement-zip',str(jobs.get('refinement_zip',base/'results_phase2_refine/return_zips/phase2_refine_20261020T201951Z_3900908_15370_phase2_results.zip')),
         '--geometry-zip',str(jobs.get('geometry_zip',base/'results/return_zips/uma_phase1_cont_20261020T151825Z_1912433_9416_phase1_results.zip'))]
raise SystemExit(subprocess.call(command))
PY
