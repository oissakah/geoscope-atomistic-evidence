#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
cat VERSION
source hpc/common_env.sh
python3 -m unittest discover -s tests -v
python3 -m hpc.external_stage
[[ -f /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_5_OC20_external_gate/outputs/external_oc20_benchmark/SEAL_OFFLINE/gold_proofs_SEALED.json ]] || {
  echo 'WARNING: sealed offline source not currently available. Model inputs stay sealed regardless.' >&2;
}
echo 'PUBLIC ONLY STAGED. No gold in the model-input folder.'
