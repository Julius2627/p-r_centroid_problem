#!/bin/bash
# Das ist der einzige Befehl, den du pro Lauf von Hand ausfuehrst:
#
#   ./submit_all.sh            # max. 20 Tasks gleichzeitig (Default)
#   ./submit_all.sh 40         # max. 40 Tasks gleichzeitig
#
# Ermittelt automatisch die Gesamtzahl (Instanzen x Methoden), reicht
# den Array-Job ein und haengt direkt danach einen Merge-Job dran, der
# automatisch erst startet, wenn ALLE Array-Tasks fertig sind (egal ob
# erfolgreich oder nicht -> collect_results.py meldet fehlgeschlagene
# Kombinationen).

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
source config.sh

MAX_CONCURRENT="${1:-20}"

mkdir -p logs results/partial

module load "$PYTHON_MODULE"
source "$VENV_DIR/bin/activate"

TOTAL=$(python main.py --count --instance-dir instances)
if [ "$TOTAL" -eq 0 ]; then
    echo "Keine Instanz/Methode-Kombinationen gefunden (instances/ oder methods/ leer?)." >&2
    exit 1
fi

echo "Instanzen x Methoden x FacilityOeffnungsMglk = $TOTAL zu rechnende Kombinationen."
echo "Reiche Array-Job ein (max. $MAX_CONCURRENT gleichzeitig)..."
ARRAY_JOB_ID=$(sbatch --parsable --array="0-$((TOTAL - 1))%${MAX_CONCURRENT}" solve_array.sh)
echo "  -> Array-Job: $ARRAY_JOB_ID"

MERGE_JOB_ID=$(sbatch --parsable --mail-type=END,FAIL --mail-user="julius.hoffmann@kit.edu" --dependency="afterany:${ARRAY_JOB_ID}" merge_results.sh)
echo "  -> Merge-Job: $MERGE_JOB_ID (startet automatisch, sobald alle $TOTAL Tasks fertig sind)"

echo ""
echo "Fortschritt verfolgen:   squeue -u \$USER"
echo "Endergebnis erscheint:   results/final_results.csv"
