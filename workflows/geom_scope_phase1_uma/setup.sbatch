#!/usr/bin/env bash
#SBATCH --job-name=geom-uma-setup
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=setup-%j.log

set -Eeuo pipefail
PACKAGE_DIR="${GEOMSCOPE_PACKAGE_DIR:-${SLURM_SUBMIT_DIR:?Submit from the unpacked package directory.}}"
cd -- "$PACKAGE_DIR"
bash "$PACKAGE_DIR/setup_swan.sh"
