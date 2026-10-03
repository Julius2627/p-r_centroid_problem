#!/usr/bin/env python3
"""
main.py -- fuehrt eine Loesungsmethode auf einer Instanz aus und schreibt
das Ergebnis als eine Zeile in eine CSV-Datei.

ZWEI Aufrufarten:

1) Grid-Modus (empfohlen, so ruft solve_array.sh dieses Script auf):
   Jeder Slurm-Array-Task bekommt genau EINE (Instanz, Methode)-Kombination
   zugewiesen. Das ist die feinste sinnvolle Aufteilung ("stueckeln"),
   damit nicht ein einzelner Job alle Methoden nacheinander abarbeitet
   und dadurch Tage braucht -- stattdessen laufen viele Kombinationen
   gleichzeitig auf dem Cluster.

       python main.py --task-id $SLURM_ARRAY_TASK_ID --instance-dir instances

   Gesamtzahl der Kombinationen abfragen (für die Array-Groesse in
   submit_all.sh):

       python main.py --count --instance-dir instances

2) Manueller Modus (lokales Testen / gezielter Einzellauf, z.B. am
   Login-Node oder auf deinem Laptop):

       python main.py instances/beispiel.csv --models methodeA methodeB

Jede Datei in methods/ muss eine Funktion

    def solve(instance_path: str, time_limit: int) -> dict

bereitstellen (mindestens die Schluessel objective, bound, gap,
runtime_sec, status), siehe methods/_TEMPLATE_method.py als Vorlage.

Lizenz: Bevor die erste Methode rechnet, wird per gurobi_license.acquire_license()
ein Gurobi-Token reserviert. Sind alle Tokens vergeben, wird in Abstaenden
erneut versucht (Optionen --license-wait / --license-poll). Klappt es bis zum
Ablauf nicht, landet pro Methode eine Zeile mit status=NO_LICENSE in der
Ergebnisdatei und das Programm endet mit Exit-Code 1.
"""
import argparse
import csv
import importlib
import sys
import time
import traceback
from pathlib import Path

import grid

RESULT_FIELDS = [
    "instance",
    "model",
    "wall_time_sec",
    "status",
    "problem_catrgory",
    "instance_number",
    "n",
    "p",
    "objective",
    "value_pmed_classic",
    "value_pmed_new",
    "bound",
    "gap",
    "total_weight",
    "iterations",
    "runtime",
    "runtime_ll",
    "runtime_cb",
    "runtime_precalc_para",
    "runtime_precalc_heur",
    "model_loading_time",
    "total_time",
    "workTime_heur",
    "workTime_main",
    "workTime_ll",
    "max_memory",
    "nr_solutions",
    "license_wait_sec",
    "error",]


def run_one(model_name: str, instance_path: Path, nr_fac: int, time_limit: int, license_wait: float = 0.0) -> dict:
    """Eine Methode auf einer Instanz ausfuehren. Fehler werden abgefangen
    und als Ergebniszeile mit status=ERROR festgehalten, statt den ganzen
    Task abstuerzen zu lassen -- so bleibt sichtbar, WELCHE Kombination
    fehlgeschlagen ist, statt dass einfach keine Ergebniszeile existiert."""
    start = time.time()
    try:
        module = importlib.import_module(f"methods.{model_name}")
        result = module.solve(str(instance_path), nr_fac, time_limit)
        result.setdefault("status", "OK")
        result.setdefault("error", "")
    except Exception as exc:
        traceback.print_exc()
        result = {
            "status": "ERROR",
            "objective": "",
            "bound": "",
            "gap": "",
            "runtime_sec": "",
            "error": f"{type(exc).__name__}: {exc}",
        }

    result["wall_time_sec"] = str(round(time.time() - start, 2))
    result["instance"] = instance_path.stem
    result["model"] = model_name
    result["license_wait_sec"] = str(round(license_wait, 1))
    return {field: result.get(field, "") for field in RESULT_FIELDS}

def no_license_row(model_name: str, instance_path: Path, waited: float, message: str) -> dict:
    """Ergebniszeile fuer eine Kombination, die wegen fehlender Lizenz nie gerechnet wurde."""
    row = {field: "" for field in RESULT_FIELDS}
    row.update(
        instance=instance_path.stem,
        model=model_name,
        status="NO_LICENSE",
        license_wait_sec=str(round(waited, 1)),
        error=message,
    )
    return row

def write_rows(rows, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("instance", nargs="?", help="Pfad zur Instanz-CSV (manueller Modus)")
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help="Methodennamen fuer den manuellen Modus (Default: alle in methods/)",
    )
    parser.add_argument(
        "--task-id",
        type=int,
        default=None,
        help="0-basierte Slurm-Array-Task-ID (Grid-Modus, z.B. $SLURM_ARRAY_TASK_ID)",
    )
    parser.add_argument(
        "--instance-dir",
        default="instances",
        help="Ordner mit Instanz-CSVs, fuer --task-id und --count (Default: instances)",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="Nur Gesamtzahl (Instanzen x Methoden x Facility_Oeffnungen) ausgeben und beenden",
    )
    parser.add_argument(
        "--time-limit",
        type=int,
        default=3600,
        help="Gurobi-Zeitlimit pro Lauf in Sekunden (an solve() weitergereicht)",
    )
    parser.add_argument(
        "--nr-of-facilities",
        nargs="+",
        type=int,
        default=None,
        help="Zahl an zu errichtenden facilities fuer den Lauf",
    )
    parser.add_argument(
        "--license-wait",
        type=float,
        default=900.0,
        help="Maximale Wartezeit in Sekunden auf ein freies Gurobi-Token "
        "(Default 900; 0 = nur ein Versuch, nicht warten)",
    )
    parser.add_argument(
        "--license-poll",
        type=float,
        default=60.0,
        help="Sekunden zwischen zwei Lizenz-Versuchen (Default 60, +-25 %% Streuung)",
    )
    parser.add_argument(
        "--skip-license-check",
        action="store_true",
        help="Lizenz-Reservierung ueberspringen (nur fuer Methoden ganz ohne Gurobi)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Zieldatei fuer das Ergebnis (Default wird automatisch bestimmt)",
    )
    args = parser.parse_args()

    if args.count:
        print(grid.grid_size(args.instance_dir))
        return

    if args.task_id is not None:
        instance_path, model_name, nr_facilities = grid.resolve_grid_task(args.task_id, args.instance_dir)
        models = [model_name]
    else:
        if not args.instance:
            parser.error("Entweder <instance> angeben oder --task-id/--count verwenden.")
        instance_path = Path(args.instance)
        if not instance_path.is_file():
            raise SystemExit(f"Instanzdatei nicht gefunden: {instance_path}")
        models = args.models or grid.discover_methods()
        if not models:
            raise SystemExit("Keine Methoden in methods/ gefunden.")
        if not args.nr_of_facilities:
            raise SystemExit("Keine Zahl an zu oeffnenden Facilities gegeben.")
        nr_facilities = args.nr_of_facilities

    if args.output:
        output_path = Path(args.output)
    elif len(models) == 1:
        output_path = Path("results/partial") / f"{grid.result_stem(instance_path, models[0], nr_facilities)}.csv"
    else:
        output_path = Path("results/partial") / f"{instance_path.stem}.csv"

    # Lizenz reservieren, BEVOR gerechnet wird (wartet notfalls, siehe gurobi_license.py).
    # Der Import steht hier, damit --count auch ohne gurobipy funktioniert.
    waited = 0.0
    if not args.skip_license_check:
        import gurobi_license

        try:
            waited = gurobi_license.acquire_license(
                max_wait=args.license_wait, poll_interval=args.license_poll
            )
        except gurobi_license.LicenseUnavailableError as exc:
            print(f"FEHLER: {exc}", file=sys.stderr, flush=True)
            rows = [no_license_row(m, instance_path, exc.waited, str(exc)) for m in models]
            write_rows(rows, output_path)
            print(f"{len(rows)} NO_LICENSE-Zeile(n) geschrieben nach {output_path}")
            sys.exit(1)

    rows = []
    for model_name in models:
        print(f"[{instance_path.name}] starte Methode '{model_name}' mit '{nr_facilities}' zu oeffnenden facilities ...", flush=True)
        rows.append(run_one(model_name, instance_path, nr_facilities, args.time_limit, waited))

    write_rows(rows, output_path)
    print(f"{len(rows)} Ergebniszeile(n) geschrieben nach {output_path}")


if __name__ == "__main__":
    main()
