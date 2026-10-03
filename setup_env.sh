#!/bin/bash
# Einmaliges Setup der Python-Umgebung mit exakt gesperrten Versionen
# (requirements.txt). Direkt auf dem Login-Node ausfuehren:
#
#   bash setup_env.sh
#
# Erneut ausfuehren, wenn sich requirements.txt aendert (z.B. nach einem
# neuen `pip freeze` auf deinem lokalen Rechner).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

module load "$PYTHON_MODULE"
module load "$GUROBI_MODULE"   # fuer Lizenz-Umgebungsvariablen, siehe config.sh

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "Pruefe gurobipy + Lizenz ..."
python3 -c "
import gurobipy as gp
m = gp.Model()
print('gurobipy Version:', gp.gurobi.version())
print('Lizenz OK.')
"

echo ""
echo "Fertig. Environment liegt unter: $VENV_DIR"
echo "Wird von solve_array.sh / merge_results.sh automatisch aktiviert."
