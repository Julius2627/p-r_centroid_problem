#!/bin/bash
# Zentrale Konfiguration -- HIER EINMAL anpassen, statt in jedem einzelnen
# Script. Wird von setup_env.sh, submit_all.sh, solve_array.sh und
# merge_results.sh per `source config.sh` eingebunden.

# TODO: einmalig einen Workspace anlegen:  ws_allocate gurobi_ws 60
#       (Laufzeit in Tagen anpassen; vor Ablauf ggf. mit ws_extend verlaengern)
WSROOT="$(ws_find pr_classic_ws)"
REPO="$WSROOT/repo"
VENV_DIR="$WSROOT/venv"

# TODO: exakte Modulnamen/-versionen auf dem Cluster pruefen:
#   module spider gurobi
#   module avail devel/python
# (Bestaetigt: Gurobi liegt in der Kategorie "optimization". Die
# Kategorienliste im Wiki ist also unvollstaendig.)
PYTHON_MODULE="devel/python/3.12"
GUROBI_MODULE="optimization/gurobi/12.0.3"

# Maximale Groesse EINES einzelnen Slurm-Array-Jobs. Mehr Kombinationen werden
# von submit_all.sh automatisch auf mehrere Array-Jobs aufgeteilt.
# TODO: an die tatsaechliche Cluster-Grenze anpassen:
#   scontrol show config | grep MaxArraySize
# 1000 ist ein verbreiteter Slurm-Default (Indizes 0-999), kann aber je nach
# Cluster hoeher oder niedriger sein.
MAX_ARRAY_CHUNK=1000

# Lizenz: Das Gurobi-Modul setzt GRB_LICENSE_FILE selbst auf eine zentrale
# Client-Lizenz (gurobi_client.lic, Token-Server) -- bei dir bestaetigt
# ueber `module show`. Deshalb hier NICHTS setzen: eine eigene
# GRB_LICENSE_FILE-Zeile wuerde die zentrale Lizenz ueberschreiben.
# Massgeblich ist der Lizenz-Test (check_license.py bzw. test_license.sh).
