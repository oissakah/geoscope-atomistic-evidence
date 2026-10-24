#!/usr/bin/env bash
#SBATCH --job-name=geo-oc20-dl
#SBATCH --partition=batch
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=outputs/logs/geo_oc20_download_%j.out
#SBATCH --error=outputs/logs/geo_oc20_download_%j.err
set -euo pipefail
cd /lustre/work/ock/oissakah10/GeoScope_Phase4_v1_5_OC20_external_gate
export OC20_CPU_JOB=YES
bash hpc/download_oc20.sh
