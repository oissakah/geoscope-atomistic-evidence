#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source hpc/common_env.sh
source hpc/use_cpu_env.sh
[[ -f outputs/external_oc20_source/SOURCE_GATE_STATUS.json ]] || { echo >&2 'STOP: external source gate has not finished';exit 3; }
bash hpc/bootstrap_original.sh
source "${GEOSCOPE_BASE:-/lustre/work/ock/oissakah10}/.geoscope_phase4_reference_env.sh"
python3 -m phase4.build_external_benchmark --repo-root "$REPO_ROOT"
