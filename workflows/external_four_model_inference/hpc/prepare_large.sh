#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
source hpc/common_env.sh
bash hpc/prepare_external.sh
OLD="${GEOSCOPE_32B_PARENT:-/lustre/work/ock/oissakah10/GeoScope_Phase4_v1_4_ock_qwen32b_awq}"
source "$OLD/outputs/large_environment.sh"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
python3 -m hpc.large_external_preflight
