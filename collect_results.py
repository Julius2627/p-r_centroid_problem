#!/usr/bin/env python3
"""
collect_results.py -- fasst alle results/partial/*.csv zu einer
einzigen results/final_results.csv zusammen und meldet, welche
(Instanz, Methode)-Kombinationen KEIN Ergebnis geliefert haben
(z.B. wegen OOM oder Walltime-Kill, bevor main.py etwas speichern
konnte).

Wird automatisch von merge_results.sh aufgerufen, nachdem der
komplette Array-Job durchgelaufen ist (auch wenn einzelne Tasks
fehlgeschlagen sind).
"""
import argparse
import csv
from pathlib import Path

import grid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partial-dir", required=True, help="Ordner mit den Teil-CSVs")
    parser.add_argument("--instance-dir", required=True, help="Ordner mit den Instanz-CSVs")
    parser.add_argument("--output", required=True, help="Zielpfad der finalen CSV")
    args = parser.parse_args()

    partial_dir = Path(args.partial_dir)
    instance_dir = Path(args.instance_dir)
    output_path = Path(args.output)

    partial_files = sorted(partial_dir.glob("*.csv"))
    if not partial_files:
        raise SystemExit(f"Keine Teil-Ergebnisse in {partial_dir} gefunden.")

    rows = []
    fieldnames = None
    for f in partial_files:
        with open(f, newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = fieldnames or reader.fieldnames
            rows.extend(reader)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Abgleich gegen das erwartete volle Raster (Instanzen x Methoden),
    # mit denselben Discovery-Funktionen wie main.py -> garantiert konsistent.
    instances = grid.discover_instances(instance_dir)
    models = grid.discover_methods()
    expected = {grid.result_stem(i, m, p) for i in instances for m in models for p in grid.NR_FACILITIES}
    got = {p.stem for p in partial_files}
    missing = sorted(expected - got)

    print(
        f"{len(rows)} Ergebniszeile(n) aus {len(partial_files)} Datei(en) "
        f"geschrieben nach {output_path}"
    )
    print(f"Erwartete Kombinationen (Instanzen x Methoden): {len(expected)}")

    if missing:
        print(f"WARNUNG: {len(missing)} Kombination(en) fehlen (kein Ergebnis geliefert):")
        for m in missing:
            print(f"  - {m}")
    else:
        print("Alle Instanz/Methode-Kombinationen haben ein Ergebnis geliefert.")


if __name__ == "__main__":
    main()
