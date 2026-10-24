#!/usr/bin/env bash
set -Eeuo pipefail
printf '
=== OCK PARTITION ===
'
if ! command -v sinfo >/dev/null 2>&1; then
  echo 'sinfo not found: run this on a Swan login node.' >&2; exit 2
fi
if ! sinfo -h -p ock -o '%P' | grep -Eq '^ock\*?$'; then
  echo 'Partition ock is not visible. Contact HCC if you expect owned access.' >&2; exit 3
fi
sinfo -p ock -o '%P %a %D %t %G %f'
printf '
=== OCK NODES ===
'
sinfo -N -p ock -o '%N %P %t %G %f'
printf '
=== GROUP QUEUE ===
'
squeue -p ock -o '%.16i %.10u %.12j %.9T %.16R' || true
printf '
NOTE: HCC group-owned partitions require explicit user access. Visibility alone does not guarantee permission to submit.
'
