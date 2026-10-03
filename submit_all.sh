#!/bin/bash
# Das ist der einzige Befehl, den du pro Lauf von Hand ausfuehrst:
#
#   ./submit_all.sh            # max. 5 Tasks gleichzeitig (Default)
#   ./submit_all.sh 40         # max. 40 Tasks gleichzeitig
#
# Der Default ist bewusst klein: Gurobi holt sich pro laufendem Prozess eine
# Lizenz beim Token-Server, dessen Kapazitaet begrenzt und geteilt ist.
# Erst nach `gurobi_cl --tokens` und einem ersten Testlauf erhoehen (README).
#
# Ermittelt automatisch die Gesamtzahl (Instanzen x Methoden), reicht
# den/die Array-Job(s) ein und haengt direkt danach einen Merge-Job dran,
# der automatisch erst startet, wenn ALLE Array-Tasks fertig sind (egal ob
# erfolgreich oder nicht -> collect_results.py meldet fehlgeschlagene
# Kombinationen).
#
# Grosse Arrays: Slurm begrenzt die Groesse eines einzelnen Array-Jobs
# (MaxArraySize, clusterabhaengig -- pruefen mit
# `scontrol show config | grep MaxArraySize`). Ist TOTAL groesser als
# MAX_ARRAY_CHUNK (config.sh), wird automatisch in mehrere Array-Jobs
# aufgeteilt (Task-IDs 0..TOTAL-1 bleiben dabei fortlaufend und eindeutig,
# solve_array.sh und grid.py muessen dafuer nichts wissen). Der Merge-Job
# wartet auf ALLE Teil-Jobs.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
source config.sh

MAX_CONCURRENT="${1:-5}"

mkdir -p logs results/partial

module load "$PYTHON_MODULE"
source "$VENV_DIR/bin/activate"

TOTAL=$(python main.py --count --instance-dir instances)
if [ "$TOTAL" -eq 0 ]; then
    echo "Keine Instanz/Methode-Kombinationen gefunden (instances/ oder methods/ leer?)." >&2
    exit 1
fi

echo "Instanzen x Methoden = $TOTAL zu rechnende Kombinationen."

ARRAY_JOB_IDS=()
start=0
while [ "$start" -lt "$TOTAL" ]; do
    end=$((start + MAX_ARRAY_CHUNK))
    if [ "$end" -gt "$TOTAL" ]; then
        end="$TOTAL"
    fi
    last=$((end - 1))

    echo "Reiche Array-Job ein: Tasks $start-$last (max. $MAX_CONCURRENT gleichzeitig)..."
    job_id=$(sbatch --parsable --array="${start}-${last}%${MAX_CONCURRENT}" solve_array.sh)
    echo "  -> Array-Job: $job_id"
    ARRAY_JOB_IDS+=("$job_id")

    start="$end"
done

# Mehrere Job-IDs durch ":" getrennt -> Slurm wartet auf ALLE davon.
DEPENDENCY="afterany:$(IFS=:; echo "${ARRAY_JOB_IDS[*]}")"

# TODO: Mail-Adresse eintragen. Der Merge-Job laeuft erst nach dem letzten Task,
# seine END-Mail bedeutet also "alles fertig".
MERGE_JOB_ID=$(sbatch --parsable --mail-type=END,FAIL --mail-user="julius.hoffmann@kit.edu" \
    --dependency="$DEPENDENCY" merge_results.sh)
echo "  -> Merge-Job: $MERGE_JOB_ID (startet automatisch, sobald alle $TOTAL Tasks fertig sind)"

echo ""
echo "Fortschritt verfolgen:   squeue -u \$USER"
echo "Endergebnis erscheint:   results/final_results.csv"
