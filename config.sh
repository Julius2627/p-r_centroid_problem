#!/bin/bash
# Zentrale Konfiguration -- HIER EINMAL anpassen, statt in jedem einzelnen
# Script. Wird von setup_env.sh, submit_all.sh, solve_array.sh und
# merge_results.sh per `source config.sh` eingebunden.

# TODO: einmalig einen Workspace anlegen:  ws_allocate gurobi_ws 60
#       (Laufzeit in Tagen anpassen; vor Ablauf ggf. mit ws_extend verlaengern)
WSROOT="$(ws_find gpr_classic_ws)"
REPO="$WSROOT/repo"
VENV_DIR="$WSROOT/venv"

# TODO: exakte Modulnamen/-versionen auf dem Cluster pruefen:
#   module avail devel/python
#   module avail optimization/gurobi
PYTHON_MODULE="devel/python/3.12"
GUROBI_MODULE="optimization/gurobi/12.0.3"

# TODO: nur setzen, falls das Gurobi-Modul GRB_LICENSE_FILE NICHT bereits
# automatisch setzt. Pruefen mit:
#   module load "$GUROBI_MODULE" && env | grep GRB
# Falls dort schon ein Pfad steht: diese Zeile auskommentiert lassen.
# export GRB_LICENSE_FILE="$HOME/gurobi.lic"
