#!/bin/bash
#SBATCH --job-name=merge_results
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --partition=dev_cpu               # kurze Aufgabe -> Development-Queue
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=julius.hoffmann@kit.edu                      # TODO: deine Mail-Adresse
# Wird NICHT von Hand gestartet, sondern von submit_all.sh mit
# --dependency=afterany:<array_job_id> eingereicht.

set -euo pipefail

cd "${SLURM_SUBMIT_DIR:-$(dirname "${BASH_SOURCE[0]}")}"
source config.sh

module load "$PYTHON_MODULE"
source "$VENV_DIR/bin/activate"

python collect_results.py \
    --partial-dir results/partial \
    --instance-dir instances \
    --output results/final_results.csv
