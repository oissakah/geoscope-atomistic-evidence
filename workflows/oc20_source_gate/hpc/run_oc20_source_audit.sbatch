#!/usr/bin/env bash
#SBATCH --job-name=geo-oc20-gate
#SBATCH --partition=batch
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=20G
#SBATCH --output=outputs/logs/geo_oc20_%j.out
#SBATCH --error=outputs/logs/geo_oc20_%j.err
set -euo pipefail
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_5_OC20_external_gate
source hpc/common_env.sh
source hpc/use_cpu_env.sh
SRC="${OC20_TAR:-/lustre/work/ock/oissakah10/GeoScope_OC20_source/is2res_val_ood_both_trajectories.tar}"
test -f "$SRC" || { echo "MISSING OC20 tar: $SRC" >&2;exit 3; }
python3 -m phase4.external_oc20 --tar "$SRC" --out outputs/external_oc20_source
