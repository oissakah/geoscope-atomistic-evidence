#!/usr/bin/env bash
# Only run inside an allocated HCC CPU batch job; never a busy login or GPU node.
set -euo pipefail
BASE="${GEOSCOPE_BASE:-/lustre/work/ock/oissakah10}"
DEST="$BASE/GeoScope_OC20_source/is2res_val_ood_both_trajectories.tar"
URL=https://dl.fbaipublicfiles.com/opencatalystproject/data/is2res_val_ood_both_trajectories.tar
MD5=bc74b6474a13542cc56eaa97bd51adfc
if [[ "${OC20_CPU_JOB:-}" != YES || -z "${SLURM_JOB_ID:-}" ]]; then
 echo >&2 'STOP: use bash hpc/submit_download_oc20.sh to download in a scheduled CPU allocation.'
 echo >&2 "Expected source: $URL (~4.4 GB)"
 echo >&2 "Expected destination: $DEST"
 exit 2
fi
mkdir -p "$(dirname "$DEST")"
if [[ ! -f "$DEST" ]]; then
 command -v curl >/dev/null || { echo 'curl unavailable';exit 2; }
 curl -fL --retry 5 --continue-at - --output "$DEST.part" "$URL"
 mv "$DEST.part" "$DEST"
fi
printf '%s  %s\n' "$MD5" "$DEST" | md5sum -c -
echo "SOURCE_VERIFIED=$DEST"
