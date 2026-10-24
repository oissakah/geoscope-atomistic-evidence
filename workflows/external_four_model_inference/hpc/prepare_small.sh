#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
source hpc/common_env.sh
bash hpc/prepare_external.sh
MM="${GEOSCOPE_MM_PARENT:-/lustre/work/ock/oissakah10/GeoScope_Phase4_v1_3_ock_multimodel}"
source "$MM/outputs/gpu_environment.sh"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
python3 -m hpc.external_preflight
