#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
source hpc/common_env.sh
python3 -m hpc.collect_external
