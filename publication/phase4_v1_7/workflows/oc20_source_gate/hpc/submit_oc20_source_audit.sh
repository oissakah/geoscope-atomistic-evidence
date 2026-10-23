#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p outputs/logs
SRC="${OC20_TAR:-/lustre/work/ock/oissakah10/GeoScope_OC20_source/is2res_val_ood_both_trajectories.tar}"
test -s "$SRC" || { echo "STOP: missing verified source archive $SRC" >&2;exit 2; }
if ! sinfo -h -p batch | grep -q .; then echo >&2 'STOP: batch partition not visible; request valid CPU partition from HCC';exit 2;fi
sbatch --export=ALL,OC20_TAR="$SRC" hpc/run_oc20_source_audit.sbatch
