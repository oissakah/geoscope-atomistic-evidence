#!/usr/bin/env bash
#SBATCH --job-name=geo-oc20-format
#SBATCH --partition=batch
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --output=outputs/logs/geo_oc20_format_%j.out
#SBATCH --error=outputs/logs/geo_oc20_format_%j.err
set -euo pipefail
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_5_OC20_external_gate
source hpc/common_env.sh
source hpc/use_cpu_env.sh
SRC="${OC20_TAR:-/lustre/work/ock/oissakah10/GeoScope_OC20_source/s2ef_val_ood_both.tar}"
python3 -m phase4.oc20_archive_inventory --tar "$SRC" --out outputs/oc20_format_inventory
