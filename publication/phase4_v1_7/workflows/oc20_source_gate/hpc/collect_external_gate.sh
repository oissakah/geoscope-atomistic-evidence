#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY_COLLECT'
from pathlib import Path
import zipfile,datetime,json,hashlib
root=Path.cwd();stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
dest=root.parent/f'GeoScope_Phase4_v1_5_OC20_external_gate_results_{stamp}.zip'
allowed=['VERSION','EXPERIMENT_PROTOCOL.md','STATUS.md','README.md','outputs/external_oc20_source','outputs/external_oc20_benchmark','outputs/oc20_format_inventory','outputs/logs']
manifest={}
with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for sub in allowed:
  p=root/sub
  files=[p] if p.is_file() else (p.rglob('*') if p.is_dir() else [])
  for f in files:
   if not f.is_file():continue
   if f.stat().st_size>30_000_000:continue
   name=f.relative_to(root).as_posix();data=f.read_bytes()
   z.writestr(name,data);manifest[name]=hashlib.sha256(data).hexdigest()
 z.writestr('COLLECTION_SHA256.json',json.dumps(manifest,indent=2,sort_keys=True)+'\n')
assert zipfile.is_zipfile(dest)
with zipfile.ZipFile(dest) as z:
 assert z.testzip() is None
print('RESULT_ARCHIVE',dest)
print('SOURCE_GATE', (root/'outputs/external_oc20_source/SOURCE_GATE_STATUS.json').exists())
print('BENCHMARK', (root/'outputs/external_oc20_benchmark/BUILD_STATUS.json').exists())
PY_COLLECT
