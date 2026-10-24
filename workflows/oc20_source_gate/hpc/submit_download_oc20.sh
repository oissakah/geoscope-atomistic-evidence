#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p outputs/logs
if ! sinfo -h -p batch | grep -q .; then echo >&2 'STOP: batch CPU partition is not visible; check HCC partition entitlement';exit 2;fi
sbatch hpc/download_oc20_cpu.sbatch
